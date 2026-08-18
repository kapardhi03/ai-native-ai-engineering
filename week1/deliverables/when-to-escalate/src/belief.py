"""
belief.py — inbound message -> belief, with a reproducible cache.

Belief shape (locked design 0a):
  - readiness: a probability distribution over {hot, warm, cold} that sums to 1
  - needs_human: a single probability in [0, 1], INDEPENDENT of readiness

These are two separate judgments, not one score. A hot lead can have low
needs_human; a cold lead can have high needs_human.

`Belief` is deliberately the pure mathematical object — the same thing the paper
calls a belief, and nothing else. Where a number came from lives in a separate
`BeliefMeta`, so bookkeeping never contaminates the object the policy reasons
over. `get_belief()` returns the pair.

Belief source is a real LLM call, which is non-deterministic. To keep the
experiment reproducible, every case is run through the LLM exactly once and the
result is written to a JSON cache keyed by case_id. Policies read beliefs from
the cache and never call the LLM themselves, so both policies see identical
beliefs.

This module owns the belief, the provider *policy*, and the cache. It does not
own the providers themselves — those live in `providers/`, so adding one does
not mean editing this file. Nor does it own configuration; that is `config.py`.

The keyword fallback exists so the pipeline runs with no API key, but it is not
allowed to be invisible. When `allow_rule_fallback` is false, exhausting the real
providers raises `BeliefSourceError` and writes nothing, rather than quietly
producing keyword numbers that are indistinguishable from LLM numbers once
cached. Every cache entry records its provider either way.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:  # package import
    from .config import Settings, load_settings
    from .providers import RULE_PROVIDER, get_provider, llm_chain
except ImportError:  # run directly as a script
    from config import Settings, load_settings  # type: ignore
    from providers import RULE_PROVIDER, get_provider, llm_chain  # type: ignore

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

READINESS_LABELS = ("hot", "warm", "cold")


class BeliefSourceError(RuntimeError):
    """No permitted provider could produce a belief.

    Raised instead of silently degrading to keyword scoring when the run has
    declared that beliefs must come from a real LLM call.
    """


# --------------------------------------------------------------------------- #
# The belief itself — pure. No provenance, no bookkeeping.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Belief:
    """readiness always sums to 1; needs_human in [0, 1], independent of it."""

    readiness: dict          # {"hot": p, "warm": p, "cold": p}
    needs_human: float

    def to_dict(self) -> dict:
        return {
            "readiness": {k: float(self.readiness[k]) for k in READINESS_LABELS},
            "needs_human": float(self.needs_human),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Belief":
        return cls(
            readiness={k: float(d["readiness"][k]) for k in READINESS_LABELS},
            needs_human=float(d["needs_human"]),
        )

    def most_likely(self) -> str:
        """Highest-probability readiness state. Ties break in READINESS_LABELS order."""
        return max(READINESS_LABELS, key=lambda k: self.readiness[k])


# --------------------------------------------------------------------------- #
# Provenance — separate, so Belief stays the paper's object exactly.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BeliefMeta:
    """Where a belief came from. Never enters the decision arithmetic."""

    provider: str            # registry name: "openai" | "google" | "rule"
    model: str
    generated_at: str        # ISO-8601, UTC
    msg_hash: str
    from_cache: bool

    @property
    def is_llm(self) -> bool:
        """False means keyword-scored. Calibration claims require this to be True."""
        try:
            return get_provider(self.provider).is_llm
        except KeyError:
            return False     # unknown provider in an old cache: assume not LLM

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "generated_at": self.generated_at,
            "msg_hash": self.msg_hash,
        }


def to_belief(raw: dict) -> Belief:
    """Validate a raw {hot,warm,cold,needs_human} dict into a Belief.

    Robust to model sloppiness: clamps negatives, normalises the distribution,
    clamps needs_human into [0, 1]. Uniform if the readiness mass is zero.
    This is the only place the sum-to-1 invariant is established.
    """
    hot = max(0.0, float(raw.get("hot", 0.0)))
    warm = max(0.0, float(raw.get("warm", 0.0)))
    cold = max(0.0, float(raw.get("cold", 0.0)))
    total = hot + warm + cold
    if total <= 0.0:
        logger.warning("Provider returned zero readiness mass; falling back to uniform.")
        hot = warm = cold = 1.0 / 3.0
        total = 1.0
    readiness = {"hot": hot / total, "warm": warm / total, "cold": cold / total}

    needs_human = min(1.0, max(0.0, float(raw.get("needs_human", 0.0))))
    return Belief(readiness=readiness, needs_human=needs_human)


# --------------------------------------------------------------------------- #
# Provider policy. Which provider runs, and what happens when they all fail.
# --------------------------------------------------------------------------- #

def _generate_belief(message: str, settings: Settings) -> tuple[Belief, str]:
    """Return (belief, provider_name), honouring the configured provider policy."""
    choice = settings.provider

    if choice != "auto":
        provider = get_provider(choice)
        logger.debug("Pinned provider: %s.", provider.name)
        return to_belief(provider.generate_raw(message, settings)), provider.name

    failures: list[str] = []
    for provider in llm_chain():
        if not provider.is_available(settings):
            failures.append(f"{provider.name}: no API key")
            continue
        try:
            raw = provider.generate_raw(message, settings)
            return to_belief(raw), provider.name
        except Exception as exc:  # noqa: BLE001 - deliberate fall-through
            failures.append(f"{provider.name}: {type(exc).__name__}: {exc}")
            logger.warning("Provider %s failed (%s); trying the next.", provider.name, exc)

    if not settings.allow_rule_fallback:
        raise BeliefSourceError(
            "Every real LLM provider failed and BELIEF_ALLOW_RULE_FALLBACK=false, "
            "so no belief can be produced. Falling back to keyword scoring here "
            "would put numbers in the cache that are indistinguishable from LLM "
            "beliefs.\nProvider failures:\n  - " + "\n  - ".join(failures)
        )

    logger.warning(
        "Falling back to keyword scoring. This belief is NOT LLM-derived.\n"
        "Provider failures:\n  - %s", "\n  - ".join(failures),
    )
    rule = get_provider(RULE_PROVIDER)
    return to_belief(rule.generate_raw(message, settings)), rule.name


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def msg_hash(message: str) -> str:
    """Short, stable fingerprint of the message text."""
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cache(path: Path, cache: dict) -> None:
    """Write atomically: a crash mid-write must not destroy collected beliefs,
    each of which cost an API call."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


def get_belief(
    case_id: str,
    message: str,
    *,
    settings: Optional[Settings] = None,
    force_refresh: bool = False,
    refresh_on_message_change: bool = False,
) -> tuple[Belief, BeliefMeta]:
    """Get the belief for a case, using the cache when possible.

    Returns (belief, meta). The belief is the pure distribution; the meta says
    which provider produced it and whether it came from the cache. Check
    `meta.is_llm` before making any calibration claim.

    Cache is keyed by case_id (locked design 0d). The entry also stores the
    message hash and audit fields, so drift is detectable after the fact.

    If a cached case_id is present but the message text has changed, that is a
    stale-cache situation: warn loudly and, by default, still return the cached
    belief — reproducibility wins. Pass refresh_on_message_change=True to
    regenerate instead.
    """
    settings = settings or load_settings()
    cache = _load_cache(settings.cache_path)
    entry = cache.get(case_id)
    incoming_hash = msg_hash(message)

    if entry is not None and not force_refresh:
        cached_hash = entry.get("msg_hash")
        stale = cached_hash != incoming_hash
        if stale:
            logger.warning(
                "Cache for case_id=%s was built from a DIFFERENT message "
                "(cached hash %s != incoming %s).",
                case_id, cached_hash, incoming_hash,
            )
        if not stale or not refresh_on_message_change:
            logger.debug("Cache hit for case_id=%s (provider=%s).",
                         case_id, entry.get("provider"))
            return (
                Belief.from_dict(entry["belief"]),
                BeliefMeta(
                    provider=entry.get("provider", "unknown"),
                    model=entry.get("model", "unknown"),
                    generated_at=entry.get("generated_at", "unknown"),
                    msg_hash=cached_hash or "unknown",
                    from_cache=True,
                ),
            )

    logger.info("Cache miss for case_id=%s; generating a belief.", case_id)
    belief, provider_name = _generate_belief(message, settings)

    meta = BeliefMeta(
        provider=provider_name,
        model=get_provider(provider_name).model_name(settings),
        generated_at=datetime.now(timezone.utc).isoformat(),
        msg_hash=incoming_hash,
        from_cache=False,
    )

    cache[case_id] = {"belief": belief.to_dict(), **meta.to_dict()}
    _save_cache(settings.cache_path, cache)
    logger.info("Stored belief for case_id=%s (provider=%s).", case_id, provider_name)
    return belief, meta


def cache_provenance(settings: Optional[Settings] = None) -> dict[str, int]:
    """Count cache entries by provider.

    Run this before reporting calibration. A non-zero "rule" count means the
    cache is a mixture, and an ECE computed over it is not a statement about
    the LLM.
    """
    settings = settings or load_settings()
    counts: dict[str, int] = {}
    for entry in _load_cache(settings.cache_path).values():
        provider = entry.get("provider", "unknown")
        counts[provider] = counts.get(provider, 0) + 1
    return counts


def assert_llm_only(settings: Optional[Settings] = None) -> None:
    """Raise unless every cached belief came from a real model.

    The check that stands between a mixed cache and a calibration claim in the
    paper. Cheap to call; expensive to have skipped.
    """
    counts = cache_provenance(settings)
    non_llm = {
        name: n for name, n in counts.items()
        if not (name != "unknown" and _provider_is_llm(name))
    }
    if non_llm:
        raise BeliefSourceError(
            "Cache is not LLM-only, so calibration figures computed over it would "
            f"not describe the LLM. Non-LLM entries: {non_llm}. Full provenance: "
            f"{counts}. Regenerate with BELIEF_ALLOW_RULE_FALLBACK=false."
        )


def _provider_is_llm(name: str) -> bool:
    try:
        return get_provider(name).is_llm
    except KeyError:
        return False


# --------------------------------------------------------------------------- #
# Offline smoke test:  python belief.py
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

    settings = load_settings().with_overrides(
        provider=RULE_PROVIDER,
        allow_rule_fallback=True,
        cache_path=Path("/tmp/_smoke_belief_cache.json"),
    )
    if settings.cache_path.exists():
        settings.cache_path.unlink()

    samples = [
        ("demo-hot",   "What's the price and can I book a visit this weekend?"),
        ("demo-warm",  "Just wanted to understand what options you have in this area."),
        ("demo-cold",  "Just browsing for now, no rush, maybe later this year."),
        ("demo-human", "Your agreement terms look wrong, I want to talk to a manager about a refund."),
    ]
    for case_id, text in samples:
        b, meta = get_belief(case_id, text, settings=settings)
        r = b.readiness
        print(f"{case_id:11s} hot={r['hot']:.2f} warm={r['warm']:.2f} cold={r['cold']:.2f} "
              f"needs_human={b.needs_human:.2f} sum={sum(r.values()):.3f} "
              f"[{meta.provider}, llm={meta.is_llm}] -> {b.most_likely()}")

    print("\ncache provenance:", cache_provenance(settings))
    try:
        assert_llm_only(settings)
    except BeliefSourceError as exc:
        print(f"\nassert_llm_only correctly refuses this cache:\n  {str(exc).splitlines()[0]}")
