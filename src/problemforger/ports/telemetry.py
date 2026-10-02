"""Provider-neutral optional observation sink."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TelemetrySink(Protocol):
    """Accept optional observations without affecting authoritative state."""

    def emit(self, observation: object) -> None: ...

    def close(self) -> None: ...
