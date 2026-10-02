"""Typed telemetry provider configuration."""

from __future__ import annotations

from dataclasses import dataclass

from problemforger.modules.telemetry import DEFAULT_MAX_OBSERVATIONS

from ._validation import reject_unknown_keys, require_mapping


@dataclass(frozen=True, slots=True)
class NullTelemetryConfig:
    @classmethod
    def from_value(cls, value: object) -> NullTelemetryConfig:
        config = require_mapping(value, "null telemetry config")
        reject_unknown_keys(config, frozenset(), "null telemetry config")
        return cls()

    def to_value(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True, slots=True)
class RecordingTelemetryConfig:
    max_observations: int = DEFAULT_MAX_OBSERVATIONS

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_observations, bool)
            or not isinstance(self.max_observations, int)
            or self.max_observations <= 0
            or self.max_observations > DEFAULT_MAX_OBSERVATIONS
        ):
            raise ValueError(
                "max_observations must be a positive integer no greater than "
                f"{DEFAULT_MAX_OBSERVATIONS}"
            )

    @classmethod
    def from_value(cls, value: object) -> RecordingTelemetryConfig:
        config = require_mapping(value, "recording telemetry config")
        reject_unknown_keys(
            config,
            frozenset({"max_observations"}),
            "recording telemetry config",
        )
        return cls(max_observations=config.get("max_observations", DEFAULT_MAX_OBSERVATIONS))

    def to_value(self) -> dict[str, object]:
        return {"max_observations": self.max_observations}


TelemetryConfig = NullTelemetryConfig | RecordingTelemetryConfig


def telemetry_config_from_value(provider: str, value: object) -> TelemetryConfig:
    if provider == "null":
        return NullTelemetryConfig.from_value(value)
    if provider == "recording":
        return RecordingTelemetryConfig.from_value(value)
    raise ValueError(f"unknown telemetry provider {provider!r}")
