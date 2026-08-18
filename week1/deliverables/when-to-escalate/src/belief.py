"""
belief.py — inbound message -> belief, with a reproducible cache.

Belief shape (locked design):
  - readiness: a probability distribution over {hot, warm, cold} that sums to 1
  - needs_human: a single probability in [0, 1], INDEPENDENT of readiness

These are two separate judgments, not one score. A hot lead can have low
needs_human; a cold lead can have high needs_human.

Belief source is a real LLM call, which is non-deterministic. To keep the
experiment reproducible, every case is run through the LLM exactly once and the
result is written to a JSON cache keyed by case_id. Policies read beliefs from
the cache and never call the LLM themselves, so both policies see identical
beliefs.

Provider order: OpenAI (1st) -> Google (2nd) -> rule-based fallback (always works,
so the pipeline runs offline / with no API key).

Public boundary: the prompt below is a generic, synthetic lead-qualification
prompt written for this experiment. It is NOT the production prompt, and it
carries no product name, client data, or real message content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

READINESS_LABELS = ("hot", "warm", "cold")

DEFAULT_CACHE_PATH = "data/belief_cache.json"


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GOOGLE_MODEL = "gemini-2.0-flash"

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


# --------------------------------------------------------------------------- #
# Belief type
# --------------------------------------------------------------------------- #

@dataclass
class Belief:
    """A validated belief. readiness always sums to 1; needs_human in [0, 1]."""
    readiness: dict          # {"hot": p, "warm": p, "cold": p}, sums to 1
    needs_human: float       # in [0, 1]

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


def _to_belief(raw: dict) -> Belief:
    """Turn a raw {hot,warm,cold,needs_human} dict into a validated Belief.

    Robust to LLM sloppiness: clamps negatives, normalizes the distribution,
    clamps needs_human. If the readiness mass is zero, falls back to uniform.
    """
    hot = max(0.0, float(raw.get("hot", 0.0)))
    warm = max(0.0, float(raw.get("warm", 0.0)))
    cold = max(0.0, float(raw.get("cold", 0.0)))
    s = hot + warm + cold
    if s <= 0.0:
        hot = warm = cold = 1.0 / 3.0
        s = 1.0
    readiness = {"hot": hot / s, "warm": warm / s, "cold": cold / s}

    nh = float(raw.get("needs_human", 0.0))
    nh = min(1.0, max(0.0, nh))
    return Belief(readiness=readiness, needs_human=nh)


# --------------------------------------------------------------------------- #
# JSON extraction (defensive against fenced / chatty LLM output)
# --------------------------------------------------------------------------- #

def _extract_json(text: str) -> dict:
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
# Providers. Each returns a RAW dict and raises on any failure.
# Imports are inside the functions so the module imports fine without the SDKs.
# --------------------------------------------------------------------------- #

def _call_openai(message: str, model: str) -> dict:
    from openai import OpenAI  # raises ImportError if not installed
    client = OpenAI()          # reads OPENAI_API_KEY from env
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


def _call_google(message: str, model: str) -> dict:
    # VERSION-SENSITIVE. This uses the newer unified `google-genai` SDK.
    # If you're on the older `google-generativeai`, the client/config surface
    # differs — confirm before trusting this call.
    from google import genai
    from google.genai import types
    client = genai.Client()  # reads GOOGLE_API_KEY / GEMINI_API_KEY from env
    resp = client.models.generate_content(
        model=model,
        contents=f"{SYSTEM_PROMPT}\n\nInbound message:\n{message}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return _extract_json(resp.text)


# keyword banks for the fallback. Deliberately crude — this is a floor, not a model.
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
    """Offline fallback. Keyword-scored belief so the pipeline never hard-fails.
    Not a serious model — it exists so a run completes with no API key."""
    m = message.lower()
    hot_hits = sum(kw in m for kw in _HOT_KW)
    cold_hits = sum(kw in m for kw in _COLD_KW)
    human_hits = sum(kw in m for kw in _HUMAN_KW)

    h = 1.0 + 2.0 * hot_hits
    c = 1.0 + 2.0 * cold_hits
    w = 1.5  # warm baseline mass
    total = h + w + c
    needs = min(1.0, 0.10 + 0.25 * human_hits)
    return {"hot": h / total, "warm": w / total, "cold": c / total, "needs_human": needs}


# --------------------------------------------------------------------------- #
# Provider chain
# --------------------------------------------------------------------------- #

def _generate_belief(
    message: str,
    provider: Optional[str],
    openai_model: str,
    google_model: str,
) -> tuple[Belief, str]:
    """Return (belief, provider_used).

    provider=None  -> chain: openai -> google -> rule (each failure falls through).
    provider set   -> use exactly that one. "openai"/"google" raise on failure;
                      "rule" always succeeds. Pin a provider for testing.
    """
    if provider == "rule":
        return _to_belief(_rule_based(message)), "rule"
    if provider == "openai":
        return _to_belief(_call_openai(message, openai_model)), "openai"
    if provider == "google":
        return _to_belief(_call_google(message, google_model)), "google"
    if provider is not None:
        raise ValueError(f"unknown provider: {provider!r}")

    # chain with fallback
    try:
        return _to_belief(_call_openai(message, openai_model)), "openai"
    except Exception as e:  # noqa: BLE001 - intentional fall-through
        logger.warning("OpenAI failed (%s); trying Google.", e)
    try:
        return _to_belief(_call_google(message, google_model)), "google"
    except Exception as e:  # noqa: BLE001
        logger.warning("Google failed (%s); falling back to rule-based.", e)
    return _to_belief(_rule_based(message)), "rule"


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def _msg_hash(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def _load_cache(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cache(path: str, cache: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False, sort_keys=True)


def get_belief(
    case_id: str,
    message: str,
    *,
    provider: Optional[str] = None,
    cache_path: str = DEFAULT_CACHE_PATH,
    openai_model: str = DEFAULT_OPENAI_MODEL,
    google_model: str = DEFAULT_GOOGLE_MODEL,
    force_refresh: bool = False,
    refresh_on_message_change: bool = False,
) -> Belief:
    """Get the belief for a case, using the cache when possible.

    Cache is keyed by case_id (per the locked design). The stored entry also
    keeps the message hash + audit fields (provider, model, timestamp) so drift
    is auditable.

    If a cached case_id is present but the message text has changed, that's a
    stale-cache situation: we warn loudly. By default we still return the cached
    belief (reproducibility wins); pass refresh_on_message_change=True to
    regenerate instead.
    """
    cache = _load_cache(cache_path)
    entry = cache.get(case_id)
    incoming_hash = _msg_hash(message)

    if entry is not None and not force_refresh:
        if entry.get("msg_hash") != incoming_hash:
            logger.warning(
                "Cache for case_id=%s was built from a DIFFERENT message "
                "(cached hash %s != incoming %s).",
                case_id, entry.get("msg_hash"), incoming_hash,
            )
            if not refresh_on_message_change:
                return Belief.from_dict(entry["belief"])
        else:
            return Belief.from_dict(entry["belief"])

    belief, provider_used = _generate_belief(
        message, provider, openai_model, google_model
    )
    model_used = {
        "openai": openai_model,
        "google": google_model,
        "rule": "rule-based",
    }[provider_used]

    cache[case_id] = {
        "belief": belief.to_dict(),
        "msg_hash": incoming_hash,
        "provider": provider_used,
        "model": model_used,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_cache(cache_path, cache)
    return belief


# --------------------------------------------------------------------------- #
# Offline smoke test:  python belief.py
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    samples = [
        ("demo-hot",  "What's the price and can I book a visit this weekend?"),
        ("demo-warm", "Just wanted to understand what options you have in this area."),
        ("demo-cold", "Just browsing for now, no rush, maybe later this year."),
        ("demo-human","Your agreement terms look wrong, I want to talk to a manager about a refund."),
    ]
    test_cache = "data/_smoke_belief_cache.json"
    if os.path.exists(test_cache):
        os.remove(test_cache)

    for cid, msg in samples:
        b = get_belief(cid, msg, provider="rule", cache_path=test_cache)
        r = b.readiness
        print(f"{cid:11s} hot={r['hot']:.2f} warm={r['warm']:.2f} "
              f"cold={r['cold']:.2f} needs_human={b.needs_human:.2f} "
              f"(sum={sum(r.values()):.3f})")