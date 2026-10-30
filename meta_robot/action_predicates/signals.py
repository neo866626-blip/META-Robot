# SPDX-FileCopyrightText: Copyright (c) 2026 META-Robot contributors
# SPDX-License-Identifier: Apache-2.0

"""Explicit observation adapters and bounded temporal signal summaries."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from .models import EvidenceFrame, EvidenceRequirement, Observation, identifier, text


@dataclass(frozen=True)
class SignalSample:
    timestamp: float
    value: float


def sustained_threshold(
    samples: tuple[SignalSample, ...], *, start: float, end: float,
    threshold: float, min_samples: int, max_gap_s: float,
) -> bool | None:
    """Resolve sustained contact/load only for a sufficiently covered window.

    Thresholds and sampling requirements are embodiment-specific inputs, never
    inferred from a generic robot name. Incomplete windows remain unresolved.
    """
    if not all(math.isfinite(x) for x in (start, end, threshold, max_gap_s)):
        raise ValueError("window parameters must be finite")
    if end <= start or max_gap_s <= 0 or type(min_samples) is not int or min_samples < 2:
        raise ValueError("invalid temporal evidence policy")
    if any(not math.isfinite(s.timestamp) or not math.isfinite(s.value) for s in samples):
        return None
    window = sorted((s for s in samples if start <= s.timestamp <= end), key=lambda s: s.timestamp)
    if len({s.timestamp for s in window}) != len(window) or len(window) < min_samples:
        return None
    times = [start, *(s.timestamp for s in window), end]
    if any(b - a > max_gap_s for a, b in zip(times, times[1:])):
        return None
    return all(sample.value >= threshold for sample in window)


class EvidenceCollector:
    """Register only operator-selected feedback sources; collect on demand."""

    def __init__(self, *, clock=time.time):
        self.clock = clock
        self._providers: dict[str, tuple[str, str, Callable[[], Any]]] = {}

    def register(self, fact: str, modality: str, source: str, read: Callable[[], Any]) -> None:
        identifier(fact)
        identifier(modality)
        text(source, "source")
        if not callable(read):
            raise ValueError("feedback reader must be callable")
        if fact in self._providers:
            raise ValueError(f"feedback source already registered: {fact}")
        self._providers[fact] = (modality, source, read)

    def missing(self, requirements: tuple[EvidenceRequirement, ...]) -> list[str]:
        return sorted(r.fact for r in requirements if r.fact not in self._providers
                      or self._providers[r.fact][0] != r.modality)

    @property
    def modalities(self) -> set[str]:
        return {provider[0] for provider in self._providers.values()}

    def collect(self) -> EvidenceFrame:
        observations = {}
        for fact, (modality, source, read) in self._providers.items():
            # Timestamp the start of acquisition, so a slow reader cannot make
            # old evidence appear fresh merely by returning later.
            observed_at = self.clock()
            try:
                value = read()
            except Exception:
                value = None
            observations[fact] = Observation(value, modality, source, observed_at)
        return EvidenceFrame(observations, self.clock())
