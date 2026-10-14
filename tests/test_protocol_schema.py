"""Conformance matrices from the finite contract, shared by both codecs."""

from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import get_args, get_type_hints, get_origin, NotRequired
import unittest
from unittest.mock import patch

from problemforger.application import protocol
from problemforger.core.journal import GovernanceOutcome, MutationDecision, ProposalStatus, RecordMetadata
from scripts import generate_protocol_contract as generator


ROOT = Path(__file__).resolve().parents[1]


def closed_objects(value, schema, definitions, path=()):
    if "$ref" in schema:
        schema = definitions[schema["$ref"].removeprefix("#/$defs/")]
    if "properties" not in schema:
        for part in schema.get("allOf", []):
            if "$ref" in part:
                yield from closed_objects(value, part, definitions, path)
        return
    if schema.get("additionalProperties") is False:
        yield path, schema["required"]
    for field, rule in schema["properties"].items():
        if field not in value:
            continue
        if rule.get("type") == "array":
            for index, item in enumerate(value[field]):
                yield from closed_objects(item, rule["items"], definitions, (*path, field, index))
        elif isinstance(value[field], dict):
            yield from closed_objects(value[field], rule, definitions, (*path, field))


def accepts_field(rule, value):
    if rule == "null":
        return value is None
    if rule == "identifier":
        return value == "reason"
    if rule == "nullable_identifier":
        return value is None or value == "reason"
    return type(value) is int and value >= 0


class ProtocolSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "contracts/protocol-v1.json").read_text())
        fixture = json.loads((ROOT / "tests/fixtures/protocol-v1.json").read_text())
        cls.requests = {item["label"]: item["message"] for item in fixture["requests"]}
        cls.responses = {item["label"]: item["message"] for item in fixture["responses"]}
        cls.cases = []
        definitions = cls.contract["$defs"]
        for kind, messages in (("request", cls.requests), ("response", cls.responses)):
            for label, message in messages.items():
                operation = message.get("operation")
                roots = [("Request" if kind == "request" else "ErrorResponse" if "error" in message else "SuccessResponse", ())]
                if operation:
                    entry = cls.contract["x-operations"][operation]
                    roots.append((entry["params" if kind == "request" else "result"], ("params" if kind == "request" else "result",)))
                context = next((r for r in cls.requests.values() if r["request_id"] == message.get("request_id")), None) if kind == "response" else None
                cls.cases.append({"label": f"valid {label}", "kind": kind, "message": message, "request": context, "valid": True})
                for schema_name, root_path in roots:
                    value = message
                    for field in root_path:
                        value = value[field]
                    for path, required in closed_objects(value, definitions[schema_name], definitions, root_path):
                        for field in (*required, "unknown_field"):
                            invalid = deepcopy(message)
                            parent = invalid
                            for part in path:
                                parent = parent[part]
                            if field == "unknown_field":
                                parent[field] = None
                            else:
                                del parent[field]
                            cls.cases.append({"label": f"{label} {path} {field}", "kind": kind, "message": invalid, "valid": False})
        for status, rule in cls.contract["x-proposal-states"].items():
            for reason in (None, "reason", ""):
                for version in (None, 0, 1, False, -1, 1.5):
                    message = deepcopy(cls.responses["get_proposal_commit"])
                    message["result"].update(status=status, reason_code=reason, resulting_graph_version=version, journal_position=10)
                    cls.cases.append({"label": f"{status} reason={reason!r} version={version!r}", "kind": "response", "message": message,
                                      "valid": accepts_field(rule["reason_code"], reason) and accepts_field(rule["resulting_graph_version"], version)})
        for code, mode in cls.contract["x-errors"].items():
            for identifier in (None, "reason", ""):
                message = {"protocol_schema_version": 1, "request_id": identifier, "error": {"code": code, "message": "error"}}
                cls.cases.append({"label": f"{code} request_id={identifier!r}", "kind": "response", "message": message, "valid": accepts_field(mode, identifier)})
        proposal_request = deepcopy(cls.requests["propose_mutation"])
        proposal_request["params"]["expected_graph_version"] = 2
        for outcome in GovernanceOutcome:
            for version in (1, 2, 3, 4):
                message = deepcopy(cls.responses["get_proposal_commit"])
                message.update(operation="propose_mutation", request_id=proposal_request["request_id"])
                result = message["result"]
                reason = None if outcome is GovernanceOutcome.COMMIT else "reason"
                result.update(status=outcome.value, resulting_graph_version=version, reason_code=reason, journal_position=10)
                try:
                    MutationDecision(
                        metadata=RecordMetadata(result["run_id"], "decision", datetime(2026, 10, 14, tzinfo=timezone.utc)),
                        proposal_id=result["proposal_id"], request_hash=result["request_hash"],
                        expected_graph_version=2, resulting_graph_version=version,
                        outcome=outcome, reason_code=reason,
                    )
                except ValueError:
                    valid = False
                else:
                    valid = True
                cls.cases.append({"label": f"domain {outcome.value} expected=2 resulting={version}", "kind": "response", "message": message, "request": proposal_request, "valid": valid})
        for operation in ("create_run", "get_run"):
            for created in (False, True):
                for version in (0, 1):
                    for position in (0, 1):
                        message = deepcopy(cls.responses[operation])
                        message["result"].update(created=created, graph_version=version, last_journal_position=position)
                        valid = version <= position and (not created or version == position == 0) and (operation != "get_run" or not created)
                        cls.cases.append({"label": f"{operation} created={created} version={version} position={position}", "kind": "response", "message": message, "request": cls.requests[operation], "valid": valid})
        for identifier, valid in (("\u001c", False), ("\ufeff", False), ("\u001c\ufeff ", False), ("\u001ca", True), ("a\ufeff", True)):
            message = deepcopy(cls.requests["get_run"])
            message["request_id"] = identifier
            cls.cases.append({"label": f"identifier {identifier!r}", "kind": "request", "message": message, "valid": valid})
        for label in ("get_proposal_commit", "get_audit_timeline"):
            message = deepcopy(cls.responses[label])
            if label == "get_proposal_commit":
                message["result"].update(resulting_graph_version=99, journal_position=1)
            else:
                message["result"]["records"][0]["graph_version"] = 99
            cls.cases.append({"label": f"{label} impossible version", "kind": "response", "message": message, "valid": False})

    def test_both_codecs_conform_to_the_same_complete_matrix(self):
        for case in self.cases:
            with self.subTest(label=case["label"]):
                message = case["message"]
                request = case.get("request")
                encode = lambda: protocol.encode_request(message) if case["kind"] == "request" else protocol.encode_response(message, request)
                decode = lambda: protocol.decode_request(json.dumps(message)) if case["kind"] == "request" else protocol.decode_response(json.dumps(message), request)
                if case["valid"]:
                    encode()
                    self.assertEqual(message, decode())
                else:
                    with self.assertRaises(protocol.ProtocolValidationError):
                        encode()
                    with self.assertRaises(protocol.ProtocolValidationError):
                        decode()
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "cases.json"
            path.write_text(json.dumps(self.cases))
            node = shutil.which("node")
            self.assertIsNotNone(node)
            result = subprocess.run([node, "--experimental-strip-types", str(ROOT / "tests/check_protocol_schema.mjs"), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_contract_states_match_domain_enums_and_static_python_types(self):
        states = self.contract["x-proposal-states"]
        self.assertEqual(set(states), {s.value for s in GovernanceOutcome} | {s.value for s in ProposalStatus})
        self.assertEqual({s for s, rule in states.items() if rule["kind"] == "governance"}, {s.value for s in GovernanceOutcome})
        self.assertEqual({s for s, rule in states.items() if rule["kind"] == "lifecycle"}, {s.value for s in ProposalStatus})
        self.assertEqual(set(states), set(get_args(get_type_hints(protocol.ProposalResult)["status"])))
        self.assertEqual(set(self.contract["x-operations"]), set(get_args(protocol.Operation)))
        for name in ("RunMetadata", "CreateRunParams", "GetRunParams", "GetGraphParams", "ProposeMutationParams", "GetProposalParams", "GetAuditTimelineParams", "RunResult", "GraphResult", "ProposalResult", "AuditTimelineResult", "PublicAuditRecord", "ProtocolError"):
            fields = get_type_hints(getattr(protocol, name), include_extras=True)
            schema = self.contract["$defs"][{"PublicAuditRecord": "AuditRecord", "ProtocolError": "Error"}.get(name, name)]
            self.assertEqual(set(fields), set(schema["properties"]), name)
            self.assertEqual({field for field, annotation in fields.items() if get_origin(annotation) is not NotRequired}, set(schema["required"]), name)
        self.assertEqual(protocol.CURRENT_PROTOCOL_SCHEMA_VERSION, self.contract["x-contract-version"])
        self.assertEqual(protocol.CURRENT_REQUEST_SCHEMA_VERSION, self.contract["$defs"]["RequestVersion"]["const"])

    def test_generated_contracts_are_current_and_stale_copies_fail(self):
        generator.generate(check=True)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "contracts").mkdir()
            shutil.copyfile(ROOT / "contracts/protocol-v1.json", root / "contracts/protocol-v1.json")
            with self.assertRaisesRegex(ValueError, "stale"):
                generator.generate(root, check=True)
            generator.generate(root)
            generator.generate(root, check=True)
            target = root / "clients/typescript/protocol_contract.ts"
            target.write_text("stale")
            with self.assertRaisesRegex(ValueError, "stale"):
                generator.generate(root, check=True)
        with patch.object(sys, "argv", ["generate_protocol_contract", "--check"]):
            self.assertEqual(generator.main(), 0)
            with patch.object(generator, "generate", side_effect=ValueError("stale")), patch.object(sys, "stderr", StringIO()):
                self.assertEqual(generator.main(), 1)

    def test_generation_rejects_unsupported_rules_and_missing_references(self):
        definitions = self.contract["$defs"]
        with self.assertRaisesRegex(ValueError, "unsupported"):
            generator.check_schema({"format": "email"}, definitions)
        with self.assertRaisesRegex(ValueError, "unknown"):
            generator.check_schema({"$ref": "#/$defs/Missing"}, definitions)


if __name__ == "__main__":
    unittest.main()
