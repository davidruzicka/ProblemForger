"""Typed configuration and explicit provider selection."""

from .event_store import (
    EventStoreConfig,
    MemoryEventStoreConfig,
    ServiceProfile,
    SqliteEventStoreConfig,
    build_event_store,
)

__all__ = [
    "EventStoreConfig",
    "MemoryEventStoreConfig",
    "ServiceProfile",
    "SqliteEventStoreConfig",
    "build_event_store",
]
