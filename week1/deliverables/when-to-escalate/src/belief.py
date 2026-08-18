"""
belief.py — inbound message -> belief, with a reproducible cache.

Belief shape (locked design 0a):
  - readiness: a probability distribution over {hot, warm, cold} that sums to 1
  - needs_human: a single probability in [0, 1], INDEPENDENT of readiness

These are two separate judgments, not one score. A hot lead can have low
needs_human; a cold lead can have high needs_human.

`Belief` is deliberately kept as the pure mathematical object — the same thing
the paper calls a belief, and nothing else. Everything about *where a number came
from* lives in a separate `BeliefMeta`, so bookkeeping never contaminates the
object the policy reasons over. `get_belief()` returns the pair.

Belief source is a real LLM call, which is non-deterministic. To keep the
experiment reproducible, every case is run through the LLM exactly once and the
result is written to a JSON cache keyed by case_id. Policies read beliefs from
the cache and never call the LLM themselves, so both policies see identical
beliefs.

Provider order: OpenAI -> Google -> rule-based keyword fallback.

The keyword fallback exists so the pipeline runs with no API key, but it is not
allowed to be invisible. When `allow_rule_fallback` is false, exhausting the real
providers raises `BeliefSourceError` instead of quietly producing keyword numbers
that are indistinguishable from LLM numbers once they are in the cache. Every
cache entry records which provider produced it either way.

All configuration comes from `config.py` (and therefore from `.env`). This module
holds no paths, no model names, and no keys of its own.

Public boundary: the prompt below is a generic, synthetic lead-qualification
prompt written for this experiment. It is NOT the production prompt, and it
carries no product name, client data, or real message content.
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
    from .config import ConfigError, Settings, load_settings
except ImportError:  # run directly as a script
    from config import ConfigError, Settings, load_settings  # type: ignore

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

READINESS_LABELS = ("hot", "warm", "cold")

SYSTEM_PROMPT = """You are a lead-qualification analyst for an inbound sales channel.
You read ONE inbound message from a prospective customer and estimate two separate things.

1) readiness — the prospect's buying readiness as a probability distribution over three
   states that sums to 1:
     - hot:  strong, concrete intent to move forward soon (asks price/availability to buy,
             wants to schedule or visit, ready to commit, urgency)
     - warm: genuine interest but still exploring (comparing options, general questions,
             no concrete next step yet)
     - cold: low or unclear intent (vague, browsing, early curiosity, or off-topic)

2) needs_human — a single probability in [0, 1], INDEPENDENT of readiness, that this
   message should be handled by a human rather than an automated agent. Raise it for:
   legal or contractual questions, complaints or dissatisfaction, negotiation, sensitive
   or emotional content, or anything where a wrong automated answer could cause real harm.
   A hot lead can have LOW needs_human; a cold lead can have HIGH needs_human. These are
   separate judgments — do not tie one to the other.

Return ONLY a JSON object with keys: hot, warm, cold, needs_human.
hot + warm + cold should sum to about 1. All values in [0, 1]. No prose, no explanation."""


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
        return max(READINESS_LABELS, key=lambda k: self.readiness[k])


# --------------------------------------------------------------------------- #
# Provenance — kept separate so Belief stays the paper's object exactly.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BeliefMeta:
    """Where a belief came from. Never used in the decision arithmetic."""

    provider: str            # "openai" | "google" | "rule"
    model: str
    generated_at: str        # ISO-8601, UTC
    msg_hash: str
    from_cache: bool

    @property
    def is_llm(self) -> bool:
        """False means keyword-scored. Calibration claims require this to be True."""
        return self.provider in ("openai", "google")

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "generated_at": self.generated_at,
            "msg_hash": self.msg_hash,
        }


def _to_belief(raw: dict) -> Belief:
    """Validate a raw {hot,warm,cold,needs_human} dict into a Belief.

    Robust to LLM sloppiness: clamps negatives, normalizes the distribution,
    clamps needs_human. Uniform if the readiness mass is zero.
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


def _extract_json(text: str) -> dict:
    """Defensive against fenced or chatty model output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


# --------------------------------------------------------------------------- #
# Providers. Each takes its key explicitly from Settings — no ambient env reads,
# so config.py stays the only place configuration is resolved.
# SDK imports are function-local so this module imports without them installed.
# --------------------------------------------------------------------------- #

def _call_openai(message: str, model: str, api_key: str) -> dict:
    from openai import OpenAI

    logger.debug("Calling OpenAI (model=%s).", model)
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return _extract_json(resp.choices[0].message.content)


def _call_google(message: str, model: str, api_key: str) -> dict:
    # VERSION-SENSITIVE. Uses the newer unified `google-genai` SDK. The older
    # `google-generativeai` package has a different client surface.
    from google import genai
    from google.genai import types

    logger.debug("Calling Google (model=%s).", model)
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=f"{SYSTEM_PROMPT}\n\nInbound message:\n{message}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return _extract_json(resp.text)


# Keyword banks for the fallback. Deliberately crude — this is a floor, not a model.
_HOT_KW = (
    "price", "cost", "how much", "buy", "purchase", "book", "schedule",
    "available", "availability", "deposit", "sign", "ready", "when can",
    "today", "tomorrow", "visit", "emi", "budget", "finalize", "close",
)
_COLD_KW = (
    "just looking", "just browsing", "curious", "maybe later", "not sure",
    "someday", "no rush", "just checking", "eventually", "no hurry",
)
_HUMAN_KW = (
    "legal", "lawyer", "advocate", "court", "complaint", "refund", "cheated",
    "fraud", "manager", "contract", "terms", "guarantee", "sue", "dispute",
    "angry", "unacceptable", "scam", "misled",
)


def _rule_based(message: str) -> dict:
    """Offline keyword scoring. Not a serious model — it exists so a run
    completes with no API key. Never counted as an LLM belief."""
    m = message.lower()
    hot_hits = sum(kw in m for kw in _HOT_KW)
    cold_hits = sum(kw in m for kw in _COLD_KW)
    human_hits = sum(kw in m for kw in _HUMAN_KW)

    h = 1.0 + 2.0 * hot_hits
    c = 1.0 + 2.0 * cold_hits
    w = 1.5  # warm baseline mass
    total = h + w + c
    return {
        "hot": h / total,
        "warm": w / total,
        "cold": c / total,
        "needs_human": min(1.0, 0.10 + 0.25 * human_hits),
    }


# --------------------------------------------------------------------------- #
# Provider chain
# --------------------------------------------------------------------------- #

def _model_for(provider: str, settings: Settings) -> str:
    return {
        "openai": settings.openai_model,
        "google": settings.google_model,
        "rule": "rule-based",
    }[provider]


def _generate_belief(message: str, settings: Settings) -> tuple[Belief, str]:
    """Return (belief, provider_used), honouring the configured provider policy."""
    provider = settings.provider

    if provider == "rule":
        return _to_belief(_rule_based(message)), "rule"
    if provider == "openai":
        key = settings.require_key("openai")
        return _to_belief(_call_openai(message, settings.openai_model, key)), "openai"
    if provider == "google":
        key = settings.require_key("google")
        return _to_belief(_call_google(message, settings.google_model, key)), "google"

    # provider == "auto": try each real provider that has a key, in order.
    failures: list[str] = []
    for name, fn, model in (
        ("openai", _call_openai, settings.openai_model),
        ("google", _call_google, settings.google_model),
    ):
        if not settings.has_key(name):
            failures.append(f"{name}: no API key")
            continue
        try:
            return _to_belief(fn(message, model, settings.require_key(name))), name
        except Exception as exc:  # noqa: BLE001 - intentional fall-through
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            logger.warning("Provider %s failed (%s); trying the next one.", name, exc)

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
    return _to_belief(_rule_based(message)), "rule"


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def _msg_hash(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)  # atomic: a crash mid-write cannot corrupt the cache


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
    cache_path = settings.cache_path
    cache = _load_cache(cache_path)
    entry = cache.get(case_id)
    incoming_hash = _msg_hash(message)

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
    belief, provider_used = _generate_belief(message, settings)

    meta = BeliefMeta(
        provider=provider_used,
        model=_model_for(provider_used, settings),
        generated_at=datetime.now(timezone.utc).isoformat(),
        msg_hash=incoming_hash,
        from_cache=False,
    )

    cache[case_id] = {"belief": belief.to_dict(), **meta.to_dict()}
    _save_cache(cache_path, cache)
    logger.info("Stored belief for case_id=%s (provider=%s).", case_id, provider_used)
    return belief, meta


def cache_provenance(settings: Optional[Settings] = None) -> dict[str, int]:
    """Count cache entries by provider.

    The check to run before reporting calibration: any non-zero "rule" count
    means the cache is a mixture, and an ECE computed over it is not a
    statement about the LLM.
    """
    settings = settings or load_settings()
    counts: dict[str, int] = {}
    for entry in _load_cache(settings.cache_path).values():
        provider = entry.get("provider", "unknown")
        counts[provider] = counts.get(provider, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# Offline smoke test:  python belief.py
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")

    settings = load_settings().with_overrides(
        provider="rule",
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
    for case_id, msg in samples:
        b, meta = get_belief(case_id, msg, settings=settings)
        r = b.readiness
        print(f"{case_id:11s} hot={r['hot']:.2f} warm={r['warm']:.2f} cold={r['cold']:.2f} "
              f"needs_human={b.needs_human:.2f} sum={sum(r.values()):.3f} "
              f"[{meta.provider}, llm={meta.is_llm}]")

    print("\ncache provenance:", cache_provenance(settings))
