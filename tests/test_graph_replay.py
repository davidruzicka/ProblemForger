"""Replay real journals through both EventStore providers."""

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from problemforger.application.graph import GraphReplayError, replay_graph
from problemforger.application._graph_contract import CONTRACT
from problemforger.core.journal import (
    GovernanceOutcome, GraphChangedEvent, JsonDocument, MutationDecision,
    NonTerminalAuditRecord, NormalizedMutationRequest, ProposalReceipt, RecordMetadata, VersionConflict,
)
from problemforger.modules.persistence.memory import MemoryEventStore
from problemforger.modules.persistence.sqlite import SqliteEventStore
from problemforger.ports.event_store import JournalPage, RunMetadata, StoreError, StoreErrorCode


NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)
ROOT = {'node_id': 'root', 'kind': 'RootGoal', 'label': 'Goal', 'protected': True}
TASK = {'node_id': 'task', 'kind': 'Task', 'label': 'Work', 'protected': False}
EDGE = {'edge_id': 'origin', 'kind': 'derived_from', 'source_id': 'task', 'target_id': 'root'}
INITIAL = [('node_created', {'node': ROOT}), ('node_created', {'node': TASK}),
           ('edge_created', {'edge': EDGE})]
EVIDENCE = {'evidence_id': 'check', 'content_digest': 'sha256:' + 'a' * 64}


def commit(store, events, *, run_id='run', proposal_id='p1'):
    version = store.current_graph_version(run_id)
    def metadata(suffix):
        return RecordMetadata(run_id=run_id, record_id=f'{proposal_id}-{suffix}', recorded_at=NOW)
    operations = {rule['event_type']: name for name, rule in CONTRACT['x-operations'].items()}
    request = NormalizedMutationRequest(1, version, tuple(
        JsonDocument.from_value({'graph_schema_version': 1, 'op': operations.get(kind, 'unknown'), **payload})
        for kind, payload in events), ())
    receipt = ProposalReceipt(metadata('receipt'), proposal_id, request)
    store.record_proposal(run_id, proposal_id, receipt.request_hash, request, receipt)
    decision = MutationDecision(metadata('decision'), proposal_id, receipt.request_hash,
                                version, version + 1, GovernanceOutcome.COMMIT)
    batch = tuple(GraphChangedEvent(metadata(str(i)), proposal_id, version + 1, kind, 1,
                                    JsonDocument.from_value(payload))
                  for i, (kind, payload) in enumerate(events))
    result = store.append_graph(run_id, proposal_id, version, (decision,), batch)
    if isinstance(result, (StoreError, VersionConflict)):
        raise AssertionError(result)


class GraphReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    def providers(self):
        for store in (MemoryEventStore(), SqliteEventStore(Path(self.temporary.name) / 'journal.db')):
            try:
                store.create_run('run', RunMetadata.from_value({}))
                yield store
            finally:
                store.close()

    def test_empty_and_multievent_batch_across_every_page_boundary(self):
        expected = None
        for store in self.providers():
            self.assertEqual(replay_graph(store, 'run').to_value()['nodes'], [])
            commit(store, INITIAL)
            values = [replay_graph(store, 'run', page_size=n).to_value() for n in (1, 2, 3, 100)]
            self.assertTrue(all(value == values[0] for value in values))
            value = values[0]
            self.assertEqual(value['graph_version'], 1)
            self.assertEqual(value['nodes'][0]['created_by'], {
                'proposal_id': 'p1', 'record_id': 'p1-0', 'journal_position': 3, 'graph_version': 1})
            if expected is not None:
                self.assertEqual(value, expected)
            expected = value
            frozen = replay_graph(store, 'run')
            detached = frozen.to_value()
            detached['nodes'][0]['label'] = 'changed'
            self.assertEqual(frozen.to_value(), value)

    def test_lifecycle_evidence_audit_and_run_isolation_survive_restart(self):
        for store in self.providers():
            commit(store, INITIAL)
            changes = [('evidence_attached', {'entity_kind': 'node', 'entity_id': 'task', 'evidence': EVIDENCE}),
                       ('evidence_attached', {'entity_kind': 'edge', 'entity_id': 'origin', 'evidence': EVIDENCE}),
                       ('lifecycle_changed', {'entity_kind': 'node', 'entity_id': 'task', 'lifecycle': 'superseded', 'reason': 'Replaced'}),
                       ('lifecycle_changed', {'entity_kind': 'edge', 'entity_id': 'origin', 'lifecycle': 'invalidated', 'reason': 'Historical'})]
            commit(store, changes, proposal_id='p2')
            projection = replay_graph(store, 'run').to_value()
            self.assertEqual(projection['nodes'][1]['evidence_refs'], [EVIDENCE])
            self.assertEqual(projection['nodes'][1]['lifecycle'], 'superseded')
            self.assertEqual(projection['edges'][0]['lifecycle'], 'invalidated')
            audit = NonTerminalAuditRecord(RecordMetadata('run', 'audit', NOW), 'observation', JsonDocument.from_value({'ignore': True}))
            store.append_audit('run', (audit,))
            self.assertEqual(replay_graph(store, 'run').to_value(), projection)
            store.create_run('other', RunMetadata.from_value({}))
            self.assertEqual(replay_graph(store, 'other').to_value()['nodes'], [])
            if isinstance(store, SqliteEventStore):
                store.close()
                with SqliteEventStore(Path(self.temporary.name) / 'journal.db') as reopened:
                    self.assertEqual(replay_graph(reopened, 'run', page_size=1).to_value(), projection)

    def test_all_noncommit_outcomes_leave_graph_state_unchanged(self):
        for store in self.providers():
            commit(store, INITIAL)
            expected = replay_graph(store, 'run')
            for outcome in (GovernanceOutcome.REJECT, GovernanceOutcome.RETRY,
                            GovernanceOutcome.ESCALATE, GovernanceOutcome.CONFLICT):
                proposal_id = outcome.value
                version = 2 if outcome is GovernanceOutcome.CONFLICT else 1
                request = NormalizedMutationRequest(1, version, (), ())
                receipt = ProposalReceipt(RecordMetadata('run', proposal_id + '-receipt', NOW), proposal_id, request)
                store.record_proposal('run', proposal_id, receipt.request_hash, request, receipt)
                decision = MutationDecision(RecordMetadata('run', proposal_id + '-decision', NOW),
                                           proposal_id, receipt.request_hash, version, 1, outcome, 'test')
                self.assertNotIsInstance(store.append_audit('run', (decision,), proposal_id), StoreError)
            self.assertEqual(replay_graph(store, 'run'), expected)


    def test_invalid_committed_batches_fail_without_returning_partial_state(self):
        changes = [
            [('node_created', {'node': TASK})],  # reused ID
            [('node_created', {'node': {**TASK, 'node_id': 'orphan'}})],
            [('node_created', {'node': {**ROOT, 'node_id': 'second-root'}})],
            [('edge_created', {'edge': {**EDGE, 'edge_id': 'bad', 'target_id': 'missing'}})],
            [('lifecycle_changed', {'entity_kind': 'node', 'entity_id': 'missing', 'lifecycle': 'invalidated', 'reason': 'x'})],
            [('evidence_attached', {'entity_kind': 'node', 'entity_id': 'task', 'evidence': EVIDENCE})] * 2,
            [('lifecycle_changed', {'entity_kind': 'node', 'entity_id': 'task', 'lifecycle': state, 'reason': 'x'})
             for state in ('invalidated', 'superseded')],
            [('lifecycle_changed', {'entity_kind': 'node', 'entity_id': 'task', 'lifecycle': 'invalidated', 'reason': 'x'}),
             ('evidence_attached', {'entity_kind': 'node', 'entity_id': 'task', 'evidence': EVIDENCE})],
            [('lifecycle_changed', {'entity_kind': 'node', 'entity_id': 'task', 'lifecycle': 'invalidated', 'reason': 'x'}),
             ('edge_created', {'edge': {**EDGE, 'edge_id': 'late'}})],
            [('node_created', {'node': {**TASK, 'unknown': True}})],
            [('node_created', {'node': {**ROOT, 'node_id': 'bad', 'protected': False}})],
            [('unknown', {})],
        ]
        for i, events in enumerate(changes):
            with self.subTest(case=i):
                for provider in (MemoryEventStore(), SqliteEventStore(Path(self.temporary.name) / f'invalid-{i}.db')):
                    with closing(provider) as store:
                        store.create_run('run', RunMetadata.from_value({}))
                        commit(store, INITIAL)
                        before = replay_graph(store, 'run')
                        commit(store, events, proposal_id='p2')
                        with self.assertRaises(GraphReplayError):
                            replay_graph(store, 'run', page_size=1)
                        self.assertEqual(before.to_value()['graph_version'], 1)

    def test_forward_references_fail_but_cycles_with_root_provenance_are_valid(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            commit(store, [INITIAL[2], *INITIAL[:2]])
            with self.assertRaises(GraphReplayError):
                replay_graph(store, 'run')
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            commit(store, [*INITIAL, ('edge_created', {'edge': {**EDGE, 'edge_id': 'self', 'target_id': 'task'}}),
                           ('edge_created', {'edge': {**EDGE, 'edge_id': 'dependency', 'kind': 'depends_on'}})])
            self.assertEqual(len(replay_graph(store, 'run').to_value()['edges']), 3)

    def test_replay_excludes_appends_after_captured_boundary(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            commit(store, INITIAL)
            original = store.read_journal
            before = replay_graph(store, 'run').to_value()
            def append_during_read(*args, **kwargs):
                commit(store, [('lifecycle_changed', {'entity_kind': 'node', 'entity_id': 'task',
                       'lifecycle': 'invalidated', 'reason': 'Later append'})], proposal_id='p2')
                return original(*args, **kwargs)
            with patch.object(store, 'read_journal', side_effect=append_during_read):
                self.assertEqual(replay_graph(store, 'run').to_value(), before)
            self.assertEqual(replay_graph(store, 'run').graph_version, 2)

    def test_corrupt_versions_and_batch_boundaries_fail_closed(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            commit(store, INITIAL)
            page = store.read_journal('run', limit=100)
            snapshot = store.get_run('run')
            for snapshot_change in ({'run_id': 'other'}, {'graph_version': 2}):
                with patch.object(store, 'get_run', return_value=replace(snapshot, **snapshot_change)):
                    with self.assertRaises(GraphReplayError):
                        replay_graph(store, 'run')
            first_event = replace(page.records[2], record=replace(page.records[2].record, graph_version=2))
            with patch.object(store, 'read_journal', return_value=replace(page, records=(*page.records[:2], first_event, *page.records[3:]))):
                with self.assertRaises(GraphReplayError):
                    replay_graph(store, 'run')
            for change in ({'graph_version': 2}, {'proposal_id': 'other'}):
                bad = replace(page.records[-1], record=replace(page.records[-1].record, **change))
                with patch.object(store, 'read_journal', return_value=replace(page, records=(*page.records[:-1], bad))):
                    with self.assertRaises(GraphReplayError):
                        replay_graph(store, 'run')
            bad = replace(page.records[-1].record)
            object.__setattr__(bad, 'event_schema_version', 2)  # Model an unsupported port result.
            with patch.object(store, 'read_journal', return_value=replace(page, records=(*page.records[:-1], replace(page.records[-1], record=bad)))):
                with self.assertRaises(GraphReplayError):
                    replay_graph(store, 'run')


    def test_unavailable_truncated_or_cross_run_journal_is_not_a_projection(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            commit(store, INITIAL)
            for limit in (0, -1, True, 1.5):
                with self.assertRaises(GraphReplayError):
                    replay_graph(store, 'run', page_size=limit)
            with self.assertRaises(GraphReplayError):
                replay_graph(store, 'missing')
            for result in (StoreError(StoreErrorCode.NOT_FOUND), JournalPage((), 0, False)):
                with patch.object(store, 'read_journal', return_value=result):
                    with self.assertRaises(GraphReplayError):
                        replay_graph(store, 'run')
            page = store.read_journal('run', limit=100)
            for records in (page.records[:-1], page.records[1:]):
                with patch.object(store, 'read_journal', return_value=replace(page, records=records)):
                    with self.assertRaises(GraphReplayError):
                        replay_graph(store, 'run')
            bad = replace(page.records[-1].record, metadata=RecordMetadata('other', 'bad', NOW))
            with patch.object(store, 'read_journal', return_value=replace(page, records=(*page.records[:-1], replace(page.records[-1], record=bad)))):
                with self.assertRaises(GraphReplayError):
                    replay_graph(store, 'run')


if __name__ == '__main__':
    unittest.main()
