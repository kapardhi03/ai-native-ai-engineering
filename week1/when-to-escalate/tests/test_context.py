"""
Conversation context.

Added because roughly a third of the authored archetypes are not decidable from
text alone. These tests cover the two properties that make context safe to add:
the cache fingerprint must notice a context change, and context prose must never
leak into a provider that inspects the text directly.
"""

from __future__ import annotations

import json

import pytest

PAYLOAD = {"hot": .5, "warm": .3, "cold": .2, "needs_human": .1}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def test_no_context_renders_the_bare_message(belief):
    from providers.prompt import render_observation
    assert render_observation("what is the price?") == "what is the price?"


def test_first_turn_is_labelled_as_such(belief):
    from providers.prompt import render_observation
    text = render_observation("hi", belief.CaseContext(turn_index=0))
    assert "first inbound message" in text and "hi" in text


def test_later_turn_states_its_position(belief):
    from providers.prompt import render_observation
    assert "turn 7" in render_observation("hi", belief.CaseContext(turn_index=7))


def test_repeats_are_only_mentioned_when_present(belief):
    from providers.prompt import render_observation
    assert "repetition" not in render_observation("hi", belief.CaseContext(turn_index=3))
    assert "repetition" in render_observation(
        "hi", belief.CaseContext(turn_index=3, repeat_count=5))


def test_the_message_survives_rendering_intact(belief):
    from providers.prompt import render_observation
    msg = "Can I get land papers? 🙏"
    assert msg in render_observation(msg, belief.CaseContext(turn_index=2, repeat_count=1))


# --------------------------------------------------------------------------- #
# The regression: context prose must not reach a substring matcher
# --------------------------------------------------------------------------- #

def test_context_does_not_change_the_keyword_belief(belief, make_settings, providers):
    """Regression. The rendered phrase "already received" contains "ready", a hot
    keyword, so rendering context into the rule provider turned a no-signal
    opener into a hot lead."""
    rule = providers.get_provider("rule")
    s = make_settings(provider="rule")
    bare = rule.generate_raw("Hi, can I get more info", s)
    with_ctx = rule.generate_raw("Hi, can I get more info", s,
                                 belief.CaseContext(turn_index=7, repeat_count=4))
    assert bare == with_ctx


def test_no_hot_keyword_fires_on_a_no_signal_opener(belief, make_settings, providers):
    raw = providers.get_provider("rule").generate_raw(
        "Hi, can I get more info", make_settings(provider="rule"),
        belief.CaseContext(turn_index=9, repeat_count=6))
    assert raw["hot"] < raw["warm"], "a template opener must not read as hot"


# --------------------------------------------------------------------------- #
# What the LLM providers actually receive
# --------------------------------------------------------------------------- #

def test_openai_is_sent_the_context(belief, make_settings, fake_openai, providers):
    rec = fake_openai(PAYLOAD)
    providers.get_provider("openai").generate_raw(
        "send photos", make_settings(openai_api_key="sk-x"),
        belief.CaseContext(turn_index=12, repeat_count=2))
    sent = rec.messages[0]
    assert "turn 12" in sent and "2 time(s)" in sent and "send photos" in sent


def test_google_is_sent_the_context(belief, make_settings, fake_google, providers):
    rec = fake_google(PAYLOAD)
    providers.get_provider("google").generate_raw(
        "send photos", make_settings(google_api_key="g-x"),
        belief.CaseContext(turn_index=4))
    assert "turn 4" in rec.messages[0]


def test_both_providers_receive_identical_wording(belief, make_settings,
                                                  fake_openai, fake_google, providers):
    """A wording difference between providers would be indistinguishable from a
    model difference in the results."""
    o = fake_openai(PAYLOAD)
    g = fake_google(PAYLOAD)
    ctx = belief.CaseContext(turn_index=5, repeat_count=1)
    providers.get_provider("openai").generate_raw(
        "hello", make_settings(openai_api_key="sk-x"), ctx)
    providers.get_provider("google").generate_raw(
        "hello", make_settings(google_api_key="g-x"), ctx)
    assert o.messages[0] in g.messages[0]


# --------------------------------------------------------------------------- #
# Cache honesty
# --------------------------------------------------------------------------- #

def test_hash_distinguishes_context(belief):
    bare = belief.input_hash("Hi")
    turn7 = belief.input_hash("Hi", belief.CaseContext(turn_index=7))
    repeat = belief.input_hash("Hi", belief.CaseContext(turn_index=7, repeat_count=3))
    assert len({bare, turn7, repeat}) == 3


def test_default_context_hashes_like_no_context(belief):
    """CaseContext() states turn 0, which is what an unannotated message means."""
    assert belief.input_hash("Hi", belief.CaseContext()) == belief.input_hash(
        "Hi", belief.CaseContext(turn_index=0, repeat_count=0))


def test_changed_context_is_detected_as_stale(belief, make_settings, fake_openai, caplog):
    """The property that makes context safe: context cannot drift silently while
    the cache still claims a match."""
    fake_openai(PAYLOAD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("c1", "Hi", context=belief.CaseContext(turn_index=0), settings=s)

    with caplog.at_level("WARNING"):
        belief.get_belief("c1", "Hi", context=belief.CaseContext(turn_index=9), settings=s)
    assert "DIFFERENT input" in caplog.text


def test_changed_context_can_force_a_regeneration(belief, make_settings, fake_openai):
    rec = fake_openai(PAYLOAD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("c1", "Hi", context=belief.CaseContext(turn_index=0), settings=s)
    belief.get_belief("c1", "Hi", context=belief.CaseContext(turn_index=9),
                      settings=s, refresh_on_message_change=True)
    assert rec.call_count == 2


def test_context_is_recorded_in_the_cache(belief, make_settings, fake_openai):
    fake_openai(PAYLOAD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("c1", "Hi", context=belief.CaseContext(turn_index=6, repeat_count=2),
                      settings=s)
    entry = json.loads(s.cache_path.read_text())["c1"]
    assert entry["context"] == {"turn_index": 6, "repeat_count": 2}


def test_absent_context_is_not_written(belief, make_settings, fake_openai):
    fake_openai(PAYLOAD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("c1", "Hi", settings=s)
    assert "context" not in json.loads(s.cache_path.read_text())["c1"]


def test_context_survives_a_cache_round_trip(belief, make_settings, fake_openai):
    fake_openai(PAYLOAD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    ctx = belief.CaseContext(turn_index=3, repeat_count=1)
    belief.get_belief("c1", "Hi", context=ctx, settings=s)
    _, meta = belief.get_belief("c1", "Hi", context=ctx, settings=s)
    assert meta.from_cache and meta.context == ctx.to_dict()


# --------------------------------------------------------------------------- #
# CaseContext itself
# --------------------------------------------------------------------------- #

def test_context_is_frozen(belief):
    ctx = belief.CaseContext(turn_index=1)
    with pytest.raises(Exception):
        ctx.turn_index = 2


def test_context_round_trips_through_dict(belief):
    ctx = belief.CaseContext(turn_index=4, repeat_count=2)
    assert belief.CaseContext.from_dict(ctx.to_dict()) == ctx


@pytest.mark.parametrize("value", [None, {}])
def test_empty_dict_yields_no_context(belief, value):
    assert belief.CaseContext.from_dict(value) is None


def test_partial_dict_fills_defaults(belief):
    assert belief.CaseContext.from_dict({"turn_index": 5}) == belief.CaseContext(
        turn_index=5, repeat_count=0)


def test_belief_still_carries_no_context(belief, make_settings, fake_openai):
    """Locked design: the policy reasons over the distribution, nothing else."""
    fake_openai(PAYLOAD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    b, _ = belief.get_belief("c", "Hi", context=belief.CaseContext(turn_index=3), settings=s)
    assert set(b.to_dict()) == {"readiness", "needs_human"}
