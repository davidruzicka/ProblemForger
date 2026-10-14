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

        requests_by_id = {
            fixture["message"]["request_id"]: fixture["message"]
            for fixture in self.fixtures["requests"]
        }
        for fixture in self.fixtures["responses"]:
            with self.subTest(label=fixture["label"]):
                request = requests_by_id.get(fixture["message"]["request_id"])
                encoded = encode_response(fixture["message"], request)
                self.assertEqual(decode_response(encoded, request), fixture["message"])

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

    def test_subdocument_size_uses_shared_exponential_number_formatting(self) -> None:
        values = [{"x": 1e-7}] * 95_000
        create_run = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "create_run")
        )
        create_run["params"]["run_metadata"]["data"]["items"] = values
        encode_request(create_run)

        mutation = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "propose_mutation")
        )
        mutation["params"]["operations"] = values
        mutation["params"]["evidence"] = []
        encode_request(mutation)

    def test_decoded_integral_json_numbers_are_normalized(self) -> None:
        request = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "get_graph")
        )
        request["params"]["limit"] = 1.0
        encode_request(request)

        for number in (b"1.0", b"1e0"):
            payload = (
                b'{"protocol_schema_version":1,"request_id":"req","operation":"get_graph",'
                b'"params":{"run_id":"run-1","limit":' + number + b"}}"
            )
            with self.subTest(number=number):
                decoded = decode_request(payload)
                self.assertEqual(decoded["params"]["limit"], 1)
                self.assertIs(type(decoded["params"]["limit"]), int)

    def test_decode_wraps_python_integer_digit_limit_as_protocol_error(self) -> None:
        payload = (
            b'{"protocol_schema_version":1,"request_id":"req","operation":"create_run",'
            b'"params":{"run_id":"run-1","run_metadata":{"metadata_schema_version":1,'
            b'"data":{"value":' + b"9" * 5_000 + b"}}}}}"
        )
        with self.assertRaises(ProtocolValidationError):
            decode_request(payload)

    def test_decoder_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        duplicate = b'{"protocol_schema_version":1,"protocol_schema_version":1}'
        non_finite = b'{"protocol_schema_version":1,"request_id":"r","operation":"get_run","params":{"run_id":"x","extra":NaN}}'
        for payload in (duplicate, non_finite):
            with self.subTest(payload=payload):
                with self.assertRaises(ProtocolValidationError):
                    decode_request(payload)

    def test_json_documents_reject_unsafe_integers_and_invalid_unicode(self) -> None:
        with self.assertRaises(ProtocolValidationError):
            decode_request(
                b'{"protocol_schema_version":1,"request_id":"req","operation":"create_run","params":{"run_id":"run-1","run_metadata":{"metadata_schema_version":1,"data":{"value":9007199254740993}}}}'
            )
        with self.assertRaises(ProtocolValidationError):
            decode_request(
                br'{"protocol_schema_version":1,"request_id":"req","operation":"create_run","params":{"run_id":"run-1","run_metadata":{"metadata_schema_version":1,"data":{"value":"\ud800"}}}}'
            )

        requests = {item["label"]: deepcopy(item["message"]) for item in self.fixtures["requests"]}
        create_run = requests["create_run"]
        create_run["params"]["run_metadata"]["data"]["nested"] = {"value": 9_007_199_254_740_993}
        with self.assertRaises(ProtocolValidationError):
            encode_request(create_run)

        safe_integer = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "create_run")
        )
        safe_integer["params"]["run_metadata"]["data"]["value"] = 9_007_199_254_740_991
        encode_request(safe_integer)

        propose = requests["propose_mutation"]
        propose["params"]["operations"] = [{"value": 9_007_199_254_740_993}]
        with self.assertRaises(ProtocolValidationError):
            encode_request(propose)

        graph = next(item["message"] for item in self.fixtures["responses"] if item["label"] == "get_graph")
        unsafe_graph = deepcopy(graph)
        unsafe_graph["result"]["nodes"] = [{"value": 9_007_199_254_740_993}]
        with self.assertRaises(ProtocolValidationError):
            encode_response(unsafe_graph)

        for invalid_json in (
            {"value": "\ud800"},
            {"key\ud800": "value"},
        ):
            with self.subTest(invalid_json=repr(invalid_json)):
                invalid_request = deepcopy(requests["create_run"])
                invalid_request["params"]["run_metadata"]["data"] = invalid_json
                with self.assertRaises(ProtocolValidationError):
                    encode_request(invalid_request)

    def test_response_correlation_applies_to_all_operations_and_errors(self) -> None:
        requests = {item["label"]: deepcopy(item["message"]) for item in self.fixtures["requests"]}
        responses = {item["label"]: deepcopy(item["message"]) for item in self.fixtures["responses"]}

        create_request = requests["create_run"]
        create_response = responses["create_run"]
        for bad_request in (
            {**create_request, "request_id": "another-request"},
            {**create_request, "operation": "get_run", "params": {"run_id": "run-1"}},
            {**create_request, "params": {**create_request["params"], "run_id": "another-run"}},
        ):
            with self.subTest(bad_request=bad_request), self.assertRaises(ProtocolValidationError):
                encode_response(create_response, bad_request)

        proposal_request = requests["propose_mutation"]
        proposal_response = responses["propose_mutation_pending"]
        wrong_proposal = deepcopy(proposal_request)
        wrong_proposal["params"]["proposal_id"] = "another-proposal"
        with self.assertRaises(ProtocolValidationError):
            encode_response(proposal_response, wrong_proposal)

        with self.assertRaises(ProtocolValidationError):
            encode_response(responses["unknown_run"], {**requests["get_run"], "request_id": "another-request"})

        encoded = encode_response(create_response, create_request)
        self.assertEqual(decode_response(encoded, create_request), create_response)

    def test_create_run_response_metadata_matches_request_canonically(self) -> None:
        request = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "create_run")
        )
        response = deepcopy(
            next(item["message"] for item in self.fixtures["responses"] if item["label"] == "create_run")
        )
        request["params"]["run_metadata"]["data"] = {
            "second": 2,
            "first": {"enabled": True},
            "integral_float": 1.0,
        }
        response["result"]["run_metadata"]["data"] = {
            "first": {"enabled": True},
            "second": 2,
            "integral_float": 1,
        }
        response["result"]["metadata_hash"] = (
            "sha256:problemforger-run-metadata-v1:"
            "00ee606ab94545cf77dae3af2ae13d37971a0723991ef224347872807c00aabc"
        )
        self.assertEqual(decode_response(encode_response(response, request), request), response)

        mismatches = []
        different_value = deepcopy(response)
        different_value["result"]["run_metadata"]["data"]["first"]["enabled"] = False
        mismatches.append(("different metadata value", different_value))
        different_type = deepcopy(response)
        different_type["result"]["run_metadata"]["data"]["first"]["enabled"] = 1
        mismatches.append(("boolean and number metadata differ", different_type))

        for label, invalid in mismatches:
            with self.subTest(label=label), self.assertRaises(ProtocolValidationError):
                encode_response(invalid, request)
            with self.subTest(label=f"decoded {label}"), self.assertRaises(ProtocolValidationError):
                decode_response(json.dumps(invalid, separators=(",", ":")), request)

    def test_newly_created_run_response_has_zero_versions(self) -> None:
        response = deepcopy(
            next(item["message"] for item in self.fixtures["responses"] if item["label"] == "create_run")
        )
        for field in ("graph_version", "last_journal_position"):
            invalid = deepcopy(response)
            invalid["result"][field] = 1
            with self.subTest(field=field), self.assertRaises(ProtocolValidationError):
                encode_response(invalid)
            with self.subTest(field=f"decoded {field}"), self.assertRaises(ProtocolValidationError):
                decode_response(json.dumps(invalid, separators=(",", ":")))

    def test_run_response_graph_version_does_not_exceed_journal_position(self) -> None:
        response = deepcopy(
            next(item["message"] for item in self.fixtures["responses"] if item["label"] == "get_run")
        )
        response["result"]["graph_version"] = response["result"]["last_journal_position"] + 1
        request = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "get_run")
        )

        with self.assertRaises(ProtocolValidationError):
            encode_response(response, request)
        with self.assertRaises(ProtocolValidationError):
            decode_response(json.dumps(response, separators=(",", ":")), request)

    def test_get_run_response_cannot_claim_to_create_the_run(self) -> None:
        response = deepcopy(
            next(item["message"] for item in self.fixtures["responses"] if item["label"] == "get_run")
        )
        response["result"].update(created=True, graph_version=0, last_journal_position=0)
        request = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "get_run")
        )

        with self.assertRaises(ProtocolValidationError):
            encode_response(response, request)
        with self.assertRaises(ProtocolValidationError):
            decode_response(json.dumps(response, separators=(",", ":")), request)

    def test_all_public_graph_versions_are_bounded_by_journal_position(self) -> None:
        responses = {item["label"]: deepcopy(item["message"]) for item in self.fixtures["responses"]}
        proposal = responses["get_proposal_commit"]
        proposal["result"].update(resulting_graph_version=99, journal_position=1)
        audit = responses["get_audit_timeline"]
        audit["result"]["records"][0]["graph_version"] = 99
        for response in (proposal, audit):
            with self.subTest(operation=response["operation"]):
                with self.assertRaises(ProtocolValidationError):
                    encode_response(response)
                with self.assertRaises(ProtocolValidationError):
                    decode_response(json.dumps(response))

    def test_identifier_blank_set_is_language_independent(self) -> None:
        request = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "get_run")
        )
        for blank in ("\u001c", "\ufeff", "\u001c\ufeff "):
            request["request_id"] = blank
            with self.subTest(blank=repr(blank)), self.assertRaises(ProtocolValidationError):
                encode_request(request)

    def test_proposal_response_versions_match_the_originating_request(self) -> None:
        request = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "propose_mutation")
        )
        request["params"]["expected_graph_version"] = 2
        response = deepcopy(
            next(item["message"] for item in self.fixtures["responses"] if item["label"] == "get_proposal_commit")
        )
        response["request_id"] = request["request_id"]
        response["operation"] = "propose_mutation"
        response["result"]["proposal_id"] = request["params"]["proposal_id"]

        invalid_results = (
            ("commit advances more than once", "COMMIT", None, 4),
            ("reject advances graph", "REJECT", "POLICY_REJECTED", 3),
            ("conflict has no version mismatch", "CONFLICT", "VERSION_CONFLICT", 2),
        )
        for label, status, reason_code, resulting_version in invalid_results:
            invalid = deepcopy(response)
            invalid["result"].update(
                status=status,
                reason_code=reason_code,
                resulting_graph_version=resulting_version,
            )
            with self.subTest(label=label), self.assertRaises(ProtocolValidationError):
                encode_response(invalid, request)
            with self.subTest(label=f"decoded {label}"), self.assertRaises(ProtocolValidationError):
                decode_response(json.dumps(invalid, separators=(",", ":")), request)

        valid_commit = deepcopy(response)
        valid_commit["result"].update(status="COMMIT", resulting_graph_version=3)
        self.assertEqual(decode_response(encode_response(valid_commit, request), request), valid_commit)

        for status, resulting_version in (("REJECT", 2), ("RETRY", 2), ("ESCALATE", 2), ("CONFLICT", 3)):
            valid_terminal = deepcopy(response)
            valid_terminal["result"].update(
                status=status,
                reason_code=f"{status}_REASON",
                resulting_graph_version=resulting_version,
            )
            with self.subTest(status=status):
                self.assertEqual(
                    decode_response(encode_response(valid_terminal, request), request),
                    valid_terminal,
                )

    def test_committed_proposal_accepts_a_valid_optional_reason_code(self) -> None:
        request = deepcopy(
            next(item["message"] for item in self.fixtures["requests"] if item["label"] == "propose_mutation")
        )
        request["params"]["expected_graph_version"] = 2
        response = deepcopy(
            next(item["message"] for item in self.fixtures["responses"] if item["label"] == "get_proposal_commit")
        )
        response["request_id"] = request["request_id"]
        response["operation"] = "propose_mutation"
        response["result"]["proposal_id"] = request["params"]["proposal_id"]
        response["result"]["reason_code"] = "all_checks_passed"

        self.assertEqual(decode_response(encode_response(response, request), request), response)

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

    def test_invalid_audit_limits_use_invalid_limit_error_code(self) -> None:
        template = deepcopy(
            next(
                item["message"]
                for item in self.fixtures["requests"]
                if item["label"] == "get_audit_timeline"
            )
        )
        invalid_requests = []
        for limit in (0, 101, 1.5, True):
            request = deepcopy(template)
            request["params"]["limit"] = limit
            invalid_requests.append((f"limit={limit!r}", request))
        missing_limit = deepcopy(template)
        del missing_limit["params"]["limit"]
        invalid_requests.append(("missing limit", missing_limit))

        for label, request in invalid_requests:
            with self.subTest(label=label):
                with self.assertRaises(ProtocolValidationError) as error:
                    encode_request(request)
                self.assertEqual(error.exception.code, "INVALID_LIMIT")

        with self.assertRaises(ProtocolValidationError) as decode_error:
            decode_request(json.dumps(invalid_requests[0][1]))
        self.assertEqual(decode_error.exception.code, "INVALID_LIMIT")

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

    def test_response_pages_respect_the_originating_request_limit(self) -> None:
        requests = {item["label"]: deepcopy(item["message"]) for item in self.fixtures["requests"]}
        responses = {item["label"]: deepcopy(item["message"]) for item in self.fixtures["responses"]}

        graph_request = requests["get_graph"]
        graph_request["params"]["limit"] = 1
        graph_response = responses["get_graph"]
        first_node = graph_response["result"]["nodes"][0]
        graph_response["result"]["nodes"] = [first_node, {**first_node, "id": "goal-2"}]
        with self.assertRaises(ProtocolValidationError):
            encode_response(graph_response, graph_request)
        with self.assertRaises(ProtocolValidationError):
            decode_response(json.dumps(graph_response, separators=(",", ":")), graph_request)

        graph_request["params"]["limit"] = 2
        self.assertEqual(
            decode_response(encode_response(graph_response, graph_request), graph_request),
            graph_response,
        )

        audit_request = requests["get_audit_timeline"]
        audit_request["params"]["limit"] = 1
        audit_response = responses["get_audit_timeline"]
        with self.assertRaises(ProtocolValidationError):
            encode_response(audit_response, audit_request)
        with self.assertRaises(ProtocolValidationError):
            decode_response(json.dumps(audit_response, separators=(",", ":")), audit_request)

        audit_request["params"]["limit"] = 2
        self.assertEqual(
            decode_response(encode_response(audit_response, audit_request), audit_request),
            audit_response,
        )

    def test_audit_cursor_matches_last_record_and_supplied_request_cursor(self) -> None:
        response = next(
            item["message"] for item in self.fixtures["responses"] if item["label"] == "get_audit_timeline"
        )
        invalid = deepcopy(response)
        invalid["result"]["next_after_journal_position"] = 99
        with self.assertRaises(ProtocolValidationError):
            encode_response(invalid)

        empty = deepcopy(response)
        empty["result"]["records"] = []
        empty["result"]["next_after_journal_position"] = 5
        empty["result"]["has_more"] = False
        request = deepcopy(next(
            item["message"] for item in self.fixtures["requests"] if item["label"] == "get_audit_timeline"
        ))
        request["params"]["after_journal_position"] = 4
        with self.assertRaises(ProtocolValidationError):
            encode_response(empty, request)

        empty["result"]["next_after_journal_position"] = 4
        self.assertEqual(decode_response(encode_response(empty, request), request), empty)
        with self.assertRaises(ProtocolValidationError):
            encode_response(empty)

        from_start = deepcopy(empty)
        from_start["result"]["next_after_journal_position"] = 0
        initial_request = deepcopy(request)
        initial_request["params"].pop("after_journal_position")
        with self.assertRaises(ProtocolValidationError):
            encode_response(from_start)
        self.assertEqual(
            decode_response(encode_response(from_start, initial_request), initial_request),
            from_start,
        )

        empty["result"]["has_more"] = True
        with self.assertRaises(ProtocolValidationError):
            encode_response(empty, request)
        empty["result"]["has_more"] = False

        wrong_request = deepcopy(request)
        wrong_request["request_id"] = "another-request"
        with self.assertRaises(ProtocolValidationError):
            encode_response(empty, wrong_request)
        wrong_request = deepcopy(request)
        wrong_request["params"]["run_id"] = "another-run"
        with self.assertRaises(ProtocolValidationError):
            encode_response(empty, wrong_request)
        wrong_request = deepcopy(request)
        wrong_request["operation"] = "get_run"
        wrong_request["params"] = {"run_id": "run-1"}
        with self.assertRaises(ProtocolValidationError):
            encode_response(empty, wrong_request)

        before_cursor = deepcopy(response)
        before_cursor["result"]["records"][0]["journal_position"] = 1
        before_cursor["result"]["next_after_journal_position"] = 2
        request["params"]["after_journal_position"] = 1
        with self.assertRaises(ProtocolValidationError):
            encode_response(before_cursor, request)

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
