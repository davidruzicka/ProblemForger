"""Typed EventStore settings and the explicit provider composition root."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import os
from pathlib import Path

from problemforger.modules.persistence import MemoryEventStore, SqliteEventStore
from problemforger.modules.persistence._base import DEFAULT_MAX_JOURNAL_PAGE_SIZE
from problemforger.ports.event_store import EventStore


class ServiceProfile(str, Enum):
    NORMAL = "normal"
    EPHEMERAL_TEST = "ephemeral_test"


@dataclass(frozen=True, slots=True)
class MemoryEventStoreConfig:
    max_journal_page_size: int = DEFAULT_MAX_JOURNAL_PAGE_SIZE

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_journal_page_size, bool)
            or not isinstance(self.max_journal_page_size, int)
            or self.max_journal_page_size <= 0
            or self.max_journal_page_size > DEFAULT_MAX_JOURNAL_PAGE_SIZE
        ):
            raise ValueError(
                "max_journal_page_size must be a positive integer no greater than "
                f"{DEFAULT_MAX_JOURNAL_PAGE_SIZE}"
            )


@dataclass(frozen=True, slots=True)
class SqliteEventStoreConfig:
    path: str | os.PathLike[str]
    max_journal_page_size: int = DEFAULT_MAX_JOURNAL_PAGE_SIZE
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not os.fspath(self.path):
            raise ValueError("SQLite path is required")
        if (
            isinstance(self.max_journal_page_size, bool)
            or not isinstance(self.max_journal_page_size, int)
            or self.max_journal_page_size <= 0
            or self.max_journal_page_size > DEFAULT_MAX_JOURNAL_PAGE_SIZE
        ):
            raise ValueError(
                "max_journal_page_size must be a positive integer no greater than "
                f"{DEFAULT_MAX_JOURNAL_PAGE_SIZE}"
            )
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")


EventStoreConfig = MemoryEventStoreConfig | SqliteEventStoreConfig


def build_event_store(
    config: EventStoreConfig, *, profile: ServiceProfile = ServiceProfile.NORMAL
) -> EventStore:
    """Construct one typed provider and enforce normal-service durability."""
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
