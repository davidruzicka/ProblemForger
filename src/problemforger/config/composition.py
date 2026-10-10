"""Single composition root for configured ProblemForger capabilities."""

from __future__ import annotations

from dataclasses import dataclass

from problemforger.ports.event_store import EventStore
from problemforger.ports.telemetry import TelemetrySink

from .event_store import ServiceProfile
from .models import ModuleConfig
from .registry import ProviderRegistry, default_registry


@dataclass(slots=True)
class ComposedModules:
    """The one provider instance set shared by the service/application."""

    event_store: EventStore
    telemetry: TelemetrySink
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.telemetry.close()
        finally:
            try:
                self.event_store.close()
            finally:
                self._closed = True


def compose(
    config: ModuleConfig,
    *,
    profile: ServiceProfile = ServiceProfile.NORMAL,
    registry: ProviderRegistry | None = None,
) -> ComposedModules:
    """Construct configured ports and clean up if later startup fails."""
    if not isinstance(config, ModuleConfig):
        raise TypeError("config must be a ModuleConfig")
    active_registry = registry if registry is not None else default_registry()
    event_store: EventStore | None = None
    try:
        event_store = active_registry.build(
            "event_store",
            config.event_store.provider,
            config.event_store.config,
            profile=profile,
        )
        telemetry = active_registry.build(
            "telemetry",
            config.telemetry.provider,
            config.telemetry.config,
            profile=profile,
        )
        return ComposedModules(event_store=event_store, telemetry=telemetry)
    except BaseException as error:
        if event_store is not None:
            try:
                event_store.close()
            except Exception as cleanup_error:
                error.add_note(f"provider cleanup failed: {cleanup_error}")
        raise
