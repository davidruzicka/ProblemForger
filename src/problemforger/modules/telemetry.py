"""Minimal optional telemetry providers."""

from __future__ import annotations

from problemforger.ports.telemetry import TelemetryObservation


DEFAULT_MAX_OBSERVATIONS = 10_000


def _require_observation(observation: object) -> TelemetryObservation:
    if not isinstance(observation, TelemetryObservation):
        raise TypeError("observation must be a TelemetryObservation")
    return observation


class NullTelemetrySink:
    """Drop observations while preserving the telemetry port."""

    def emit(self, observation: TelemetryObservation) -> None:
        _require_observation(observation)
        return None

    def close(self) -> None:
        return None


class RecordingTelemetrySink:
    """Bounded in-memory sink for tests and local diagnostics."""

    def __init__(self, *, max_observations: int = DEFAULT_MAX_OBSERVATIONS) -> None:
        if (
            isinstance(max_observations, bool)
            or not isinstance(max_observations, int)
            or max_observations <= 0
            or max_observations > DEFAULT_MAX_OBSERVATIONS
        ):
            raise ValueError(
                "max_observations must be a positive integer no greater than "
                f"{DEFAULT_MAX_OBSERVATIONS}"
            )
        self._max_observations = max_observations
        self._observations: list[TelemetryObservation] = []
        self._closed = False

    @property
    def observations(self) -> tuple[TelemetryObservation, ...]:
        return tuple(self._observations)

    def emit(self, observation: TelemetryObservation) -> None:
        if self._closed:
            raise RuntimeError("telemetry sink is closed")
        item = _require_observation(observation)
        if len(self._observations) >= self._max_observations:
            raise OverflowError("telemetry observation limit exceeded")
        self._observations.append(item)

    def close(self) -> None:
        self._closed = True
