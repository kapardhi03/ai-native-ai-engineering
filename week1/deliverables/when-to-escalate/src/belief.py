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
    from .providers.prompt import render_observation
except ImportError:  # run directly as a script
    from config import Settings, load_settings  # type: ignore
    from providers import RULE_PROVIDER, get_provider, llm_chain  # type: ignore
    from providers.prompt import render_observation  # type: ignore

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

READINESS_LABELS = ("hot", "warm", "cold")


@dataclass(frozen=True)
class CaseContext:
    """Where in a conversation a message arrived.

    Added because roughly a third of the authored archetypes are not decidable
    from text alone: the same words mean different things on turn 0 and turn 12,
    and a template opener repeated many times is a blast rather than a lead.
    This is the evidence for research-file question 8.

    Deliberately minimal. Only what the archetypes actually needed — adding
    fields the case set does not exercise would be untested surface.
    """

    turn_index: int = 0        # 0 = first inbound message of the conversation
    repeat_count: int = 0      # times this same text was already seen from this lead

    def describe_lines(self) -> list[tuple[str, str]]:
        """Label/value pairs for the prompt. Omits fields at their default, so a
        first message is not padded with noise the model has to ignore."""
        lines: list[tuple[str, str]] = []
        if self.turn_index == 0:
            lines.append(("position", "first inbound message of the conversation"))
        else:
            lines.append(("position", f"turn {self.turn_index} of an ongoing conversation"))
        if self.repeat_count:
            lines.append(("repetition",
                          f"this same text was already received {self.repeat_count} time(s)"))
        return lines

    def to_dict(self) -> dict:
        return {"turn_index": self.turn_index, "repeat_count": self.repeat_count}

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> Optional["CaseContext"]:
        if not d:
            return None
        return cls(turn_index=int(d.get("turn_index", 0)),
                   repeat_count=int(d.get("repeat_count", 0)))


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
    input_hash: str          # fingerprint of message AND context together
    from_cache: bool
    context: Optional[dict] = None

    @property
    def is_llm(self) -> bool:
        """False means keyword-scored. Calibration claims require this to be True."""
        try:
            return get_provider(self.provider).is_llm
        except KeyError:
            return False     # unknown provider in an old cache: assume not LLM

    def to_dict(self) -> dict:
        d = {
            "provider": self.provider,
            "model": self.model,
            "generated_at": self.generated_at,
            "input_hash": self.input_hash,
        }
        if self.context is not None:
            d["context"] = self.context
        return d


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

def _generate_belief(
    message: str, settings: Settings, context: Optional[CaseContext] = None,
) -> tuple[Belief, str]:
    """Return (belief, provider_name), honouring the configured provider policy.

    Message and context are passed through separately; each provider decides how
    to combine them. Rendering here instead would force the keyword provider to
    scan generated context prose.
    """
    choice = settings.provider

    if choice != "auto":
        provider = get_provider(choice)
        logger.debug("Pinned provider: %s.", provider.name)
        return to_belief(provider.generate_raw(message, settings, context)), provider.name

    failures: list[str] = []
    for provider in llm_chain():
        if not provider.is_available(settings):
            failures.append(f"{provider.name}: no API key")
            continue
        try:
            raw = provider.generate_raw(message, settings, context)
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
    return to_belief(rule.generate_raw(message, settings, context)), rule.name


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def input_hash(message: str, context: Optional[CaseContext] = None) -> str:
    """Fingerprint of exactly what the provider was shown.

    Hashes the rendered observation rather than the raw message, so a case whose
    context changed is detected as changed. Hashing the message alone would let
    context drift silently while the cache still reported a match.
    """
    return hashlib.sha256(
        render_observation(message, context).encode("utf-8")
    ).hexdigest()[:16]


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
    context: Optional[CaseContext] = None,
    settings: Optional[Settings] = None,
    force_refresh: bool = False,
    refresh_on_message_change: bool = False,
) -> tuple[Belief, BeliefMeta]:
    """Get the belief for a case, using the cache when possible.

    Returns (belief, meta). The belief is the pure distribution; the meta says
    which provider produced it and whether it came from the cache. Check
    `meta.is_llm` before making any calibration claim.

    `context` is optional conversation position. The belief is a pure function of
    (message, context): both are rendered into one observation, and that
    observation is what gets hashed, so the cache cannot report a match when the
    context has changed underneath it.

    Cache is keyed by case_id (locked design 0d). The entry stores the input hash
    and audit fields, so drift is detectable after the fact.

    If a cached case_id is present but the input has changed, that is a
    stale-cache situation: warn loudly and, by default, still return the cached
    belief — reproducibility wins. Pass refresh_on_message_change=True to
    regenerate instead.
    """
    settings = settings or load_settings()
    cache = _load_cache(settings.cache_path)
    entry = cache.get(case_id)
    incoming_hash = input_hash(message, context)

    if entry is not None and not force_refresh:
        cached_hash = entry.get("input_hash")
        stale = cached_hash != incoming_hash
        if stale:
            logger.warning(
                "Cache for case_id=%s was built from DIFFERENT input "
                "(cached hash %s != incoming %s). Message or context changed.",
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
                    input_hash=cached_hash or "unknown",
                    from_cache=True,
                    context=entry.get("context"),
                ),
            )

    logger.info("Cache miss for case_id=%s; generating a belief.", case_id)
    belief, provider_name = _generate_belief(message, settings, context)

    meta = BeliefMeta(
        provider=provider_name,
        model=get_provider(provider_name).model_name(settings),
        generated_at=datetime.now(timezone.utc).isoformat(),
        input_hash=incoming_hash,
        from_cache=False,
        context=context.to_dict() if context is not None else None,
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

    # The smoke test is explicitly an offline exercise, so it opts into the
    # keyword floor rather than inheriting whatever the environment says. Set
    # before load_settings() because strict mode is now the default and a
    # keyless machine would otherwise fail validation here.
    os.environ.setdefault("BELIEF_PROVIDER", RULE_PROVIDER)
    os.environ.setdefault("BELIEF_ALLOW_RULE_FALLBACK", "true")

    settings = load_settings(reload=True).with_overrides(
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
