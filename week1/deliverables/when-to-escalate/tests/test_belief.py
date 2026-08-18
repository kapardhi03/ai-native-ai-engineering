"""The Belief object, its validation, and the provider policy."""

from __future__ import annotations

import math

import pytest


# --------------------------------------------------------------------------- #
# Belief — the pure object
# --------------------------------------------------------------------------- #

def test_readiness_sums_to_one(belief):
    b = belief.to_belief({"hot": 3, "warm": 1, "cold": 1, "needs_human": 0.2})
    assert math.isclose(sum(b.readiness.values()), 1.0)


@pytest.mark.parametrize("raw,expected", [
    ({"hot": 1, "warm": 1, "cold": 1}, 1 / 3),
    ({"hot": 2, "warm": 1, "cold": 1}, 0.5),
    ({"hot": 0.7, "warm": 0.2, "cold": 0.1}, 0.7),
    ({"hot": 70, "warm": 20, "cold": 10}, 0.7),      # percentages normalise
])
def test_normalisation(belief, raw, expected):
    assert math.isclose(belief.to_belief(raw).readiness["hot"], expected)


def test_negative_mass_is_clamped_not_propagated(belief):
    b = belief.to_belief({"hot": -5, "warm": 1, "cold": 1, "needs_human": 0})
    assert b.readiness["hot"] == 0.0
    assert all(v >= 0 for v in b.readiness.values())
    assert math.isclose(sum(b.readiness.values()), 1.0)


def test_zero_mass_becomes_uniform(belief):
    b = belief.to_belief({"hot": 0, "warm": 0, "cold": 0, "needs_human": 0.5})
    assert all(math.isclose(v, 1 / 3) for v in b.readiness.values())


def test_all_negative_becomes_uniform(belief):
    b = belief.to_belief({"hot": -1, "warm": -2, "cold": -3, "needs_human": 0})
    assert all(math.isclose(v, 1 / 3) for v in b.readiness.values())


def test_missing_keys_default_to_zero(belief):
    b = belief.to_belief({"hot": 1})
    assert math.isclose(b.readiness["hot"], 1.0) and b.needs_human == 0.0


def test_empty_dict_is_uniform(belief):
    assert all(math.isclose(v, 1 / 3)
               for v in belief.to_belief({}).readiness.values())


@pytest.mark.parametrize("value,expected", [
    (1.5, 1.0), (2, 1.0), (-0.3, 0.0), (-99, 0.0), (0.0, 0.0), (1.0, 1.0), (0.42, 0.42),
])
def test_needs_human_is_clamped_into_range(belief, value, expected):
    raw = {"hot": 1, "warm": 1, "cold": 1, "needs_human": value}
    assert belief.to_belief(raw).needs_human == expected


def test_numeric_strings_are_accepted(belief):
    """Some models return JSON numbers as strings."""
    b = belief.to_belief({"hot": "0.6", "warm": "0.3", "cold": "0.1",
                          "needs_human": "0.4"})
    assert math.isclose(b.readiness["hot"], 0.6) and math.isclose(b.needs_human, 0.4)


@pytest.mark.parametrize("junk", [
    {"hot": "not-a-number", "warm": 1, "cold": 1},
    {"hot": None, "warm": 1, "cold": 1},
    {"hot": [1], "warm": 1, "cold": 1},
    {"hot": {"a": 1}, "warm": 1, "cold": 1},
])
def test_non_numeric_values_raise(belief, junk):
    """Loud failure beats a silently wrong belief."""
    with pytest.raises((ValueError, TypeError)):
        belief.to_belief(junk)


def test_needs_human_is_independent_of_readiness(belief):
    """Locked design 0a. Normalising readiness must not touch needs_human."""
    b = belief.to_belief({"hot": 90, "warm": 5, "cold": 5, "needs_human": 0.9})
    assert math.isclose(sum(b.readiness.values()), 1.0)
    assert b.needs_human == 0.9


def test_round_trip_through_dict(belief):
    b = belief.to_belief({"hot": .5, "warm": .3, "cold": .2, "needs_human": .25})
    assert belief.Belief.from_dict(b.to_dict()) == b


def test_to_dict_has_the_documented_shape(belief):
    d = belief.to_belief({"hot": 1, "warm": 1, "cold": 1, "needs_human": .1}).to_dict()
    assert set(d) == {"readiness", "needs_human"}
    assert set(d["readiness"]) == {"hot", "warm", "cold"}


@pytest.mark.parametrize("raw,winner", [
    ({"hot": 3, "warm": 1, "cold": 1}, "hot"),
    ({"hot": 1, "warm": 3, "cold": 1}, "warm"),
    ({"hot": 1, "warm": 1, "cold": 3}, "cold"),
    ({"hot": 1, "warm": 1, "cold": 1}, "hot"),      # tie breaks in label order
])
def test_most_likely(belief, raw, winner):
    assert belief.to_belief(raw).most_likely() == winner


def test_belief_is_frozen(belief):
    b = belief.to_belief({"hot": 1, "warm": 1, "cold": 1})
    with pytest.raises(Exception):
        b.needs_human = 0.9


# --------------------------------------------------------------------------- #
# BeliefMeta
# --------------------------------------------------------------------------- #

def _meta(belief, provider):
    return belief.BeliefMeta(provider=provider, model="m", generated_at="t",
                             input_hash="h", from_cache=False)


@pytest.mark.parametrize("provider,is_llm", [
    ("openai", True), ("google", True), ("rule", False),
    ("unknown", False), ("", False),
])
def test_is_llm_reads_from_the_registry(belief, provider, is_llm):
    assert _meta(belief, provider).is_llm is is_llm


def test_meta_is_not_part_of_the_belief(belief):
    """The paper's belief is the distribution. Provenance must stay outside it."""
    b = belief.to_belief({"hot": 1, "warm": 1, "cold": 1, "needs_human": 0})
    assert set(vars(b)) == {"readiness", "needs_human"}


# --------------------------------------------------------------------------- #
# Provider policy
# --------------------------------------------------------------------------- #

GOOD = {"hot": .6, "warm": .3, "cold": .1, "needs_human": .2}
OTHER = {"hot": .1, "warm": .2, "cold": .7, "needs_human": .8}


def test_pinned_provider_is_used_verbatim(belief, make_settings, fake_openai, fake_google):
    fake_openai(GOOD)
    g = fake_google(OTHER)
    s = make_settings(provider="openai", openai_api_key="sk-x", google_api_key="g-x")
    _, meta = belief.get_belief("c", "hi", settings=s)
    assert meta.provider == "openai" and g.call_count == 0


def test_auto_prefers_openai(belief, make_settings, fake_openai, fake_google):
    fake_openai(GOOD)
    g = fake_google(OTHER)
    s = make_settings(provider="auto", openai_api_key="sk-x", google_api_key="g-x")
    _, meta = belief.get_belief("c", "hi", settings=s)
    assert meta.provider == "openai" and g.call_count == 0


def test_auto_falls_through_to_google(belief, make_settings, fake_openai, fake_google):
    o = fake_openai(error=RuntimeError("429"))
    fake_google(OTHER)
    s = make_settings(provider="auto", openai_api_key="sk-x", google_api_key="g-x")
    _, meta = belief.get_belief("c", "hi", settings=s)
    assert o.call_count == 1 and meta.provider == "google" and meta.is_llm


def test_provider_without_a_key_is_skipped_not_called(belief, make_settings,
                                                      fake_openai, fake_google):
    o = fake_openai(GOOD)
    fake_google(OTHER)
    s = make_settings(provider="auto", google_api_key="g-x")     # no OpenAI key
    _, meta = belief.get_belief("c", "hi", settings=s)
    assert o.call_count == 0 and meta.provider == "google"


def test_malformed_llm_reply_falls_through(belief, make_settings, fake_openai, fake_google):
    """Unparseable output is a provider failure like any other."""
    fake_openai(raw_text="I'm not going to answer that.")
    fake_google(OTHER)
    s = make_settings(provider="auto", openai_api_key="sk-x", google_api_key="g-x")
    _, meta = belief.get_belief("c", "hi", settings=s)
    assert meta.provider == "google"


# --------------------------------------------------------------------------- #
# The strict gate. This is what makes the calibration claim defensible.
# --------------------------------------------------------------------------- #

def test_strict_mode_raises_when_every_provider_fails(belief, make_settings,
                                                      fake_openai, fake_google):
    fake_openai(error=RuntimeError("401 unauthorized"))
    fake_google(error=RuntimeError("503 unavailable"))
    s = make_settings(provider="auto", allow_rule_fallback=False,
                      openai_api_key="sk-x", google_api_key="g-x")
    with pytest.raises(belief.BeliefSourceError, match="BELIEF_ALLOW_RULE_FALLBACK"):
        belief.get_belief("c", "hi", settings=s)


def test_strict_failure_names_every_provider_that_failed(belief, make_settings,
                                                         fake_openai, fake_google):
    fake_openai(error=RuntimeError("401 unauthorized"))
    fake_google(error=RuntimeError("503 unavailable"))
    s = make_settings(provider="auto", allow_rule_fallback=False,
                      openai_api_key="sk-x", google_api_key="g-x")
    with pytest.raises(belief.BeliefSourceError) as exc:
        belief.get_belief("c", "hi", settings=s)
    assert "401" in str(exc.value) and "503" in str(exc.value)


def test_strict_failure_writes_nothing(belief, make_settings, fake_openai, fake_google):
    """A failed strict run must not leave a partial cache behind."""
    fake_openai(error=RuntimeError("boom"))
    fake_google(error=RuntimeError("boom"))
    s = make_settings(provider="auto", allow_rule_fallback=False,
                      openai_api_key="sk-x", google_api_key="g-x")
    with pytest.raises(belief.BeliefSourceError):
        belief.get_belief("c", "hi", settings=s)
    assert not s.cache_path.exists()


def test_permissive_mode_degrades_but_flags_it(belief, make_settings,
                                               fake_openai, fake_google):
    fake_openai(error=RuntimeError("boom"))
    fake_google(error=RuntimeError("boom"))
    s = make_settings(provider="auto", allow_rule_fallback=True,
                      openai_api_key="sk-x", google_api_key="g-x")
    _, meta = belief.get_belief("c", "hi", settings=s)
    assert meta.provider == "rule" and meta.is_llm is False


def test_permissive_mode_warns_loudly(belief, make_settings, fake_openai,
                                      fake_google, caplog):
    fake_openai(error=RuntimeError("boom"))
    fake_google(error=RuntimeError("boom"))
    s = make_settings(provider="auto", allow_rule_fallback=True,
                      openai_api_key="sk-x", google_api_key="g-x")
    with caplog.at_level("WARNING"):
        belief.get_belief("c", "hi", settings=s)
    assert "NOT LLM-derived" in caplog.text


def test_strict_mode_with_no_keys_at_all_raises(belief, make_settings):
    """No key means the chain has nothing to try, so it must not reach keywords.

    Built with dataclasses.replace rather than with_overrides: the config
    validator rejects this combination at load time, so this exercises the
    belief-layer guard on its own.
    """
    import dataclasses
    s = dataclasses.replace(make_settings(provider="auto"), allow_rule_fallback=False)
    with pytest.raises(belief.BeliefSourceError):
        belief.get_belief("c", "hi", settings=s)


def test_no_keys_permissive_uses_keywords(belief, make_settings):
    _, meta = belief.get_belief("c", "price?", settings=make_settings(provider="auto"))
    assert meta.provider == "rule"
