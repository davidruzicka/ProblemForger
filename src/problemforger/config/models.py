"""Versioned top-level module configuration and redacted export."""

from __future__ import annotations

from collections.abc import Mapping
import json
from dataclasses import dataclass

from ._validation import reject_unknown_keys, require_mapping, require_provider_name
from .event_store import (
    EventStoreConfig,
    MemoryEventStoreConfig,
    SqliteEventStoreConfig,
    event_store_config_from_value,
)
from .telemetry import (
    NullTelemetryConfig,
    RecordingTelemetryConfig,
    TelemetryConfig,
    telemetry_config_from_value,
)


MODULE_CONFIGURATION_SCHEMA_VERSION = 1
_SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "credential",
    "password",
    "private_key",
    "privatekey",
    "secret",
    "token",
)


def _provider_selection(value: object, label: str) -> tuple[str, Mapping[str, object]]:
    selection = require_mapping(value, label)
    reject_unknown_keys(selection, frozenset({"provider", "config"}), label)
    provider = require_provider_name(selection.get("provider"), label)
    return provider, require_mapping(selection.get("config", {}), f"{label} config")


@dataclass(frozen=True, slots=True)
class EventStoreModuleConfig:
    provider: str
    config: EventStoreConfig

    def __post_init__(self) -> None:
        require_provider_name(self.provider, "event_store")
        if self.provider not in {"memory", "sqlite"}:
            raise ValueError(f"unknown event_store provider {self.provider!r}")
        if self.provider == "memory" and not isinstance(
            self.config, MemoryEventStoreConfig
        ):
            raise TypeError("memory EventStore requires MemoryEventStoreConfig")
        if self.provider == "sqlite" and not isinstance(
            self.config, SqliteEventStoreConfig
        ):
            raise TypeError("sqlite EventStore requires SqliteEventStoreConfig")

    def to_value(self) -> dict[str, object]:
        return {"provider": self.provider, "config": self.config.to_value()}


@dataclass(frozen=True, slots=True)
class TelemetryModuleConfig:
    provider: str
    config: TelemetryConfig

    def __post_init__(self) -> None:
        require_provider_name(self.provider, "telemetry")
        if self.provider not in {"null", "recording"}:
            raise ValueError(f"unknown telemetry provider {self.provider!r}")
        expected = {
            "null": NullTelemetryConfig,
            "recording": RecordingTelemetryConfig,
        }[self.provider]
        if not isinstance(self.config, expected):
            raise TypeError(f"{self.provider} telemetry requires {expected.__name__}")

    def to_value(self) -> dict[str, object]:
        return {"provider": self.provider, "config": self.config.to_value()}


@dataclass(frozen=True, slots=True)
class ModuleConfig:
    event_store: EventStoreModuleConfig
    telemetry: TelemetryModuleConfig
    schema_version: int = MODULE_CONFIGURATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.event_store, EventStoreModuleConfig):
            raise TypeError("event_store must be an EventStoreModuleConfig")
        if not isinstance(self.telemetry, TelemetryModuleConfig):
            raise TypeError("telemetry must be a TelemetryModuleConfig")
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != MODULE_CONFIGURATION_SCHEMA_VERSION
        ):
            raise ValueError("unsupported module configuration schema version")

    @classmethod
    def from_value(cls, value: object) -> ModuleConfig:
        source = require_mapping(value, "module configuration")
        reject_unknown_keys(source, frozenset({"schema_version", "modules"}), "module configuration")
        schema_version = source.get("schema_version")
        if schema_version != MODULE_CONFIGURATION_SCHEMA_VERSION or isinstance(schema_version, bool):
            raise ValueError("unsupported module configuration schema version")
        modules = require_mapping(source.get("modules"), "modules")
        allowed = frozenset({"event_store", "telemetry"})
        unknown = sorted(set(modules) - allowed)
        if unknown:
            raise ValueError(f"unknown module capability {unknown[0]!r}")
        event_store_provider, event_store_value = _provider_selection(
            modules.get("event_store"), "event_store"
        )
        telemetry_source = modules.get("telemetry", {"provider": "null", "config": {}})
        telemetry_provider, telemetry_value = _provider_selection(
            telemetry_source, "telemetry"
        )
        return cls(
            event_store=EventStoreModuleConfig(
                event_store_provider,
                event_store_config_from_value(event_store_provider, event_store_value),
            ),
            telemetry=TelemetryModuleConfig(
                telemetry_provider,
                telemetry_config_from_value(telemetry_provider, telemetry_value),
            ),
            schema_version=schema_version,
        )

    def to_value(self, *, redacted: bool = True) -> dict[str, object]:
        value = {
            "schema_version": self.schema_version,
            "modules": {
                "event_store": self.event_store.to_value(),
                "telemetry": self.telemetry.to_value(),
            },
        }
        return redact_value(value) if redacted else value

    def to_json(self, *, redacted: bool = True) -> str:
        return json.dumps(
            self.to_value(redacted=redacted),
            sort_keys=True,
            separators=(",", ":"),
        )


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def redact_value(value: object, *, _key: str | None = None) -> object:
    if _key is not None and _is_sensitive_key(_key):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {
            str(key): redact_value(item, _key=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value


def export_effective_config(config: ModuleConfig) -> dict[str, object]:
    if not isinstance(config, ModuleConfig):
        raise TypeError("config must be a ModuleConfig")
    return config.to_value(redacted=True)


def export_effective_config_json(config: ModuleConfig) -> str:
    if not isinstance(config, ModuleConfig):
        raise TypeError("config must be a ModuleConfig")
    return config.to_json(redacted=True)
