"""
providers/base.py — the contract every belief source implements.

A provider turns one inbound message into a raw
{hot, warm, cold, needs_human} dict. It does not validate, normalise, cache, or
know what a Belief is; belief.py owns all of that. Keeping providers this thin is
what makes adding one a matter of dropping in a file.

`is_llm` is not decoration. Calibration claims are only meaningful over beliefs
that came from a real model, so the flag travels with the belief into the cache
and is what `cache_provenance()` counts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoids a circular import at runtime
    from ..config import Settings


class ProviderError(RuntimeError):
    """A provider could not produce a raw belief. Carries the provider name so a
    chain failure says which link broke."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider


class Provider(ABC):
    """One belief source."""

    #: registry key, and what gets written into the cache entry
    name: str = ""

    #: True only for real model calls. False for anything heuristic.
    is_llm: bool = False

    @abstractmethod
    def model_name(self, settings: "Settings") -> str:
        """Identifier recorded in the cache alongside the belief."""

    @abstractmethod
    def is_available(self, settings: "Settings") -> bool:
        """Whether this provider could run at all — usually 'is a key set'.
        Checked before calling, so a missing key is skipped rather than raised."""

    @abstractmethod
    def generate_raw(self, message: str, settings: "Settings") -> dict:
        """Return a raw {hot, warm, cold, needs_human} dict. Raise on failure."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Provider {self.name} llm={self.is_llm}>"
