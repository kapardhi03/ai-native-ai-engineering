"""The belief cache: keying, staleness, atomicity, and provenance.

The cache is what makes both policies score identical beliefs, so its failure
modes are the ones that would quietly invalidate a result.
"""

from __future__ import annotations

import json

import pytest

GOOD = {"hot": .6, "warm": .3, "cold": .1, "needs_human": .2}
OTHER = {"hot": .1, "warm": .2, "cold": .7, "needs_human": .8}


# --------------------------------------------------------------------------- #
# Basic read-through
# --------------------------------------------------------------------------- #

def test_miss_then_hit(belief, make_settings, fake_openai):
    rec = fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")

    b1, m1 = belief.get_belief("case-1", "price?", settings=s)
    assert rec.call_count == 1 and m1.from_cache is False

    b2, m2 = belief.get_belief("case-1", "price?", settings=s)
    assert rec.call_count == 1, "a cache hit must not call the API again"
    assert m2.from_cache is True and b2 == b1


def test_cache_file_is_created_with_the_documented_shape(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x", openai_model="gpt-test")
    belief.get_belief("case-1", "price?", settings=s)

    entry = json.loads(s.cache_path.read_text())["case-1"]
    assert set(entry) == {"belief", "provider", "model", "generated_at", "msg_hash"}
    assert entry["provider"] == "openai" and entry["model"] == "gpt-test"
    assert set(entry["belief"]["readiness"]) == {"hot", "warm", "cold"}


def test_parent_directories_are_created(belief, make_settings, tmp_path, fake_openai):
    fake_openai(GOOD)
    target = tmp_path / "deep" / "nested" / "cache.json"
    s = make_settings(provider="openai", openai_api_key="sk-x", cache_path=target)
    belief.get_belief("c", "hi", settings=s)
    assert target.exists()


def test_distinct_case_ids_are_independent(belief, make_settings, fake_openai):
    rec = fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("a", "one", settings=s)
    belief.get_belief("b", "two", settings=s)
    assert rec.call_count == 2
    assert set(json.loads(s.cache_path.read_text())) == {"a", "b"}


def test_existing_entries_survive_a_new_write(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    for i in range(5):
        belief.get_belief(f"case-{i}", f"message {i}", settings=s)
    assert len(json.loads(s.cache_path.read_text())) == 5


# --------------------------------------------------------------------------- #
# Identical beliefs for every reader — the guarantee the cache exists for
# --------------------------------------------------------------------------- #

def test_two_readers_see_identical_beliefs(belief, make_settings, fake_openai):
    """Stands in for the cost-aware policy and the baseline."""
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("case-1", "price?", settings=s)

    policy_a, _ = belief.get_belief("case-1", "price?", settings=s)
    policy_b, _ = belief.get_belief("case-1", "price?", settings=s)
    assert policy_a == policy_b


def test_a_cached_case_never_calls_a_provider_again(belief, make_settings, fake_openai):
    rec = fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("case-1", "price?", settings=s)
    for _ in range(10):
        belief.get_belief("case-1", "price?", settings=s)
    assert rec.call_count == 1


# --------------------------------------------------------------------------- #
# Staleness — same case_id, different message
# --------------------------------------------------------------------------- #

def test_changed_message_warns_but_keeps_the_cached_belief(belief, make_settings,
                                                           fake_openai, caplog):
    """Reproducibility wins by default: the cached belief is what was scored."""
    rec = fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    first, _ = belief.get_belief("case-1", "original text", settings=s)

    with caplog.at_level("WARNING"):
        second, meta = belief.get_belief("case-1", "EDITED text", settings=s)

    assert second == first and meta.from_cache is True
    assert rec.call_count == 1
    assert "DIFFERENT message" in caplog.text


def test_refresh_on_message_change_regenerates(belief, make_settings, fake_openai):
    rec = fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("case-1", "original", settings=s)
    _, meta = belief.get_belief("case-1", "edited", settings=s,
                                refresh_on_message_change=True)
    assert rec.call_count == 2 and meta.from_cache is False


def test_refresh_flag_does_nothing_when_the_message_is_unchanged(belief, make_settings,
                                                                 fake_openai):
    rec = fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("case-1", "same", settings=s)
    _, meta = belief.get_belief("case-1", "same", settings=s,
                                refresh_on_message_change=True)
    assert rec.call_count == 1 and meta.from_cache is True


def test_force_refresh_always_regenerates(belief, make_settings, fake_openai):
    rec = fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("case-1", "same", settings=s)
    _, meta = belief.get_belief("case-1", "same", settings=s, force_refresh=True)
    assert rec.call_count == 2 and meta.from_cache is False


def test_force_refresh_overwrites_the_stored_entry(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("case-1", "hi", settings=s)
    fake_openai(OTHER)
    belief.get_belief("case-1", "hi", settings=s, force_refresh=True)
    stored = json.loads(s.cache_path.read_text())["case-1"]["belief"]
    assert stored["readiness"]["cold"] == pytest.approx(.7)


# --------------------------------------------------------------------------- #
# Message hashing
# --------------------------------------------------------------------------- #

def test_hash_is_stable_and_message_sensitive(belief):
    assert belief.msg_hash("hello") == belief.msg_hash("hello")
    assert belief.msg_hash("hello") != belief.msg_hash("hello ")
    assert belief.msg_hash("Hello") != belief.msg_hash("hello")


@pytest.mark.parametrize("message", ["", "😀", "ünïcode", "a" * 50_000, "\n\t"])
def test_hash_handles_awkward_input(belief, message):
    assert len(belief.msg_hash(message)) == 16


# --------------------------------------------------------------------------- #
# Durability
# --------------------------------------------------------------------------- #

def test_write_is_atomic_and_leaves_no_temp_file(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("c", "hi", settings=s)
    leftovers = list(s.cache_path.parent.glob("*.tmp"))
    assert leftovers == [], f"temp files left behind: {leftovers}"


def test_a_failed_write_does_not_destroy_existing_beliefs(belief, make_settings,
                                                          fake_openai, monkeypatch):
    """The reason writes are atomic: each cached belief cost an API call."""
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("case-1", "first", settings=s)
    before = s.cache_path.read_text()

    def explode(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr(belief.os, "replace", explode)

    with pytest.raises(OSError):
        belief.get_belief("case-2", "second", settings=s)

    assert s.cache_path.read_text() == before, "the previous cache must survive"
    assert json.loads(s.cache_path.read_text())["case-1"]


def test_unicode_survives_a_round_trip(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("café-😀", "¿cuánto cuesta?", settings=s)
    assert "café-😀" in json.loads(s.cache_path.read_text())


def test_corrupt_cache_fails_loudly(belief, make_settings, fake_openai):
    """Silently starting over would mean re-paying for every belief."""
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    s.cache_path.parent.mkdir(parents=True, exist_ok=True)
    s.cache_path.write_text("{ this is not json")
    with pytest.raises(json.JSONDecodeError):
        belief.get_belief("c", "hi", settings=s)


def test_entry_missing_optional_fields_still_reads(belief, make_settings):
    """An older cache format must not crash a run."""
    s = make_settings()
    s.cache_path.parent.mkdir(parents=True, exist_ok=True)
    s.cache_path.write_text(json.dumps({
        "old": {"belief": {"readiness": {"hot": .5, "warm": .3, "cold": .2},
                           "needs_human": .1},
                "msg_hash": belief.msg_hash("hi")}}))
    b, meta = belief.get_belief("old", "hi", settings=s)
    assert b.readiness["hot"] == .5
    assert meta.provider == "unknown" and meta.is_llm is False


# --------------------------------------------------------------------------- #
# Provenance — the guard on the calibration claim
# --------------------------------------------------------------------------- #

def test_provenance_counts_by_provider(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("a", "1", settings=s)
    belief.get_belief("b", "2", settings=s)
    assert belief.cache_provenance(s) == {"openai": 2}


def test_provenance_of_an_absent_cache_is_empty(belief, make_settings):
    assert belief.cache_provenance(make_settings()) == {}


def test_provenance_exposes_a_mixture(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("llm", "price?", settings=s)
    belief.get_belief("kw", "price?", settings=s.with_overrides(provider="rule"))
    assert belief.cache_provenance(s) == {"openai": 1, "rule": 1}


def test_assert_llm_only_passes_on_a_clean_cache(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("a", "1", settings=s)
    belief.assert_llm_only(s)


def test_assert_llm_only_rejects_a_mixture(belief, make_settings, fake_openai):
    fake_openai(GOOD)
    s = make_settings(provider="openai", openai_api_key="sk-x")
    belief.get_belief("llm", "price?", settings=s)
    belief.get_belief("kw", "price?", settings=s.with_overrides(provider="rule"))
    with pytest.raises(belief.BeliefSourceError, match="not LLM-only"):
        belief.assert_llm_only(s)


def test_assert_llm_only_rejects_an_unknown_provider(belief, make_settings):
    s = make_settings()
    s.cache_path.parent.mkdir(parents=True, exist_ok=True)
    s.cache_path.write_text(json.dumps({
        "x": {"belief": {"readiness": {"hot": 1, "warm": 0, "cold": 0},
                         "needs_human": 0}, "provider": "mystery"}}))
    with pytest.raises(belief.BeliefSourceError):
        belief.assert_llm_only(s)


def test_assert_llm_only_passes_on_an_empty_cache(belief, make_settings):
    belief.assert_llm_only(make_settings())
