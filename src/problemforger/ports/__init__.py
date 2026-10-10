"""Provider-neutral capability interfaces."""

from .event_store import EventStore
from .telemetry import TelemetrySink

__all__ = ["EventStore", "TelemetrySink"]
