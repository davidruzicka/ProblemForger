"""Check P2 graph shapes with the existing finite-schema interpreter."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from problemforger.application import protocol
from scripts.generate_protocol_contract import check_schema


ROOT = Path(__file__).resolve().parents[1]


class GraphContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / 'contracts/graph-v1.json').read_text())
        cls.fixtures = json.loads((ROOT / 'tests/fixtures/graph-v1.json').read_text())

    def validate(self, value, definition):
        # Reuse the protocol schema subset; do not introduce another validator.
        with patch.object(protocol, 'CONTRACT', self.contract):
            protocol._json_tree(value, definition)
            protocol._validate_shape(value, definition, definition)

    def test_shapes_and_negative_vectors(self):
        for case in self.fixtures['shapes']:
            with self.subTest(case=case['name']):
                if case['valid']:
                    self.validate(case['value'], case['definition'])
                else:
                    with self.assertRaises(protocol.ProtocolValidationError):
                        self.validate(case['value'], case['definition'])

    def test_closed_operations_and_matching_events(self):
        operations = self.contract['x-operations']
        examples = {case['value']['op']: case['value'] for case in self.fixtures['shapes']
                    if case['definition'] == 'Operation' and case['valid']}
        self.assertEqual(set(operations), set(examples))
        for name, entry in operations.items():
            operation = examples[name]
            definition = self.contract['$defs'][entry['operation']]
            for field in definition['required']:
                invalid = deepcopy(operation)
                del invalid[field]
                with self.subTest(op=name, missing=field):
                    with self.assertRaises(protocol.ProtocolValidationError):
                        self.validate(invalid, 'Operation')
            for field, value in [('unknown', None), ('graph_schema_version', 2)]:
                with self.assertRaises(protocol.ProtocolValidationError):
                    self.validate({**operation, field: value}, 'Operation')
            payload = {key: value for key, value in operation.items()
                       if key not in {'op', 'graph_schema_version'}}
            event = {'event_type': entry['event_type'], 'event_schema_version': 1,
                     'payload': payload}
            self.validate(event, 'Event')
            for field, value in [('event_type', 'unknown'), ('event_schema_version', 2),
                                 ('payload', {**payload, 'unknown': None})]:
                with self.assertRaises(protocol.ProtocolValidationError):
                    self.validate({**event, field: value}, 'Event')

    def test_contract_uses_existing_schema_subset_and_identifier_rules(self):
        for rule in self.contract['$defs'].values():
            check_schema(rule, self.contract['$defs'])
        wire = json.loads((ROOT / 'contracts/protocol-v1.json').read_text())
        for name in ('Identifier', 'SafeInteger', 'PositiveInteger'):
            self.assertEqual(self.contract['$defs'][name], wire['$defs'][name])
        self.assertEqual(self.contract['x-graph-schema-version'], 1)

    def test_lifecycle_table_and_scenarios_cover_every_transition(self):
        transitions = self.contract['x-lifecycle-transitions']
        self.assertEqual(transitions, {'active': ['superseded', 'invalidated'],
                                      'superseded': [], 'invalidated': []})
        states = set(transitions)
        cases = self.fixtures['transitions']
        self.assertEqual({(case['from'], case['to']) for case in cases},
                         {(source, target) for source in states for target in states})
        for case in cases:
            self.assertEqual(case['valid'], case['to'] in transitions[case['from']])


if __name__ == '__main__':
    unittest.main()
