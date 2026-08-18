"""
providers/rule_provider.py — offline keyword fallback.

Deliberately crude. This is a floor that lets the pipeline complete with no API
key, not a model anyone should draw conclusions from. `is_llm` is False, which is
what stops a belief from here being counted in a calibration claim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Provider

if TYPE_CHECKING:
    from ..config import Settings

HOT_KEYWORDS = (
    "price", "cost", "how much", "buy", "purchase", "book", "schedule",
    "available", "availability", "deposit", "sign", "ready", "when can",
    "today", "tomorrow", "visit", "emi", "budget", "finalize", "close",
)
COLD_KEYWORDS = (
    "just looking", "just browsing", "curious", "maybe later", "not sure",
    "someday", "no rush", "just checking", "eventually", "no hurry",
)
HUMAN_KEYWORDS = (
    "legal", "lawyer", "advocate", "court", "complaint", "refund", "cheated",
    "fraud", "manager", "contract", "terms", "guarantee", "sue", "dispute",
    "angry", "unacceptable", "scam", "misled",
)

WARM_BASELINE_MASS = 1.5
HIT_WEIGHT = 2.0
BASE_MASS = 1.0
HUMAN_FLOOR = 0.10
HUMAN_PER_HIT = 0.25


class RuleProvider(Provider):
    name = "rule"
    is_llm = False

    def model_name(self, settings: "Settings") -> str:
        return "rule-based"

    def is_available(self, settings: "Settings") -> bool:
        return True  # no key, no network, never unavailable

    def generate_raw(self, message: str, settings: "Settings") -> dict:
        text = (message or "").lower()
        hot_hits = sum(kw in text for kw in HOT_KEYWORDS)
        cold_hits = sum(kw in text for kw in COLD_KEYWORDS)
        human_hits = sum(kw in text for kw in HUMAN_KEYWORDS)

        hot = BASE_MASS + HIT_WEIGHT * hot_hits
        cold = BASE_MASS + HIT_WEIGHT * cold_hits
        warm = WARM_BASELINE_MASS
        total = hot + warm + cold

        return {
            "hot": hot / total,
            "warm": warm / total,
            "cold": cold / total,
            "needs_human": min(1.0, HUMAN_FLOOR + HUMAN_PER_HIT * human_hits),
        }
