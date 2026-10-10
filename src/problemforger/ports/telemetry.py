"""Provider-neutral optional observation envelope and sink port."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
from typing import Protocol, runtime_checkable

from problemforger.core.journal import (
    CausationId,
    CorrelationId,
    JournalPosition,
    JsonDocument,
    ProposalId,
    RunId,
)


OBSERVATION_SCHEMA_VERSION = 1
_SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "password",
    "credential",
    "secret",
    "authorization",
)
_TOKEN_COUNT_ATTRIBUTE_KEYS = frozenset({"input_tokens", "output_tokens"})
_RFC3339_UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z"
)
_NON_EMPTY_LABEL_ATTRIBUTE_KEYS = frozenset(
    {
        "provider",
        "model",
        "status",
        "tool_name",
        "adapter_name",
        "diagnostic_code",
    }
)


def _require_identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _redact_sensitive_attributes(value: object, *, key: str | None = None) -> object:
    if key is not None:
        normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_").casefold()
        sensitive = any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)
        token_named = "token" in normalized
        sensitive = sensitive or bool(
            token_named and key not in _TOKEN_COUNT_ATTRIBUTE_KEYS
        )
        if sensitive:
            return "<redacted>"
    if type(value) is dict:
        return {
            item_key: _redact_sensitive_attributes(item, key=item_key)
            for item_key, item in value.items()
        }
    if type(value) is list:
        return [_redact_sensitive_attributes(item) for item in value]
    return value


def _require_integer(value: object, name: str, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}")


def _require_non_negative_number(value: object, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
        or (isinstance(value, float) and not math.isfinite(value))
    ):
        raise ValueError(f"{name} must be a finite non-negative number")


def _validate_standard_attributes(attributes: dict[str, object]) -> None:
    for name in _TOKEN_COUNT_ATTRIBUTE_KEYS:
        if name in attributes:
            _require_integer(attributes[name], name, minimum=0)
    for name in _NON_EMPTY_LABEL_ATTRIBUTE_KEYS:
        if name in attributes and (
            not isinstance(attributes[name], str) or not attributes[name].strip()
        ):
            raise ValueError(f"{name} must be a non-empty string")
    for name in ("cost_usd", "latency_ms"):
        if name in attributes:
            _require_non_negative_number(attributes[name], name)


@dataclass(frozen=True, slots=True)
class TelemetryObservation:
    """Immutable, redacted, versioned observation outside the authoritative journal."""

    run_id: RunId
    event_type: str
    observed_at: datetime
    attributes: JsonDocument = field(default_factory=lambda: JsonDocument.from_value({}))
    proposal_id: ProposalId | None = None
    journal_position: JournalPosition | None = None
    correlation_id: CorrelationId | None = None
    causation_id: CausationId | None = None
    observation_schema_version: int = OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_integer(
            self.observation_schema_version,
            "observation_schema_version",
            minimum=1,
        )
        if self.observation_schema_version != OBSERVATION_SCHEMA_VERSION:
            raise ValueError(
                "unsupported observation schema version: "
                f"{self.observation_schema_version}"
            )
        _require_identifier(self.run_id, "run_id")
        _require_identifier(self.event_type, "event_type")
        if not isinstance(self.observed_at, datetime):
            raise TypeError("observed_at must be a datetime")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(timezone.utc))
        for value, name in (
            (self.proposal_id, "proposal_id"),
            (self.correlation_id, "correlation_id"),
            (self.causation_id, "causation_id"),
        ):
            if value is not None:
                _require_identifier(value, name)
        if self.journal_position is not None:
            _require_integer(self.journal_position, "journal_position", minimum=1)
        if not isinstance(self.attributes, JsonDocument):
            raise TypeError("attributes must be a JsonDocument")
        attributes = self.attributes.value
        if type(attributes) is not dict:
            raise ValueError("attributes must be a JSON object")
        redacted_attributes = _redact_sensitive_attributes(attributes)
        _validate_standard_attributes(redacted_attributes)
        object.__setattr__(
            self,
            "attributes",
            JsonDocument.from_value(redacted_attributes),
        )

    def to_value(self) -> dict[str, object]:
        """Return the stable v1 wire shape with a UTC RFC 3339 timestamp."""
        return {
            "observation_schema_version": self.observation_schema_version,
            "run_id": self.run_id,
            "proposal_id": self.proposal_id,
            "journal_position": self.journal_position,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "event_type": self.event_type,
            "observed_at": self.observed_at.isoformat().replace("+00:00", "Z"),
            "attributes": self.attributes.value,
        }

    @classmethod
    def from_value(cls, value: object) -> TelemetryObservation:
        if type(value) is not dict:
            raise TypeError("telemetry observation must be a JSON object")
        if any(type(key) is not str for key in value):
            raise TypeError("telemetry observation field names must be strings")
        expected = {
            "observation_schema_version",
            "run_id",
            "proposal_id",
            "journal_position",
            "correlation_id",
            "causation_id",
            "event_type",
            "observed_at",
            "attributes",
        }
        actual = set(value)
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            raise ValueError(
                "telemetry observation fields do not match schema "
                f"(missing={missing}, unknown={unknown})"
            )
        timestamp = value["observed_at"]
        if not isinstance(timestamp, str) or not _RFC3339_UTC_TIMESTAMP.fullmatch(
            timestamp
        ):
            raise ValueError("observed_at must be an RFC 3339 UTC timestamp ending in 'Z'")
        try:
            observed_at = datetime.fromisoformat(timestamp[:-1] + "+00:00")
        except ValueError as error:
            raise ValueError(
                "observed_at must be an RFC 3339 UTC timestamp ending in 'Z'"
            ) from error
        attributes = value["attributes"]
        if type(attributes) is not dict:
            raise ValueError("attributes must be a JSON object")
        return cls(
            observation_schema_version=value["observation_schema_version"],
            run_id=RunId(value["run_id"]),
            proposal_id=(
                ProposalId(value["proposal_id"])
                if value["proposal_id"] is not None
                else None
            ),
            journal_position=(
                JournalPosition(value["journal_position"])
                if value["journal_position"] is not None
                else None
            ),
            correlation_id=(
                CorrelationId(value["correlation_id"])
                if value["correlation_id"] is not None
                else None
            ),
            causation_id=(
                CausationId(value["causation_id"])
                if value["causation_id"] is not None
                else None
            ),
            event_type=value["event_type"],
            observed_at=observed_at,
            attributes=JsonDocument.from_value(attributes),
        )


@runtime_checkable
class TelemetrySink(Protocol):
    """Accept optional observations without affecting authoritative state."""

    def emit(self, observation: TelemetryObservation) -> None: ...

    def close(self) -> None: ...
