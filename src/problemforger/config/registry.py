"""Explicit capability/provider registry for composition wiring."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from problemforger.modules.persistence import MemoryEventStore, SqliteEventStore
from problemforger.modules.telemetry import NullTelemetrySink, RecordingTelemetrySink
from problemforger.ports.event_store import StoreDurability

from .event_store import (
    MemoryEventStoreConfig,
    ServiceProfile,
    SqliteEventStoreConfig,
)
from .telemetry import NullTelemetryConfig, RecordingTelemetryConfig


ProviderFactory = Callable[[object, ServiceProfile], object]


class UnknownCapabilityError(ValueError):
    """The composition requested an unregistered capability."""


class UnknownProviderError(ValueError):
    """The composition requested an unregistered provider."""


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    capability: str
    provider: str
    config_type: type[object]
    factory: ProviderFactory
    durability: StoreDurability | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.capability, str)
            or not isinstance(self.provider, str)
            or not self.capability.strip()
            or not self.provider.strip()
        ):
            raise ValueError("capability and provider names are required")
        if not isinstance(self.config_type, type):
            raise TypeError("config_type must be a type")
        if not callable(self.factory):
            raise TypeError("factory must be callable")
        if self.durability is not None and not isinstance(
            self.durability, StoreDurability
        ):
            raise TypeError("durability must be a StoreDurability")

    def to_value(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "provider": self.provider,
            "config_type": f"{self.config_type.__module__}.{self.config_type.__qualname__}",
            "durability": self.durability.value if self.durability else None,
        }


class ProviderRegistry:
    """Finite, inspectable registry; configuration never names import paths."""

    def __init__(self, registrations: Iterable[ProviderRegistration] = ()) -> None:
        self._registrations: dict[tuple[str, str], ProviderRegistration] = {}
        for registration in registrations:
            self.register(registration)

    @property
    def entries(self) -> tuple[ProviderRegistration, ...]:
        return tuple(
            self._registrations[key] for key in sorted(self._registrations)
        )

    def register(self, registration: ProviderRegistration) -> None:
        key = (registration.capability, registration.provider)
        if key in self._registrations:
            raise ValueError(
                f"provider already registered for {registration.capability!r}/"
                f"{registration.provider!r}"
            )
        self._registrations[key] = registration

    def resolve(self, capability: str, provider: str) -> ProviderRegistration:
        if not isinstance(capability, str) or not capability.strip():
            raise UnknownCapabilityError("capability name is required")
        if not isinstance(provider, str) or not provider.strip():
            raise UnknownProviderError("provider name is required")
        if not any(entry.capability == capability for entry in self._registrations.values()):
            raise UnknownCapabilityError(f"unknown capability {capability!r}")
        try:
            return self._registrations[(capability, provider)]
        except KeyError as error:
            raise UnknownProviderError(
                f"unknown provider {provider!r} for capability {capability!r}"
            ) from error

    def build(
        self,
        capability: str,
        provider: str,
        config: object,
        *,
        profile: ServiceProfile = ServiceProfile.NORMAL,
    ) -> object:
        if not isinstance(profile, ServiceProfile):
            raise TypeError("profile must be a ServiceProfile")
        registration = self.resolve(capability, provider)
        if not isinstance(config, registration.config_type):
            raise TypeError(
                f"{capability}/{provider} requires "
                f"{registration.config_type.__name__}"
            )
        if (
            capability == "event_store"
            and profile is ServiceProfile.NORMAL
            and registration.durability is not StoreDurability.DURABLE
        ):
            raise ValueError("normal service profile requires a durable EventStore")
        provider_instance = registration.factory(config, profile)
        if (
            capability == "event_store"
            and profile is ServiceProfile.NORMAL
            and getattr(provider_instance, "durability", None)
            is not StoreDurability.DURABLE
        ):
            error = ValueError("normal service profile requires a durable EventStore")
            try:
                provider_instance.close()
            except Exception as cleanup_error:
                error.add_note(f"provider cleanup failed: {cleanup_error}")
            raise error
        return provider_instance


def _build_event_store(config: object, profile: ServiceProfile) -> object:
    if not isinstance(profile, ServiceProfile):
        raise TypeError("profile must be a ServiceProfile")
    if isinstance(config, MemoryEventStoreConfig):
        if profile is ServiceProfile.NORMAL:
            raise ValueError("normal service profile requires a durable EventStore")
        return MemoryEventStore(max_journal_page_size=config.max_journal_page_size)
    if isinstance(config, SqliteEventStoreConfig):
        return SqliteEventStore(
            Path(config.path),
            max_journal_page_size=config.max_journal_page_size,
            timeout_seconds=config.timeout_seconds,
        )
    raise TypeError("unsupported EventStore configuration")


def _build_null_telemetry(config: object, profile: ServiceProfile) -> object:
    return NullTelemetrySink()


def _build_recording_telemetry(config: object, profile: ServiceProfile) -> object:
    return RecordingTelemetrySink(max_observations=config.max_observations)


def default_registry() -> ProviderRegistry:
    """Return the complete built-in registry as a fresh mutable instance."""
    return ProviderRegistry(
        (
            ProviderRegistration(
                "event_store",
                "memory",
                MemoryEventStoreConfig,
                _build_event_store,
                StoreDurability.EPHEMERAL,
            ),
            ProviderRegistration(
                "event_store",
                "sqlite",
                SqliteEventStoreConfig,
                _build_event_store,
                StoreDurability.DURABLE,
            ),
            ProviderRegistration(
                "telemetry",
                "null",
                NullTelemetryConfig,
                _build_null_telemetry,
            ),
            ProviderRegistration(
                "telemetry",
                "recording",
                RecordingTelemetryConfig,
                _build_recording_telemetry,
            ),
        )
    )
