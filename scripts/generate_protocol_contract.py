"""Embed the shared protocol contract for clients without runtime file I/O."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from pprint import pformat
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_KEYWORDS = {
    "$ref", "type", "const", "enum", "minimum", "maximum", "pattern", "properties",
    "required", "additionalProperties", "items", "maxItems", "allOf", "if", "then",
    "x-error-code", "x-const-error-code", "x-max-canonical-bytes", "x-size-fields",
    "x-size-canonicalization", "x-max-utf8-bytes",
    "x-version-position", "x-canonical-hash", "x-legacy-canonical-hash",
}


def check_schema(rule: dict, definitions: dict) -> None:
    unknown = rule.keys() - SCHEMA_KEYWORDS
    if unknown:
        raise ValueError(f"unsupported protocol schema keywords: {sorted(unknown)}")
    if "$ref" in rule and rule["$ref"] not in {f"#/$defs/{name}" for name in definitions}:
        raise ValueError(f"unknown protocol schema reference: {rule['$ref']}")
    children = [*rule.get("properties", {}).values(), *rule.get("allOf", [])]
    children.extend(rule[key] for key in ("items", "if", "then") if key in rule)
    for child in children:
        check_schema(child, definitions)


def expand_tables(contract: dict) -> None:
    """Materialize schema enums and conditions from the finite source tables."""
    definitions = contract["$defs"]
    for name in ("Request", "SuccessResponse"):
        definitions[name]["properties"]["operation"]["enum"] = list(contract["x-operations"])
    states = contract["x-proposal-states"]
    definitions["ProposalResult"]["properties"]["status"]["enum"] = list(states)
    scalar_rules = {
        "null": {"type": "null"},
        "identifier": {"$ref": "#/$defs/Identifier"},
        "nullable_identifier": {"$ref": "#/$defs/NullableIdentifier"},
        "integer": {"$ref": "#/$defs/SafeInteger"},
        "positive_integer": {"$ref": "#/$defs/PositiveInteger"},
    }
    definitions["ProposalResult"]["allOf"] = [
        {"if": {"properties": {"status": {"const": status}}},
         "then": {"properties": {field: scalar_rules[rule[field]]
                                  for field in ("reason_code", "resulting_graph_version")}}}
        for status, rule in states.items()
    ]
    audit = definitions["AuditRecord"]["properties"]
    for field, kind in (("lifecycle_state", "lifecycle"), ("outcome", "governance")):
        audit[field]["enum"] = [state for state, rule in states.items() if rule["kind"] == kind]
    definitions["Error"]["properties"]["code"]["enum"] = list(contract["x-errors"])
    definitions["ErrorResponse"]["allOf"] = [
        {"if": {"properties": {"error": {"properties": {"code": {"const": code}}}}},
         "then": {"properties": {"request_id": scalar_rules[mode]}}}
        for code, mode in contract["x-errors"].items()
    ]


def generate(root: Path = ROOT, *, check: bool = False) -> None:
    contract = json.loads((root / "contracts/protocol-v1.json").read_text(encoding="utf-8"))
    expand_tables(contract)
    for definition in contract["$defs"].values():
        check_schema(definition, contract["$defs"])
    header = "Generated from contracts/protocol-v1.json; run python3 -m scripts.generate_protocol_contract."
    aliases = {
        "Operation": list(contract["x-operations"]),
        "ProposalState": list(contract["x-proposal-states"]),
        "AuditLifecycleState": contract["$defs"]["AuditRecord"]["properties"]["lifecycle_state"]["enum"],
        "AuditOutcome": contract["$defs"]["AuditRecord"]["properties"]["outcome"]["enum"],
        "ErrorCode": contract["$defs"]["Error"]["properties"]["code"]["enum"],
    }
    python_aliases = "\n".join(
        f"{name} = Literal[{', '.join(repr(value) for value in values)}]"
        for name, values in aliases.items()
    )
    outputs = {
        "src/problemforger/application/_protocol_contract.py": (
            f'"""{header}"""\n\nfrom typing import Literal\n\n'
            f'{python_aliases}\n\nCONTRACT = {pformat(contract, width=100, sort_dicts=False)}\n'
        ),
        "clients/typescript/protocol_contract.ts": (
            f"// {header}\nexport const protocolContract = "
            + json.dumps(contract, ensure_ascii=True, indent=2)
            + " as const;\n"
        ),
    }
    for relative, content in outputs.items():
        path = root / relative
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise ValueError(f"stale generated protocol contract: {relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if embedded contracts are stale")
    args = parser.parse_args()
    try:
        generate(check=args.check)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
