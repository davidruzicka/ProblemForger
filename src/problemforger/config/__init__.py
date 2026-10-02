"""Typed configuration and explicit provider selection."""

from .composition import ComposedModules, compose
from .event_store import (
    EventStoreConfig,
    MemoryEventStoreConfig,
    ServiceProfile,
    SqliteEventStoreConfig,
)
from .models import (
    EventStoreModuleConfig,
    ModuleConfig,
    TelemetryModuleConfig,
    export_effective_config,
    export_effective_config_json,
    redact_value,
)
from .registry import (
    ProviderRegistration,
    ProviderRegistry,
    UnknownCapabilityError,
    UnknownProviderError,
    default_registry,
)
from .telemetry import NullTelemetryConfig, RecordingTelemetryConfig, TelemetryConfig

__all__ = [
    "ComposedModules",
    "EventStoreConfig",
    "EventStoreModuleConfig",
    "MemoryEventStoreConfig",
    "ModuleConfig",
    "NullTelemetryConfig",
    "ProviderRegistration",
    "ProviderRegistry",
    "RecordingTelemetryConfig",
    "ServiceProfile",
    "SqliteEventStoreConfig",
    "TelemetryConfig",
    "TelemetryModuleConfig",
    "UnknownCapabilityError",
    "UnknownProviderError",
    "compose",
    "default_registry",
    "export_effective_config",
    "export_effective_config_json",
    "redact_value",
]
