"""SQLite durability, ownership, and recovery evidence."""

from datetime import datetime, timezone
import gc
import json
import multiprocessing
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch
import weakref

from event_store_contract import decision, graph_event, metadata, receipt, request
from problemforger.core.journal import (
    CRunRecoveryContext,
    GovernanceOutcome,
    JsonDocument,
    ProposalAbandoned,
    ProposalReceipt,
    ProposalStatus,
    proposal_request_hash,
    serialize_entry,
)
from problemforger.config.event_store import (
    MemoryEventStoreConfig,
    ServiceProfile,
    SqliteEventStoreConfig,
    build_event_store,
)
from problemforger.modules.persistence import (
    ForkedProviderError,
    MemoryEventStore,
    SqliteEventStore,
    StoreClosedError,
    StoreIdentityChangedError,
    StoreInUseError,
    UnsupportedStoreError,
)
from problemforger.modules.persistence._base import MAX_JOURNAL_RECORD_BYTES
from problemforger.ports.event_store import (
    AppendResult,
    CreateRunStatus,
    RecordProposalStatus,
    RunMetadata,
    StoreDurability,
    StoreErrorCode,
)


LINUX = sys.platform.startswith("linux")


def _contending_open(path: str, start, released, results) -> None:
    start.wait(5)
    try:
        store = SqliteEventStore(path)
    except StoreInUseError:
        results.put("in_use")
        return
    results.put("opened")
    released.wait(10)
    store.close()


def _forked_use(path: str, inherited_store, results) -> None:
    try:
        inherited_store.current_graph_version("run-1")
    except ForkedProviderError:
        results.put("inherited_rejected")
    try:
        store = SqliteEventStore(path)
    except StoreInUseError:
        results.put("owner_still_active")
    else:
        results.put("unexpected_open")
        store.close()


def _forked_use_while_parent_lock_is_held(path: str, inherited_store, results, open_after_release) -> None:
    try:
        inherited_store.current_graph_version("run-1")
    except ForkedProviderError:
        results.put("inherited_rejected")
    try:
        SqliteEventStore(path)
    except StoreInUseError:
        results.put("owner_still_active")
    open_after_release.wait(10)
    try:
        store = SqliteEventStore(path)
    except Exception as error:
        results.put(f"reopen_failed:{type(error).__name__}")
    else:
        results.put("reopened_after_owner_close")
        store.close()


def _crash_with_journal(path: str, phase: str) -> None:
    store = SqliteEventStore(path)
    store.create_run("run-1", RunMetadata.from_value({"source": "crash-test"}))
    proposal_receipt = receipt("crash")
    store.record_proposal(
        "run-1", "crash", proposal_receipt.request_hash,
        proposal_receipt.request, proposal_receipt,
    )
    if phase == "receipt":
        os._exit(23)

    if phase == "partial_batch":
        connection = store._connection
        # Force dirty pages to spill so the child leaves a hot rollback journal.
        connection.execute("PRAGMA cache_size=1")

        class ExitDuringBatch:
            inserts = 0

            def execute(self, sql, parameters=()):
                result = connection.execute(sql, parameters)
                if sql.startswith("INSERT INTO journal"):
                    self.inserts += 1
                    if self.inserts == 2:
                        os._exit(23)
                return result

            def __getattr__(self, name):
                return getattr(connection, name)

        store._connection = ExitDuringBatch()

    result = store.append_graph(
        "run-1", "crash", 0, (decision("crash"),),
        (
            graph_event("crash", record_id="event-1", payload={"data": "x" * 32_768}),
            graph_event("crash", record_id="event-2"),
        ),
    )
    assert isinstance(result, AppendResult)
    os._exit(23)


class SqliteEventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.path = Path(self.temporary.name) / "events.db"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def open_store(self) -> SqliteEventStore:
        return SqliteEventStore(self.path)

    def _create_run(self, store: SqliteEventStore) -> None:
        self.assertEqual(
            CreateRunStatus.CREATED,
            store.create_run("run-1", RunMetadata.from_value({"source": "sqlite-test"})).status,
        )

    def _submit(self, store: SqliteEventStore, proposal_id: str, expected: int = 0) -> None:
        normalized = request(expected, proposal_id)
        record = receipt(proposal_id, expected)
        self.assertEqual(
            RecordProposalStatus.CREATED,
            store.record_proposal(
                "run-1", proposal_id, proposal_request_hash(normalized), normalized, record
            ).status,
        )

    def _commit(self, store: SqliteEventStore, proposal_id: str, expected: int = 0) -> None:
        snapshot = store.get_proposal("run-1", proposal_id)
        record = decision(
            proposal_id,
            expected_version=expected,
            request_hash=snapshot.request_hash,
            record_id=f"{proposal_id}-commit",
        )
        event = graph_event(
            proposal_id,
            version=expected + 1,
            record_id=f"{proposal_id}-event",
        )
        self.assertIsInstance(
            store.append_graph("run-1", proposal_id, expected, (record,), (event,)),
            AppendResult,
        )

    def test_reopen_preserves_pending_and_completed_proposal_snapshots(self):
        store = self.open_store()
        self._create_run(store)
        self._submit(store, "committed")
        self._commit(store, "committed")
        self._submit(store, "rejected", 1)
        rejected = decision(
            "rejected",
            outcome=GovernanceOutcome.REJECT,
            expected_version=1,
            record_id="rejected-final",
        )
        store.append_audit("run-1", (rejected,), "rejected")
        self._submit(store, "abandoned", 1)
        abandoned = ProposalAbandoned(
            metadata("abandoned-final"),
            "abandoned",
            proposal_request_hash(request(1, "abandoned")),
            "runtime_unavailable",
        )
        store.append_audit("run-1", (abandoned,), "abandoned")
        self._submit(store, "pending", 1)
        before = tuple(serialize_entry(item) for item in store.read_journal("run-1", limit=100).records)
        store.close()

        reopened = self.open_store()
        self.assertEqual(before, tuple(serialize_entry(item) for item in reopened.read_journal("run-1", limit=100).records))
        self.assertEqual(1, reopened.current_graph_version("run-1"))
        self.assertEqual(GovernanceOutcome.COMMIT, reopened.get_proposal("run-1", "committed").status)
        self.assertEqual(GovernanceOutcome.REJECT, reopened.get_proposal("run-1", "rejected").status)
        self.assertEqual(ProposalStatus.ABANDONED, reopened.get_proposal("run-1", "abandoned").status)
        self.assertEqual(ProposalStatus.PENDING, reopened.get_proposal("run-1", "pending").status)
        pending_position = reopened.get_proposal("run-1", "pending").last_journal_position
        self.assertEqual(len(before), pending_position)
        reopened.close()

    def test_reopen_preserves_c_run_recovery_context_outside_request_hash(self):
        store = self.open_store()
        context = CRunRecoveryContext(
            manifest_hash="sha256:manifest",
            effective_graph_intervention_identity="sha256:graph-intervention",
            effective_governance_policy_identity="sha256:governance-policy",
        )
        normalized = request(0, "c-proposal")
        record = ProposalReceipt(
            metadata("c-proposal-receipt"),
            "c-proposal",
            normalized,
            c_run_recovery_context=context,
        )
        self._create_run(store)
        created = store.record_proposal(
            "run-1",
            "c-proposal",
            proposal_request_hash(normalized),
            normalized,
            record,
        )
        self.assertEqual(RecordProposalStatus.CREATED, created.status)
        expected_hash = created.proposal.request_hash
        store.close()

        reopened = self.open_store()
        recovered = reopened.get_proposal("run-1", "c-proposal")
        stored_record = reopened.read_journal("run-1", limit=10).records[0].record
        self.assertEqual(normalized, recovered.normalized_request)
        self.assertEqual(expected_hash, recovered.request_hash)
        self.assertEqual(context, stored_record.c_run_recovery_context)
        reopened.close()

    def test_process_restart_recovers_pending_receipt_without_duplicate_attempt(self):
        store = self.open_store()
        self._create_run(store)
        self._submit(store, "pending")
        expected_position = store.get_run("run-1").last_journal_position
        store.close()
        probe = (
            "import json,sys; "
            "sys.path.insert(0,sys.argv[2]); "
            "from event_store_contract import decision,graph_event,receipt; "
            "from problemforger.modules.persistence import SqliteEventStore; "
            "s=SqliteEventStore(sys.argv[1]); "
            "p=s.get_proposal('run-1','pending'); "
            "print(json.dumps([p.status.value,p.last_journal_position,s.get_run('run-1').graph_version])); "
            "resubmitted=s.record_proposal('run-1','pending',p.request_hash,p.normalized_request,receipt('pending')); "
            "assert resubmitted.status.value == 'EXISTING'; "
            "committed=s.append_graph('run-1','pending',0,(decision('pending'),),(graph_event('pending'),)); "
            "assert committed.new_graph_version == 1; "
            "s.close()"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe, str(self.path), str(Path(__file__).parent)],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(["PENDING", expected_position, 0], json.loads(completed.stdout))
        with self.open_store() as final_store:
            completed_entries = final_store.read_journal("run-1", limit=10).records
            final = final_store.get_proposal("run-1", "pending")
            resubmitted = final_store.record_proposal(
                "run-1", "pending", final.request_hash, final.normalized_request,
                receipt("pending"),
            )
            self.assertEqual(RecordProposalStatus.EXISTING, resubmitted.status)
            replay = final_store.append_graph(
                "run-1", "pending", 0, (decision("pending"),),
                (graph_event("pending"),),
            )
            self.assertTrue(replay.replayed)
            self.assertEqual(GovernanceOutcome.COMMIT, final.status)
            self.assertEqual(1, final_store.current_graph_version("run-1"))
            self.assertEqual(completed_entries, final_store.read_journal("run-1", limit=10).records)
            self.assertEqual(3, len(completed_entries))

    def test_failed_multi_record_insert_rolls_back_head_graph_and_all_events(self):
        store = self.open_store()
        self._create_run(store)
        self._submit(store, "transaction")
        store._connection.execute(
            "CREATE TRIGGER fail_graph_event BEFORE INSERT ON journal "
            "WHEN NEW.record_id = 'transaction-event' BEGIN "
            "SELECT RAISE(ABORT, 'injected append failure'); END"
        )
        commit = decision(
            "transaction",
            request_hash=store.get_proposal("run-1", "transaction").request_hash,
            record_id="transaction-commit",
        )
        event = graph_event("transaction", record_id="transaction-event")
        with self.assertRaises(sqlite3.IntegrityError):
            store.append_graph("run-1", "transaction", 0, (commit,), (event,))
        self.assertEqual(1, store.get_run("run-1").last_journal_position)
        self.assertEqual(0, store.current_graph_version("run-1"))
        self.assertEqual(ProposalStatus.PENDING, store.get_proposal("run-1", "transaction").status)
        self.assertEqual((1,), tuple(e.journal_position for e in store.read_journal("run-1", limit=10).records))
        store._connection.execute("DROP TRIGGER fail_graph_event")
        store.close()
        reopened = self.open_store()
        self.assertEqual(1, reopened.get_run("run-1").last_journal_position)
        reopened.close()

    def test_interrupted_return_after_commit_reconciles_the_live_cache(self):
        store = self.open_store()
        run_metadata = RunMetadata.from_value({"source": "interruption-test"})
        persist = store._persist_transition

        def persist_then_interrupt(*args) -> None:
            persist(*args)
            raise KeyboardInterrupt

        with patch.object(store, "_persist_transition", side_effect=persist_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                store.create_run("interrupted-create", run_metadata)
        self.assertEqual(
            CreateRunStatus.EXISTING,
            store.create_run("interrupted-create", run_metadata).status,
        )

        self._create_run(store)
        self._submit(store, "interrupted-commit")
        proposal = store.get_proposal("run-1", "interrupted-commit")
        commit = decision(
            "interrupted-commit",
            request_hash=proposal.request_hash,
            record_id="interrupted-commit-record",
        )
        event = graph_event("interrupted-commit", record_id="interrupted-commit-event")
        with patch.object(store, "_persist_transition", side_effect=persist_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                store.append_graph("run-1", "interrupted-commit", 0, (commit,), (event,))
        self.assertEqual(1, store.current_graph_version("run-1"))
        self.assertEqual(
            GovernanceOutcome.COMMIT,
            store.get_proposal("run-1", "interrupted-commit").status,
        )
        replay = store.append_graph("run-1", "interrupted-commit", 0, (commit,), (event,))
        self.assertTrue(replay.replayed)
        self.assertEqual(3, replay.last_journal_position)
        store.close()

    def test_failed_rollback_poisoning_prevents_a_phantom_cached_run(self):
        store = self.open_store()
        original_connection = store._connection

        class CommitAndRollbackFail:
            @property
            def in_transaction(self):
                return original_connection.in_transaction

            def execute(self, statement, *parameters):
                if statement in {"COMMIT", "ROLLBACK"}:
                    raise sqlite3.OperationalError("injected transaction failure")
                return original_connection.execute(statement, *parameters)

            def __getattr__(self, name):
                return getattr(original_connection, name)

        store._connection = CommitAndRollbackFail()
        with self.assertRaises(sqlite3.OperationalError):
            store.create_run("uncertain-run", RunMetadata.from_value({"source": "failure"}))
        with self.assertRaises(StoreClosedError):
            store.get_run("uncertain-run")
        store.close()

        reopened = self.open_store()
        self.assertEqual(StoreErrorCode.NOT_FOUND, reopened.get_run("uncertain-run").code)
        reopened.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock and mount information")
    def test_one_live_owner_covers_same_path_symlink_and_hardlink_aliases(self):
        store = self.open_store()
        self._create_run(store)
        with self.assertRaises(StoreInUseError):
            SqliteEventStore(self.path)

        alias = self.path.with_name("alias.db")
        alias.symlink_to(self.path)
        with self.assertRaises(StoreInUseError):
            SqliteEventStore(alias)

        hard_link = self.path.with_name("hard-link.db")
        hard_link.hardlink_to(self.path)
        with self.assertRaises(StoreInUseError):
            SqliteEventStore(hard_link)

        independent = SqliteEventStore(self.path.with_name("independent.db"))
        self.assertIsInstance(independent, SqliteEventStore)
        independent.close()
        store.close()
        with self.assertRaises(UnsupportedStoreError):
            SqliteEventStore(hard_link)
        hard_link.unlink()
        reopened = SqliteEventStore(self.path)
        reopened.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock and mount information")
    def test_hard_linked_database_is_rejected_without_a_live_owner(self):
        store = self.open_store()
        store.close()
        hard_link = self.path.with_name("hard-link.db")
        hard_link.hardlink_to(self.path)
        with self.assertRaises(UnsupportedStoreError):
            SqliteEventStore(hard_link)
        hard_link.unlink()
        reopened = self.open_store()
        reopened.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_replaced_store_or_lock_identity_fails_closed_and_blocks_second_owner(self):
        store = self.open_store()
        self._create_run(store)
        replacement = self.path.with_name("replacement.db")
        connection = sqlite3.connect(replacement)
        connection.close()
        os.replace(replacement, self.path)
        with self.assertRaises(StoreIdentityChangedError):
            store.current_graph_version("run-1")
        with self.assertRaises(StoreInUseError):
            SqliteEventStore(self.path)
        store.close()

        store = SqliteEventStore(self.path)
        lock_path = self.path.with_name(f".{self.path.name}.problemforger.lock")
        lock_replacement = lock_path.with_suffix(".replacement")
        lock_replacement.write_text("replacement", encoding="utf-8")
        os.replace(lock_replacement, lock_path)
        with self.assertRaises(StoreIdentityChangedError):
            store.current_graph_version("run-1")
        store.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_competing_process_opens_have_exactly_one_owner(self):
        context = multiprocessing.get_context("fork")
        start = context.Event()
        released = context.Event()
        results = context.Queue()
        processes = [
            context.Process(target=_contending_open, args=(str(self.path), start, released, results))
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        start.set()
        outcomes = [results.get(timeout=10), results.get(timeout=10)]
        released.set()
        for process in processes:
            process.join(10)
            self.assertEqual(0, process.exitcode)
        self.assertCountEqual(["opened", "in_use"], outcomes)
        reopened = self.open_store()
        self.assertEqual(StoreErrorCode.NOT_FOUND, reopened.get_run("unknown").code)
        reopened.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_forked_child_cannot_use_inherited_provider_and_reopens_after_owner_closes(self):
        store = self.open_store()
        self._create_run(store)
        context = multiprocessing.get_context("fork")
        results = context.Queue()
        child = context.Process(target=_forked_use, args=(str(self.path), store, results))
        child.start()
        outcomes = [results.get(timeout=10), results.get(timeout=10)]
        child.join(10)
        self.assertEqual(0, child.exitcode)
        self.assertCountEqual(["inherited_rejected", "owner_still_active"], outcomes)
        store.close()
        reopened = self.open_store()
        self.assertEqual(0, reopened.get_run("run-1").graph_version)
        reopened.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_fork_callback_replaces_inherited_lock_before_rejecting_provider(self):
        store = self.open_store()
        self._create_run(store)
        context = multiprocessing.get_context("fork")
        results = context.Queue()
        release_parent_lock = Event()
        parent_lock_acquired = Event()

        def hold_store_lock() -> None:
            with store._lock:
                parent_lock_acquired.set()
                release_parent_lock.wait(10)

        holder = Thread(target=hold_store_lock)
        holder.start()
        self.assertTrue(parent_lock_acquired.wait(5))
        open_after_release = context.Event()
        child = context.Process(
            target=_forked_use_while_parent_lock_is_held,
            args=(str(self.path), store, results, open_after_release),
        )
        child.start()
        try:
            outcomes = [results.get(timeout=10), results.get(timeout=10)]
            self.assertCountEqual(["inherited_rejected", "owner_still_active"], outcomes)
        finally:
            release_parent_lock.set()
            holder.join(5)
        store.close()
        open_after_release.set()
        self.assertEqual("reopened_after_owner_close", results.get(timeout=10))
        child.join(10)
        self.assertEqual(0, child.exitcode)

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_crash_releases_os_ownership_for_normal_reopen(self):
        script = (
            "import os,sys; from problemforger.modules.persistence import SqliteEventStore; "
            "store=SqliteEventStore(sys.argv[1]); os._exit(0)"
        )
        subprocess.run(
            [sys.executable, "-c", script, str(self.path)],
            check=True,
            timeout=10,
        )
        reopened = self.open_store()
        self.assertEqual(StoreErrorCode.NOT_FOUND, reopened.get_run("missing").code)
        reopened.close()

    def test_collected_unclosed_provider_releases_ownership(self):
        for cyclic in (False, True):
            with self.subTest(cyclic=cyclic):
                store = self.open_store()
                store.create_run("run-1", RunMetadata.from_value({"source": "gc-test"}))
                if cyclic:
                    store._test_cycle = store
                reference = weakref.ref(store)
                del store
                gc.collect()
                self.assertIsNone(reference())
                with self.open_store() as reopened:
                    self.assertEqual(0, reopened.get_run("run-1").graph_version)

    def test_abrupt_exit_preserves_durable_prefix_and_recovers_hot_journal(self):
        context = multiprocessing.get_context("spawn")
        for phase in ("receipt", "commit", "partial_batch"):
            with self.subTest(phase=phase):
                path = self.path.with_name(f"{phase}.db")
                child = context.Process(target=_crash_with_journal, args=(str(path), phase))
                child.start()
                child.join(10)
                if child.is_alive():
                    child.kill()
                    child.join(5)
                    self.fail("crash probe did not exit")
                self.assertEqual(23, child.exitcode)
                if phase == "partial_batch":
                    with Path(f"{path}-journal").open("rb") as journal:
                        self.assertNotEqual(bytes(8), journal.read(8))
                with SqliteEventStore(path) as reopened:
                    committed = phase == "commit"
                    expected_positions = (1, 2, 3, 4) if committed else (1,)
                    entries = reopened.read_journal("run-1", limit=10).records
                    self.assertEqual(expected_positions, tuple(e.journal_position for e in entries))
                    self.assertEqual(int(committed), reopened.current_graph_version("run-1"))
                    self.assertEqual(len(entries), reopened.get_run("run-1").last_journal_position)
                    self.assertEqual(
                        GovernanceOutcome.COMMIT if committed else ProposalStatus.PENDING,
                        reopened.get_proposal("run-1", "crash").status,
                    )

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux fork callbacks")
    def test_fork_closes_ownership_while_cyclic_gc_finalizes_provider(self):
        report_read, report_write = os.pipe()
        child_release_read, child_release_write = os.pipe()
        entered = Event()
        release_gc = Event()
        original = SqliteEventStore._release_resources
        store = self.open_store()
        store._test_cycle = store
        descriptors = (store._owner_fd, store._path_lock_fd)
        reference = weakref.ref(store)
        del store

        def paused(provider):
            if provider._path == self.path:
                entered.set()
                if not release_gc.wait(10):
                    raise TimeoutError("GC resource release was not resumed")
            original(provider)

        child = None
        try:
            with patch.object(SqliteEventStore, "_release_resources", paused):
                collector = Thread(target=gc.collect)
                collector.start()
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertIsNone(reference(), "cyclic GC must have cleared provider weak references")
                    child = os.fork()
                    if child == 0:
                        retained = False
                        for descriptor in descriptors:
                            try:
                                os.fstat(descriptor)
                            except OSError:
                                pass
                            else:
                                retained = True
                        os.write(report_write, b"open" if retained else b"closed")
                        os.read(child_release_read, 1)
                        os._exit(0)
                    readable, _, _ = select.select([report_read], [], [], 5)
                    self.assertTrue(readable, "child did not report ownership cleanup")
                    child_state = os.read(report_read, 10)
                finally:
                    release_gc.set()
                    collector.join(10)
            self.assertFalse(collector.is_alive())
            self.assertEqual((0, 0), os.waitpid(child, os.WNOHANG), "child must remain alive during reopen")
            with self.open_store():
                pass
            self.assertEqual(b"closed", child_state)
        finally:
            if child is not None:
                os.write(child_release_write, b"x")
                os.waitpid(child, 0)
            for descriptor in (report_read, report_write, child_release_read, child_release_write):
                os.close(descriptor)

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux fork callbacks")
    def test_independent_open_and_fork_can_finish_while_another_store_loads(self):
        loading = Event()
        release = Event()
        independent_finished = Event()
        paused_providers = []
        errors = []
        original = SqliteEventStore._load_state

        def paused(provider):
            if provider._path == self.path:
                paused_providers.append(provider)
                loading.set()
                if not release.wait(10):
                    raise TimeoutError("journal load was not released")
            return original(provider)

        def first_open():
            try:
                with self.open_store():
                    pass
            except BaseException as error:
                errors.append(error)

        def independent_open_and_fork():
            try:
                with SqliteEventStore(self.path.with_name("independent.db")):
                    pass
                child = os.fork()
                if child == 0:
                    inherited = paused_providers[0]
                    clean = inherited._forked and inherited._owner_fd is None and inherited._path_lock_fd is None
                    os._exit(0 if clean else 1)
                _, status = os.waitpid(child, 0)
                if status != 0:
                    raise AssertionError("child retained ownership during journal loading")
            except BaseException as error:
                errors.append(error)
            finally:
                independent_finished.set()

        with patch.object(SqliteEventStore, "_load_state", paused):
            first = Thread(target=first_open)
            first.start()
            self.assertTrue(loading.wait(5))
            independent = Thread(target=independent_open_and_fork)
            independent.start()
            try:
                self.assertTrue(independent_finished.wait(5), "independent store opening or fork waited for journal loading")
            finally:
                release.set()
                first.join(10)
                independent.join(10)
        self.assertFalse(first.is_alive())
        self.assertFalse(independent.is_alive())
        self.assertEqual([], errors)

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux fork callbacks")
    def test_fork_waits_for_provider_construction_and_teardown(self):
        for phase in ("construction", "teardown"):
            with self.subTest(phase=phase):
                entered = Event()
                release = Event()
                fork_requested = Event()
                fork_completed = Event()
                errors = []
                opened = []
                method_name = "_acquire_ownership" if phase == "construction" else "_release_ownership"
                original = getattr(SqliteEventStore, method_name)
                store = self.open_store() if phase == "teardown" else None

                def paused(provider):
                    entered.set()
                    if not release.wait(10):
                        raise TimeoutError("lifecycle test was not released")
                    return original(provider)

                def lifecycle():
                    try:
                        if store is None:
                            opened.append(self.open_store())
                        else:
                            store.close()
                    except BaseException as error:
                        errors.append(error)

                def fork():
                    try:
                        fork_requested.set()
                        child = os.fork()
                        if child == 0:
                            os._exit(0)
                        fork_completed.set()
                        os.waitpid(child, 0)
                    except BaseException as error:
                        errors.append(error)

                with patch.object(SqliteEventStore, method_name, paused):
                    worker = Thread(target=lifecycle)
                    worker.start()
                    self.assertTrue(entered.wait(5))
                    forker = Thread(target=fork)
                    forker.start()
                    try:
                        self.assertTrue(fork_requested.wait(5))
                        self.assertFalse(fork_completed.wait(0.2), "fork escaped an active provider lifecycle transition")
                    finally:
                        release.set()
                        worker.join(10)
                        forker.join(10)
                        for provider in opened:
                            provider.close()
                        if store is not None:
                            store.close()
                self.assertFalse(worker.is_alive())
                self.assertFalse(forker.is_alive())
                self.assertTrue(fork_completed.is_set())
                self.assertEqual([], errors)

    def test_store_path_and_provider_lifecycle_errors_are_explicit(self):
        for unsupported in (":memory:", "file:events.db?mode=memory"):
            with self.subTest(path=unsupported), self.assertRaises(UnsupportedStoreError):
                SqliteEventStore(unsupported)
        directory = Path(self.temporary.name) / "directory"
        directory.mkdir()
        with self.assertRaises((UnsupportedStoreError, OSError)):
            SqliteEventStore(directory)
        with self.assertRaises(ValueError):
            SqliteEventStore(self.path, max_journal_page_size=0)
        with self.assertRaises(ValueError):
            SqliteEventStore(self.path, timeout_seconds=0)
        for timeout in (float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                SqliteEventStore(self.path, timeout_seconds=timeout)
        with self.open_store() as entered:
            self.assertIsInstance(entered, SqliteEventStore)
        store = self.open_store()
        store.close()
        with self.assertRaises(StoreClosedError):
            store.get_run("missing")
        with self.assertRaises(StoreClosedError):
            store.__enter__()

    @unittest.skipUnless(LINUX, "uses Linux mountinfo")
    def test_known_remote_and_unidentifiable_filesystems_are_rejected(self):
        store = object.__new__(SqliteEventStore)
        store._path = self.path
        mount_point = str(self.path.parent)
        remote = f"31 22 0:44 / {mount_point} rw,relatime - nfs4 server:/share rw\n"
        with patch("pathlib.Path.read_text", return_value=remote):
            with self.assertRaises(UnsupportedStoreError):
                store._assert_supported_filesystem()
        with patch("pathlib.Path.read_text", return_value="malformed mount row\n"):
            with self.assertRaises(UnsupportedStoreError):
                store._assert_supported_filesystem()

    def test_memory_provider_is_ephemeral_and_normal_profile_rejects_it(self):
        memory = build_event_store(MemoryEventStoreConfig(), profile=ServiceProfile.EPHEMERAL_TEST)
        self.assertIsInstance(memory, MemoryEventStore)
        self.assertEqual(StoreDurability.EPHEMERAL, memory.durability)
        memory.close()
        with self.assertRaisesRegex(ValueError, "requires a durable EventStore"):
            build_event_store(MemoryEventStoreConfig())
        with self.assertRaises(TypeError):
            build_event_store(MemoryEventStoreConfig(), profile="normal")

    def test_typed_sqlite_composition_builds_durable_provider(self):
        store = build_event_store(SqliteEventStoreConfig(self.path))
        self.assertEqual(StoreDurability.DURABLE, store.durability)
        store.close()

    def test_corrupt_durable_record_is_rejected_before_provider_becomes_available(self):
        store = self.open_store()
        self._create_run(store)
        self._submit(store, "corrupt")
        store.close()
        connection = sqlite3.connect(self.path)
        connection.execute("DROP TRIGGER journal_reject_update")
        connection.execute("UPDATE journal SET record_json = '{}' WHERE journal_position = 1")
        connection.commit()
        connection.close()
        with self.assertRaises(ValueError):
            self.open_store()

    def test_unsupported_schema_version_is_rejected_without_database_mutation(self):
        connection = sqlite3.connect(self.path)
        journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        self.assertEqual("wal", journal_mode)
        connection.execute(
            "CREATE TABLE store_info(singleton INTEGER PRIMARY KEY CHECK (singleton = 1), schema_version INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO store_info(singleton, schema_version) VALUES (1, 2)")
        connection.commit()
        connection.close()

        with self.assertRaises(UnsupportedStoreError):
            self.open_store()

        connection = sqlite3.connect(self.path)
        self.assertEqual("wal", connection.execute("PRAGMA journal_mode").fetchone()[0])
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        connection.close()
        self.assertEqual({"store_info"}, names)

    def test_corrupt_run_metadata_headers_and_orphan_journal_rows_are_rejected(self):
        corruptions = (
            "metadata_shape",
            "metadata_hash",
            "blank_run_id",
            "run_head",
            "unknown_run",
            "oversized_record",
        )
        for corruption in corruptions:
            with self.subTest(corruption=corruption):
                path = Path(self.temporary.name) / f"{corruption}.db"
                store = SqliteEventStore(path)
                store.create_run("run-1", RunMetadata.from_value({"source": "corruption-test"}))
                store.close()

                connection = sqlite3.connect(path)
                if corruption == "metadata_shape":
                    connection.execute("UPDATE runs SET metadata_json = '[]' WHERE run_id = 'run-1'")
                elif corruption == "metadata_hash":
                    connection.execute("UPDATE runs SET metadata_hash = 'sha256:wrong' WHERE run_id = 'run-1'")
                elif corruption == "blank_run_id":
                    connection.execute("UPDATE runs SET run_id = '' WHERE run_id = 'run-1'")
                elif corruption == "run_head":
                    connection.execute("UPDATE runs SET last_journal_position = 2 WHERE run_id = 'run-1'")
                elif corruption == "oversized_record":
                    connection.execute(
                        "INSERT INTO journal(run_id, journal_position, record_id, record_json) VALUES (?, ?, ?, ?)",
                        ("run-1", 1, "oversized-record", " " * (MAX_JOURNAL_RECORD_BYTES + 1)),
                    )
                    connection.execute(
                        "UPDATE runs SET last_journal_position = 1 WHERE run_id = 'run-1'"
                    )
                else:
                    connection.execute(
                        "INSERT INTO journal(run_id, journal_position, record_id, record_json) VALUES (?, ?, ?, ?)",
                        ("missing-run", 1, "orphan-record", "{}"),
                    )
                connection.commit()
                connection.close()
                with self.assertRaises(ValueError):
                    SqliteEventStore(path)


if __name__ == "__main__":
    unittest.main()
