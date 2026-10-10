"""Typed EventStore provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os

from problemforger.modules.persistence._base import DEFAULT_MAX_JOURNAL_PAGE_SIZE
from problemforger.modules.persistence.sqlite import (
    _normalize_timeout_seconds,
)

from ._validation import reject_unknown_keys, require_mapping


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

    @classmethod
    def from_value(cls, value: object) -> MemoryEventStoreConfig:
        config = require_mapping(value, "memory EventStore config")
        reject_unknown_keys(
            config,
            frozenset({"max_journal_page_size"}),
            "memory EventStore config",
        )
        return cls(
            max_journal_page_size=config.get(
                "max_journal_page_size", DEFAULT_MAX_JOURNAL_PAGE_SIZE
            )
        )

    def to_value(self) -> dict[str, object]:
        return {"max_journal_page_size": self.max_journal_page_size}


@dataclass(frozen=True, slots=True)
class SqliteEventStoreConfig:
    path: str | os.PathLike[str]
    max_journal_page_size: int = DEFAULT_MAX_JOURNAL_PAGE_SIZE
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        path = os.fspath(self.path)
        if not isinstance(path, str):
            raise TypeError("SQLite path must be a string")
        if not path:
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
        object.__setattr__(
            self, "timeout_seconds", _normalize_timeout_seconds(self.timeout_seconds)
        )

    @classmethod
    def from_value(cls, value: object) -> SqliteEventStoreConfig:
        config = require_mapping(value, "SQLite EventStore config")
        reject_unknown_keys(
            config,
            frozenset({"path", "max_journal_page_size", "timeout_seconds"}),
            "SQLite EventStore config",
        )
        if "path" not in config:
            raise ValueError("SQLite path is required")
        return cls(
            path=config["path"],
            max_journal_page_size=config.get(
                "max_journal_page_size", DEFAULT_MAX_JOURNAL_PAGE_SIZE
            ),
            timeout_seconds=config.get("timeout_seconds", 5.0),
        )

    def to_value(self) -> dict[str, object]:
        return {
            "path": os.fspath(self.path),
            "max_journal_page_size": self.max_journal_page_size,
            "timeout_seconds": self.timeout_seconds,
        }


EventStoreConfig = MemoryEventStoreConfig | SqliteEventStoreConfig


def event_store_config_from_value(provider: str, value: object) -> EventStoreConfig:
    if provider == "memory":
        return MemoryEventStoreConfig.from_value(value)
    if provider == "sqlite":
        return SqliteEventStoreConfig.from_value(value)
    raise ValueError(f"unknown event_store provider {provider!r}")
