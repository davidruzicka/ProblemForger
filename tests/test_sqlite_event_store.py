"""SQLite durability, ownership, and recovery evidence."""

from datetime import datetime, timezone
import gc
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
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


def _spawned_open_after_owner_closes(path: str, open_after_release, results) -> None:
    try:
        store = SqliteEventStore(path)
    except StoreInUseError:
        results.put("owner_still_active")
    else:
        results.put("unexpected_open")
        store.close()
        return
    open_after_release.wait(10)
    try:
        store = SqliteEventStore(path)
    except Exception as error:
        results.put(f"reopen_failed:{type(error).__name__}")
    else:
        results.put(f"reopened:{store.current_graph_version('run-1')}")
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

    def test_connection_uri_preserves_reserved_characters_in_path(self):
        path = Path(self.temporary.name) / "events #+%?.db"
        with SqliteEventStore(path) as store:
            self.assertEqual(
                CreateRunStatus.CREATED,
                store.create_run("run-1", RunMetadata.from_value({"source": "uri-test"})).status,
            )
        with SqliteEventStore(path) as reopened:
            self.assertEqual(0, reopened.current_graph_version("run-1"))

    def test_forked_provider_error_explains_supported_child_lifecycle(self):
        store = self.open_store()
        with patch.object(store, "_owner_pid", os.getpid() + 1):
            with self.assertRaisesRegex(ForkedProviderError, "process-bound.*spawn"):
                store.current_graph_version("run-1")
        store.close()

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
        self.assertEqual(context, recovered.c_run_recovery_context)
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
        original = self.path.with_name("original.db")
        os.replace(self.path, original)
        connection = sqlite3.connect(replacement)
        connection.close()
        os.replace(replacement, self.path)
        with self.assertRaises(StoreIdentityChangedError):
            store.current_graph_version("run-1")
        with self.assertRaises(StoreInUseError):
            SqliteEventStore(self.path)
        os.replace(original, self.path)
        with self.assertRaises(StoreClosedError):
            store.current_graph_version("run-1")
        store.close()

        store = SqliteEventStore(self.path)
        lock_path = self.path.with_name(f".{self.path.name}.problemforger.lock")
        lock_replacement = lock_path.with_suffix(".replacement")
        original_lock = lock_path.with_suffix(".original")
        os.replace(lock_path, original_lock)
        lock_replacement.write_text("replacement", encoding="utf-8")
        os.replace(lock_replacement, lock_path)
        with self.assertRaises(StoreIdentityChangedError):
            store.current_graph_version("run-1")
        os.replace(original_lock, lock_path)
        with self.assertRaises(StoreClosedError):
            store.current_graph_version("run-1")
        store.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_construction_rejects_replaced_path_before_mutating_replacement(self):
        replacement = self.path.with_name("replacement.db")
        original = self.path.with_name("original.db")
        replacement_connection = sqlite3.connect(replacement)
        self.assertEqual(
            "wal",
            replacement_connection.execute("PRAGMA journal_mode=WAL").fetchone()[0],
        )
        replacement_connection.close()

        real_connect = sqlite3.connect
        replaced = False

        def replace_before_connect(database, *args, **kwargs):
            nonlocal replaced
            os.replace(self.path, original)
            os.replace(replacement, self.path)
            replaced = True
            return real_connect(database, *args, **kwargs)

        try:
            with patch(
                "problemforger.modules.persistence.sqlite.sqlite3.connect",
                side_effect=replace_before_connect,
            ):
                with self.assertRaises(StoreIdentityChangedError):
                    self.open_store()
            self.assertTrue(replaced)
            connection = real_connect(self.path)
            try:
                self.assertEqual("wal", connection.execute("PRAGMA journal_mode").fetchone()[0])
                user_objects = {
                    (row[0], row[1])
                    for row in connection.execute(
                        "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
                    )
                }
                self.assertEqual(set(), user_objects)
            finally:
                connection.close()
        finally:
            if replaced and original.exists():
                if self.path.exists():
                    os.replace(self.path, replacement)
                os.replace(original, self.path)

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_construction_does_not_recreate_path_unlinked_before_connect(self):
        real_connect = sqlite3.connect

        def unlink_before_connect(database, *args, **kwargs):
            self.path.unlink()
            return real_connect(database, *args, **kwargs)

        with patch(
            "problemforger.modules.persistence.sqlite.sqlite3.connect",
            side_effect=unlink_before_connect,
        ):
            with self.assertRaises((sqlite3.OperationalError, StoreIdentityChangedError)):
                self.open_store()
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_construction_rechecks_identity_after_loading_state(self):
        original_load_state = SqliteEventStore._load_state
        captured_providers = []

        def load_then_unlink_lock(provider):
            runs = original_load_state(provider)
            captured_providers.append(provider)
            provider._lock_path.unlink()
            return runs

        try:
            with patch.object(SqliteEventStore, "_load_state", new=load_then_unlink_lock):
                with self.assertRaises(StoreIdentityChangedError):
                    SqliteEventStore(self.path)
        finally:
            for provider in captured_providers:
                provider.close()

        self.assertEqual(1, len(captured_providers))
        failed_provider = captured_providers[0]
        self.assertTrue(failed_provider._closed)
        self.assertTrue(failed_provider._poisoned)
        self.assertIsNone(failed_provider._connection)
        self.assertIsNone(failed_provider._owner_fd)
        self.assertIsNone(failed_provider._path_lock_fd)

        with self.open_store():
            pass

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_write_time_identity_failures_poison_even_if_lock_is_restored(self):
        for failing_check in (2, 3):
            with self.subTest(failing_check=failing_check):
                path = Path(self.temporary.name) / f"write-identity-{failing_check}.db"
                lock_path = path.with_name(f".{path.name}.problemforger.lock")
                store = SqliteEventStore(path)
                self._create_run(store)
                next_run_metadata = RunMetadata.from_value({"source": "identity-test"})
                original_verify = store._verify_identity
                check_count = 0

                def replace_lock_during_check():
                    nonlocal check_count
                    check_count += 1
                    if check_count != failing_check:
                        return original_verify()
                    backup = lock_path.with_suffix(".during-check")
                    os.replace(lock_path, backup)
                    try:
                        original_verify()
                    finally:
                        os.replace(backup, lock_path)

                with patch.object(store, "_verify_identity", new=replace_lock_during_check):
                    try:
                        with self.assertRaises(StoreIdentityChangedError):
                            store.create_run("write-after-replacement", next_run_metadata)
                        with self.assertRaises(StoreClosedError):
                            store.get_run("run-1")
                        with self.assertRaises(StoreClosedError):
                            store.create_run("write-after-replacement", next_run_metadata)
                    finally:
                        store.close()
                reopened = SqliteEventStore(path)
                self.assertEqual(
                    StoreErrorCode.NOT_FOUND,
                    reopened.get_run("write-after-replacement").code,
                )
                reopened.close()

    @unittest.skipUnless(LINUX, "SQLite owner uses Linux flock")
    def test_competing_process_opens_have_exactly_one_owner(self):
        context = multiprocessing.get_context("spawn")
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
    def test_spawned_child_reopens_after_current_owner_closes(self):
        store = self.open_store()
        self._create_run(store)
        context = multiprocessing.get_context("spawn")
        results = context.Queue()
        release = context.Event()
        child = context.Process(
            target=_spawned_open_after_owner_closes,
            args=(str(self.path), release, results),
        )
        child.start()
        try:
            self.assertEqual("owner_still_active", results.get(timeout=10))
        finally:
            store.close()
            release.set()
        self.assertEqual("reopened:0", results.get(timeout=10))
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
        invalid_timeouts = (
            ("millisecond_overflow", 2_147_483.648),
            ("large_seconds", 2_147_484),
            ("large_float", 1e20),
            ("huge_positive_integer", 10**1000),
            ("huge_negative_integer", -(10**1000)),
        )
        for name, timeout in invalid_timeouts:
            with self.subTest(timeout=name), self.assertRaises(ValueError):
                SqliteEventStore(self.path, timeout_seconds=timeout)
        self.assertFalse(self.path.exists())
        self.assertFalse(
            self.path.with_name(f".{self.path.name}.problemforger.lock").exists()
        )
        with SqliteEventStore(self.path, timeout_seconds=2_147_483.647) as store:
            busy_timeout_ms = store._connection.execute(
                "PRAGMA busy_timeout"
            ).fetchone()[0]
            self.assertEqual(2_147_483_647, busy_timeout_ms)
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
        for filesystem in ("fuse", "fuseblk", "fuse.sshfs"):
            with self.subTest(filesystem=filesystem):
                mount = f"31 22 0:44 / {mount_point} rw,relatime - {filesystem} source rw\n"
                with patch("pathlib.Path.read_text", return_value=mount):
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
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = 'journal_reject_update'"
        ).fetchone()[0]
        connection.execute("DROP TRIGGER journal_reject_update")
        connection.execute("UPDATE journal SET record_json = '{}' WHERE journal_position = 1")
        connection.execute(trigger_sql)
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

    def test_incomplete_schema_is_rejected_without_repair_or_journal_mode_change(self):
        schema_damage = {
            "runs": ("DROP TABLE runs",),
            "journal": ("DROP TABLE journal",),
            "both_tables": ("DROP TABLE journal", "DROP TABLE runs"),
            "update_trigger": ("DROP TRIGGER journal_reject_update",),
            "delete_trigger": ("DROP TRIGGER journal_reject_delete",),
            "mismatched_update_trigger": (
                "DROP TRIGGER journal_reject_update",
                "CREATE TRIGGER journal_reject_update BEFORE UPDATE ON journal BEGIN SELECT 1; END",
            ),
        }
        for corruption, statements in schema_damage.items():
            with self.subTest(corruption=corruption):
                path = Path(self.temporary.name) / f"incomplete-{corruption}.db"
                store = SqliteEventStore(path)
                store.create_run("run-1", RunMetadata.from_value({"source": "schema-test"}))
                self._submit(store, f"schema-{corruption}")
                store.close()

                connection = sqlite3.connect(path)
                self.assertEqual("wal", connection.execute("PRAGMA journal_mode=WAL").fetchone()[0])
                for statement in statements:
                    connection.execute(statement)
                connection.commit()
                before = connection.execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                ).fetchall()
                connection.close()

                with self.assertRaises(UnsupportedStoreError):
                    SqliteEventStore(path)

                connection = sqlite3.connect(path)
                self.assertEqual("wal", connection.execute("PRAGMA journal_mode").fetchone()[0])
                after = connection.execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                ).fetchall()
                connection.close()
                self.assertEqual(before, after)

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
