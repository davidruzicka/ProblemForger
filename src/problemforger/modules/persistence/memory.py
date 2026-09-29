"""Explicitly ephemeral EventStore for contract tests and local experiments."""

from problemforger.ports.event_store import StoreDurability

from ._base import DEFAULT_MAX_JOURNAL_PAGE_SIZE, EventStoreState


class MemoryEventStore(EventStoreState):
    """In-process provider; never suitable for the normal durable service profile."""

    def __init__(self, *, max_journal_page_size: int = DEFAULT_MAX_JOURNAL_PAGE_SIZE) -> None:
        super().__init__(
            durability=StoreDurability.EPHEMERAL,
            max_journal_page_size=max_journal_page_size,
        )
