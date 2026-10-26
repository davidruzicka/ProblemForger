"""P2 graph integration against both EventStore providers."""

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from problemforger.application.service import ProtocolApplication
from problemforger.application.graph import GraphProjection, replay_graph
from problemforger.application.protocol import MAX_PROTOCOL_MESSAGE_BYTES, encode_request, encode_response
from problemforger.core.journal import CRunRecoveryContext, JsonDocument, NormalizedMutationRequest, ProposalReceipt, RecordMetadata
from problemforger.modules.persistence import MemoryEventStore, SqliteEventStore
from problemforger.modules.telemetry import NullTelemetrySink
from problemforger.ports.event_store import RunMetadata
from test_application_service import message, NOW
from test_graph_replay import commit, INITIAL, ROOT, EVIDENCE


def mutation(operations, *, proposal_id='change', version=1, run_id='run', evidence=None):
    return message('propose_mutation', {
        'run_id': run_id, 'proposal_id': proposal_id, 'request_schema_version': 1,
        'expected_graph_version': version, 'operations': operations, 'evidence': evidence or [],
    })


def operation(op, **fields):
    return {'graph_schema_version': 1, 'op': op, **fields}


ADD = [operation('create_node', node={'node_id': 'new', 'kind': 'Task', 'label': 'Next', 'protected': False}),
       operation('create_edge', edge={'edge_id': 'new-origin', 'kind': 'derived_from', 'source_id': 'new', 'target_id': 'root'})]


class GraphServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    def providers(self):
        for store in (MemoryEventStore(), SqliteEventStore(Path(self.temporary.name) / 'graph.db')):
            with closing(store):
                store.create_run('run', RunMetadata.from_value({}))
                commit(store, INITIAL)
                yield store, ProtocolApplication(store, NullTelemetrySink())

    def test_queries_paginate_real_entities_and_bind_cursor_to_view(self):
        for store, app in self.providers():
            params = {'run_id': 'run', 'limit': 1}
            seen = []
            while True:
                page = app.handle(message('get_graph', params))['result']
                seen.extend(page['nodes'] + page['edges'])
                if not page['has_more']:
                    break
                params['after_cursor'] = page['next_cursor']
            self.assertEqual([e.get('node_id', e.get('edge_id')) for e in seen], ['root', 'task', 'origin'])
            first = app.handle(message('get_graph', {'run_id': 'run', 'limit': 1}))['result']
            cursor = first['next_cursor']
            prefix = cursor.rsplit(':', 1)[0] + ':'
            for suffix in ('0', '01', '999', '1.0'):
                self.assertIn('error', app.handle(message('get_graph', {'run_id': 'run', 'limit': 1, 'after_cursor': prefix + suffix})))
            for selection in ({'unknown': True}, {'node_id': 'missing'}, {'node_id': 2}, {'node_id': ' '}):
                self.assertIn('error', app.handle(message('get_graph', {'run_id': 'run', 'limit': 2, 'selection': selection})))
            neighborhood = app.handle(message('get_graph', {'run_id': 'run', 'limit': 100, 'selection': {'node_id': 'task'}}))['result']
            self.assertEqual(len(neighborhood['nodes']) + len(neighborhood['edges']), 3)
            store.create_run('other', RunMetadata.from_value({}))
            for changes in ({'run_id': 'other'}, {'selection': {'node_id': 'task'}}, {'after_cursor': 'garbage'}):
                bad = {'run_id': 'run', 'limit': 1, 'after_cursor': cursor, **changes}
                self.assertIn('error', app.handle(message('get_graph', bad)))
            self.assertEqual(app.handle(mutation(ADD))['result']['status'], 'COMMIT')
            self.assertIn('error', app.handle(message('get_graph', {'run_id': 'run', 'limit': 1, 'after_cursor': cursor})))

    def test_commit_replay_conflict_and_public_redaction(self):
        for store, app in self.providers():
            request = mutation(ADD, evidence=[{'private': 'sentinel'}])
            result = app.handle(request)['result']
            self.assertEqual(result['status'], 'COMMIT')
            self.assertEqual(result['resulting_graph_version'], 2)
            self.assertEqual(app.handle(request)['result'], result)
            self.assertEqual(app.handle(message('get_proposal', {'run_id': 'run', 'proposal_id': 'change'}))['result'], result)
            public = app.handle(message('get_audit_timeline', {'run_id': 'run', 'limit': 100}))['result']
            self.assertNotIn('sentinel', str((public, result)))
            self.assertEqual(len(replay_graph(store, 'run').to_value()['nodes']), 3)
            self.assertEqual(app.handle(mutation(ADD, proposal_id='stale'))['result']['status'], 'CONFLICT')
            changed = mutation(ADD, version=2)
            self.assertEqual(app.handle(changed)['error']['code'], 'IDEMPOTENCY_CONFLICT')
            if isinstance(store, SqliteEventStore):
                store.close()
                with SqliteEventStore(Path(self.temporary.name) / 'graph.db') as reopened:
                    recovered = ProtocolApplication(reopened, NullTelemetrySink())
                    self.assertEqual(recovered.handle(request)['result'], result)
                    self.assertEqual(replay_graph(reopened, 'run').graph_version, 2)

    def test_invalid_or_protected_batches_leave_graph_unchanged(self):
        cases = [[], ADD[:1], [ADD[1], ADD[0]], [ADD[0], ADD[0]],
                 [operation('create_node', node={**ROOT, 'node_id': 'second'})],
                 [operation('change_lifecycle', entity_kind='node', entity_id='root', lifecycle='invalidated', reason='x')],
                 [operation('attach_evidence', entity_kind='node', entity_id='root', evidence=EVIDENCE)],
                 [operation('create_node', node={'node_id': 'protected', 'kind': 'Requirement', 'label': 'x', 'protected': True})],
                 [{'op': 'unknown'}]]
        for store, app in self.providers():
            before = replay_graph(store, 'run')
            for i, operations in enumerate(cases):
                result = app.handle(mutation(operations, proposal_id=f'invalid-{i}'))['result']
                self.assertEqual(result['status'], 'REJECT')
                self.assertEqual(replay_graph(store, 'run'), before)

    def test_lifecycle_and_evidence_remain_separate(self):
        for store, app in self.providers():
            operations = [operation('attach_evidence', entity_kind='node', entity_id='task', evidence=EVIDENCE),
                          operation('change_lifecycle', entity_kind='node', entity_id='task', lifecycle='superseded', reason='Replaced')]
            self.assertEqual(app.handle(mutation(operations))['result']['status'], 'COMMIT')
            task = replay_graph(store, 'run').to_value()['nodes'][1]
            self.assertEqual(task['lifecycle'], 'superseded')
            self.assertEqual(task['evidence_refs'], [EVIDENCE])
            self.assertEqual(app.handle(mutation(operations, version=2, proposal_id='repeat'))['result']['status'], 'REJECT')

    def test_authorization_precedes_every_store_access_including_create_retry(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({'private': 'sentinel'}))
            app = ProtocolApplication(store, NullTelemetrySink(), authorize_run=lambda operation, run_id: False)
            requests = [message('create_run', {'run_id': 'run', 'run_metadata': {'metadata_schema_version': 1, 'data': data}})
                        for data in ({'private': 'sentinel'}, {'different': True})]
            requests += [message('get_run', {'run_id': 'run'}), message('get_graph', {'run_id': 'run', 'limit': 1}),
                         message('get_proposal', {'run_id': 'run', 'proposal_id': 'x'}), mutation(ADD),
                         message('get_audit_timeline', {'run_id': 'run', 'limit': 1})]
            with patch.object(store, 'get_run', side_effect=AssertionError('unauthorized read')), patch.object(store, 'create_run', side_effect=AssertionError('unauthorized create')):
                for request in requests:
                    self.assertEqual(app.handle(request)['error']['code'], 'UNAUTHORIZED')

    def test_pending_structural_mutation_recovers_once(self):
        for store, app in self.providers():
            request = mutation(ADD)
            normalized = NormalizedMutationRequest(1, 1, tuple(JsonDocument.from_value(x) for x in ADD), ())
            receipt = ProposalReceipt(RecordMetadata('run', 'pending', NOW), 'change', normalized)
            store.record_proposal('run', 'change', receipt.request_hash, normalized, receipt)
            result = app.handle(request)['result']
            self.assertEqual(result['status'], 'COMMIT')
            self.assertEqual(app.handle(request)['result'], result)

    def test_trusted_bootstrap_is_idempotent_and_absent_from_worker_protocol(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            app = ProtocolApplication(store, NullTelemetrySink())
            result = app.bootstrap_root('run', 'setup-root', 'Goal')
            self.assertEqual(result['status'], 'COMMIT')
            self.assertEqual(app.bootstrap_root('run', 'setup-root', 'Goal'), result)
            with self.assertRaises(ValueError):
                app.bootstrap_root('run', 'different', 'Goal')
            with self.assertRaises(ValueError):
                app.bootstrap_root('run', 'setup-root', 'Changed')
            with self.assertRaises(ValueError):
                app.handle(message('bootstrap_root', {'run_id': 'run'}))

    def test_graph_append_conflict_is_durable_before_response(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            commit(store, INITIAL)
            app = ProtocolApplication(store, NullTelemetrySink())
            append = store.append_graph
            def advance_before_append(*args):
                with patch.object(store, 'append_graph', append):
                    commit(store, [('lifecycle_changed', {'entity_kind': 'node', 'entity_id': 'task', 'lifecycle': 'invalidated', 'reason': 'Changed'})], proposal_id='intervening')
                return append(*args)
            with patch.object(store, 'append_graph', side_effect=advance_before_append):
                result = app.handle(mutation(ADD))['result']
            self.assertEqual(result['status'], 'CONFLICT')
            self.assertEqual(result['resulting_graph_version'], 2)
            self.assertEqual(app.handle(mutation(ADD))['result'], result)

    def test_corrupt_graph_returns_explicit_error_without_partial_state(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            commit(store, [('unknown', {'private': 'sentinel'})])
            app = ProtocolApplication(store, NullTelemetrySink())
            result = app.handle(message('get_graph', {'run_id': 'run', 'limit': 1}))
            self.assertEqual(result['error']['code'], 'PROTOCOL_ERROR')
            self.assertNotIn('sentinel', str(result))

    def test_c_policy_is_not_fabricated_and_abandonment_precedes_stale_policy_conflict(self):
        for store, app in self.providers():
            # Model a stored receipt whose C runtime identity is no longer available.
            request = mutation(ADD, version=0)
            normalized = NormalizedMutationRequest(1, 0, tuple(JsonDocument.from_value(x) for x in ADD), ())
            context = CRunRecoveryContext('sha256:manifest', 'sha256:graph', 'sha256:policy')
            receipt = ProposalReceipt(RecordMetadata('run', 'c-pending', NOW), 'change', normalized, c_run_recovery_context=context)
            store.record_proposal('run', 'change', receipt.request_hash, normalized, receipt)
            result = app.handle(request)['result']
            self.assertEqual(result['status'], 'ABANDONED')
            self.assertEqual(result['reason_code'], 'c_run_identity_mismatch')
            self.assertEqual(app.handle(request)['result'], result)
            store.create_run('c-run', RunMetadata.from_value({'configuration': 'C',
                'manifest_hash': 'sha256:manifest', 'effective_graph_intervention_identity': 'sha256:graph',
                'effective_governance_policy_identity': 'sha256:policy'}))
            response = app.handle(mutation(ADD, run_id='c-run', version=0))['result']
            self.assertEqual(response['status'], 'REJECT')
            self.assertEqual(response['reason_code'], 'P1_GOVERNANCE_NOT_IMPLEMENTED')
            with self.assertRaises(ValueError):
                app.bootstrap_root('c-run', 'root', 'Goal')

    def test_graph_pages_fit_encoded_frame_and_keep_all_entities(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            app = ProtocolApplication(store, NullTelemetrySink())
            refs = [{'evidence_id': str(i) + 'x' * 240, 'content_digest': 'sha256:' + 'a' * 64} for i in range(2200)]
            nodes = [{'node_id': str(i), 'kind': 'Task', 'label': 'Work', 'protected': False,
                'lifecycle': 'active', 'evidence_refs': refs, 'created_by': {
                    'proposal_id': 'seed', 'record_id': str(i), 'journal_position': i + 3, 'graph_version': 1}}
                for i in range(4)]
            edges = [{'edge_id': str(i), 'kind': 'depends_on', 'source_id': '0', 'target_id': '1',
                'lifecycle': 'active', 'evidence_refs': refs, 'created_by': nodes[i]['created_by']}
                for i in range(3)]
            projection = GraphProjection('run', 1, JsonDocument.from_value({'nodes': nodes, 'edges': edges}))
            params = {'run_id': 'run', 'limit': 100}
            seen = []
            with patch('problemforger.application.service.replay_graph', return_value=projection):
                while True:
                    request = message('get_graph', params, 'é' * 128)
                    response = app.handle(request)
                    self.assertLessEqual(len(encode_response(response, request)), MAX_PROTOCOL_MESSAGE_BYTES)
                    page = response['result']
                    seen.extend(('node', node['node_id']) for node in page['nodes'])
                    seen.extend(('edge', edge['edge_id']) for edge in page['edges'])
                    if not page['has_more']:
                        break
                    self.assertTrue(page['nodes'] or page['edges'])
                    params['after_cursor'] = page['next_cursor']
            self.assertEqual(seen, [('node', str(i)) for i in range(4)] + [('edge', str(i)) for i in range(3)])

    def test_page_byte_boundary_includes_unicode_envelope_and_cursor(self):
        for store, app in self.providers():
            request = message('get_graph', {'run_id': 'run', 'limit': 1}, 'é' * 128)
            expected = app.handle(request)
            exact_size = len(encode_response(expected, request))
            request['params']['limit'] = 100
            with patch('problemforger.application.graph.MAX_PROTOCOL_MESSAGE_BYTES', exact_size):
                page = app.handle(request)
            self.assertEqual(page, expected)
            self.assertEqual(len(encode_response(page, request)), exact_size)
            with patch('problemforger.application.graph.MAX_PROTOCOL_MESSAGE_BYTES', exact_size - 1):
                self.assertEqual(app.handle(request)['error']['code'], 'PAYLOAD_TOO_LARGE')

    def test_legacy_oversized_entity_returns_an_encodable_error(self):
        with closing(MemoryEventStore()) as store:
            store.create_run('run', RunMetadata.from_value({}))
            projection = GraphProjection('run', 1, JsonDocument.from_value({
                'nodes': [{'node_id': 'legacy', 'evidence_refs': [{'private': 'x' * MAX_PROTOCOL_MESSAGE_BYTES}]}], 'edges': []}))
            app = ProtocolApplication(store, NullTelemetrySink())
            request = message('get_graph', {'run_id': 'run', 'limit': 1})
            with patch('problemforger.application.service.replay_graph', return_value=projection):
                response = app.handle(request)
            self.assertEqual(response['error']['code'], 'PAYLOAD_TOO_LARGE')
            self.assertLess(len(encode_response(response, request)), 1000)

    def test_evidence_growth_is_rejected_before_entity_becomes_unretrievable(self):
        for store, app in self.providers():
            before = replay_graph(store, 'run')
            refs = [operation('attach_evidence', entity_kind='node', entity_id='task',
                evidence={**EVIDENCE, 'evidence_id': str(i)}) for i in range(10)]
            candidate = before.to_value()['nodes'][1]
            candidate['evidence_refs'] = [refs[0]['evidence']]
            exact_size = len(json.dumps(candidate, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            with patch('problemforger.application.graph.MAX_GRAPH_ENTITY_BYTES', exact_size):
                accepted = app.handle(mutation(refs[:1], proposal_id='fits'))['result']
                self.assertEqual(accepted['status'], 'COMMIT')
                before = replay_graph(store, 'run')
                request = mutation(refs[1:], version=2)
                result = app.handle(request)['result']
            self.assertEqual(result['status'], 'REJECT')
            self.assertEqual(replay_graph(store, 'run'), before)
            self.assertEqual(app.handle(request)['result'], result)

    def test_expanded_batch_is_durably_rejected_and_replayed_after_restart(self):
        for store, app in self.providers():
            run_id = 'r' * 256
            store.create_run(run_id, RunMetadata.from_value({}))
            app.bootstrap_root(run_id, 'setup', 'Goal')
            operations = [operation('create_edge', edge={'edge_id': str(i), 'kind': 'depends_on',
                'source_id': 'root', 'target_id': 'root'}) for i in range(5000)]
            request = mutation(operations, run_id=run_id, proposal_id='p' * 256)
            request['request_id'] = 'q' * 256
            self.assertLess(len(encode_request(request)), 1_048_576)
            with patch.object(store, 'append_graph', wraps=store.append_graph) as append:
                result = app.handle(request)['result']
                self.assertEqual(result['status'], 'REJECT')
                self.assertEqual(result['reason_code'], 'graph_batch_too_large')
                append.assert_not_called()
            self.assertEqual(app.handle(request)['result'], result)
            self.assertEqual(store.current_graph_version(run_id), 1)
            if isinstance(store, SqliteEventStore):
                store.close()
                with SqliteEventStore(Path(self.temporary.name) / 'graph.db') as reopened:
                    self.assertEqual(ProtocolApplication(reopened, NullTelemetrySink()).handle(request)['result'], result)
