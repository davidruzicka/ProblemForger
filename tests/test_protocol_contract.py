from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from problemforger.application.protocol import (
    MAX_PROTOCOL_MESSAGE_BYTES,
    ProtocolValidationError,
    decode_request,
    decode_response,
    encode_request,
    encode_response,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "protocol-v1.json"


class ProtocolContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_python_round_trips_shared_v1_fixtures(self) -> None:
        for fixture in self.fixtures["requests"]:
            with self.subTest(label=fixture["label"]):
                encoded = encode_request(fixture["message"])
                self.assertEqual(decode_request(encoded), fixture["message"])

        for fixture in self.fixtures["responses"]:
            with self.subTest(label=fixture["label"]):
                encoded = encode_response(fixture["message"])
                self.assertEqual(decode_response(encoded), fixture["message"])

    def test_invalid_request_fixtures_are_rejected(self) -> None:
        for fixture in self.fixtures["invalid_requests"]:
            with self.subTest(label=fixture["label"]):
                with self.assertRaises(ProtocolValidationError):
                    encode_request(fixture["message"])

    def test_invalid_response_fixtures_are_rejected(self) -> None:
        for fixture in self.fixtures["invalid_responses"]:
            with self.subTest(label=fixture["label"]):
                with self.assertRaises(ProtocolValidationError):
                    encode_response(fixture["message"])

    def test_message_size_limit_applies_to_utf8_bytes(self) -> None:
        oversized = ("x" * MAX_PROTOCOL_MESSAGE_BYTES) + "é"
        with self.assertRaisesRegex(ProtocolValidationError, "4 MiB"):
            decode_request(oversized)

    def test_decoder_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        duplicate = b'{"protocol_schema_version":1,"protocol_schema_version":1}'
        non_finite = b'{"protocol_schema_version":1,"request_id":"r","operation":"get_run","params":{"run_id":"x","extra":NaN}}'
        for payload in (duplicate, non_finite):
            with self.subTest(payload=payload):
                with self.assertRaises(ProtocolValidationError):
                    decode_request(payload)

    def test_request_validators_reject_bad_metadata_paging_and_mutation_bounds(self) -> None:
        requests = [fixture["message"] for fixture in self.fixtures["requests"]]
        create_run = next(item for item in requests if item["operation"] == "create_run")
        get_graph = next(item for item in requests if item["operation"] == "get_graph")
        propose = next(item for item in requests if item["operation"] == "propose_mutation")
        audit = next(item for item in requests if item["operation"] == "get_audit_timeline")

        invalid = []
        value = deepcopy(create_run)
        value["params"]["run_metadata"]["metadata_schema_version"] = 2
        invalid.append(("metadata version", value))
        value = deepcopy(create_run)
        value["params"]["run_metadata"]["data"] = []
        invalid.append(("metadata data shape", value))
        value = deepcopy(create_run)
        value["params"]["run_metadata"]["data"] = {"large": "x" * (1024 * 1024)}
        invalid.append(("metadata size", value))
        value = deepcopy(get_graph)
        value["params"]["selection"] = []
        invalid.append(("selection shape", value))
        value = deepcopy(get_graph)
        value["params"]["after_cursor"] = " "
        invalid.append(("empty cursor", value))
        value = deepcopy(propose)
        value["params"]["request_schema_version"] = 2
        invalid.append(("request schema version", value))
        value = deepcopy(propose)
        value["params"]["operations"] = {}
        invalid.append(("operations shape", value))
        value = deepcopy(propose)
        value["params"]["evidence"] = [None]
        invalid.append(("evidence object shape", value))
        value = deepcopy(propose)
        value["params"]["operations"] = [{"payload": "x" * (1024 * 1024)}]
        invalid.append(("normalized request size", value))
        value = deepcopy(audit)
        value["params"]["after_journal_position"] = True
        invalid.append(("boolean audit cursor", value))

        for label, message in invalid:
            with self.subTest(label=label), self.assertRaises(ProtocolValidationError):
                encode_request(message)

    def test_response_validators_reject_invalid_statuses_pages_and_error_envelopes(self) -> None:
        responses = {fixture["label"]: fixture["message"] for fixture in self.fixtures["responses"]}
        graph = responses["get_graph"]
        proposal = responses["get_proposal_commit"]
        audit = responses["get_audit_timeline"]
        error = responses["unknown_run"]

        invalid = []
        value = deepcopy(graph)
        value["result"]["nodes"] = ["not an object"]
        invalid.append(("graph object shape", value))
        value = deepcopy(graph)
        value["result"]["nodes"] = [{"id": str(index)} for index in range(101)]
        invalid.append(("graph page bound", value))
        value = deepcopy(graph)
        value["result"]["has_more"] = True
        value["result"]["next_cursor"] = None
        invalid.append(("missing graph continuation", value))
        value = deepcopy(proposal)
        value["result"]["status"] = {}
        invalid.append(("non-string proposal status", value))
        value = deepcopy(proposal)
        value["result"]["status"] = "PENDING"
        invalid.append(("pending result fields", value))
        value = deepcopy(audit)
        value["result"]["records"].reverse()
        invalid.append(("unordered audit records", value))
        value = deepcopy(audit)
        value["result"]["records"][0]["lifecycle_state"] = []
        invalid.append(("non-string lifecycle state", value))
        value = deepcopy(audit)
        value["result"]["records"][0]["run_id"] = "another-run"
        invalid.append(("audit run binding", value))
        value = deepcopy(error)
        value["error"]["code"] = {}
        invalid.append(("non-string error code", value))
        value = deepcopy(error)
        value["request_id"] = None
        invalid.append(("required error request id", value))
        value = deepcopy(error)
        value["error"]["code"] = "STORE_IN_USE"
        invalid.append(("startup error correlation", value))

        for label, message in invalid:
            with self.subTest(label=label), self.assertRaises(ProtocolValidationError):
                encode_response(message)

    def test_codecs_reject_invalid_utf8_json_types_and_oversized_output(self) -> None:
        for payload in (b"\xff", b"not json", 42):
            with self.subTest(payload=payload), self.assertRaises(ProtocolValidationError):
                decode_request(payload)

        with self.assertRaises(ProtocolValidationError):
            encode_request({
                "protocol_schema_version": 1,
                "request_id": "bad\ud800",
                "operation": "get_run",
                "params": {"run_id": "run-1"},
            })

        oversized = {
            "protocol_schema_version": 1,
            "request_id": "req",
            "error": {"code": "PROTOCOL_ERROR", "message": "x" * MAX_PROTOCOL_MESSAGE_BYTES},
        }
        with self.assertRaisesRegex(ProtocolValidationError, "4 MiB"):
            encode_response(oversized)

    def test_typescript_uses_the_same_wire_fixtures(self) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required by the repository's protocol checks")
        result = subprocess.run(
            [
                node,
                "--experimental-strip-types",
                str(ROOT / "tests" / "check_protocol_typescript.mjs"),
                str(FIXTURE_PATH),
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
