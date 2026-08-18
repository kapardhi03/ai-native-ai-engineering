"""
End-to-end checks across config, providers, belief and cache.

These are the ones that would catch a regression the unit tests would not: a
whole run behaving differently because two correct pieces disagree at the seam.
"""

from __future__ import annotations

import json
import math
import os

import pytest

CASES = [
    ("case-hot",   "What's the price and can I book a visit this weekend?"),
    ("case-warm",  "Just wanted to understand what options you have in this area."),
    ("case-cold",  "Just browsing for now, no rush, maybe later this year."),
    ("case-human", "Your agreement terms look wrong, I want a refund and a manager."),
]


def test_full_offline_run_produces_valid_beliefs(belief, make_settings):
    s = make_settings(provider="rule")
    for case_id, message in CASES:
        b, meta = belief.get_belief(case_id, message, settings=s)
        assert math.isclose(sum(b.readiness.values()), 1.0), case_id
        assert 0.0 <= b.needs_human <= 1.0, case_id
        assert meta.is_llm is False
    assert belief.cache_provenance(s) == {"rule": len(CASES)}


def test_full_llm_run_is_llm_only(belief, make_settings, fake_openai):
    fake_openai({"hot": .5, "warm": .3, "cold": .2, "needs_human": .1})
    s = make_settings(provider="openai", openai_api_key="sk-x",
                      allow_rule_fallback=False)
    for case_id, message in CASES:
        belief.get_belief(case_id, message, settings=s)
    belief.assert_llm_only(s)                       # must not raise
    assert belief.cache_provenance(s) == {"openai": len(CASES)}


def test_a_rerun_costs_nothing(belief, make_settings, fake_openai):
    """The whole point of caching: the second pass makes no API calls."""
    rec = fake_openai({"hot": .5, "warm": .3, "cold": .2, "needs_human": .1})
    s = make_settings(provider="openai", openai_api_key="sk-x")

    first = {cid: belief.get_belief(cid, m, settings=s)[0] for cid, m in CASES}
    calls_after_first = rec.call_count

    second = {cid: belief.get_belief(cid, m, settings=s)[0] for cid, m in CASES}
    assert rec.call_count == calls_after_first == len(CASES)
    assert first == second


def test_a_partial_outage_is_visible_in_the_cache(belief, make_settings,
                                                  fake_openai, fake_google):
    """The exact scenario the strict flag exists to prevent: an outage midway
    through leaves a cache whose calibration means nothing."""
    fake_openai({"hot": .5, "warm": .3, "cold": .2, "needs_human": .1})
    fake_google(error=RuntimeError("503"))
    s = make_settings(provider="auto", openai_api_key="sk-x", google_api_key="g-x")

    belief.get_belief(*CASES[0], settings=s)

    fake_openai(error=RuntimeError("401 key revoked"))          # outage begins
    belief.get_belief(*CASES[1], settings=s)

    assert belief.cache_provenance(s) == {"openai": 1, "rule": 1}
    with pytest.raises(belief.BeliefSourceError, match="not LLM-only"):
        belief.assert_llm_only(s)


def test_the_same_outage_under_strict_mode_stops_the_run(belief, make_settings,
                                                         fake_openai, fake_google):
    fake_openai({"hot": .5, "warm": .3, "cold": .2, "needs_human": .1})
    fake_google(error=RuntimeError("503"))
    s = make_settings(provider="auto", allow_rule_fallback=False,
                      openai_api_key="sk-x", google_api_key="g-x")

    belief.get_belief(*CASES[0], settings=s)
    fake_openai(error=RuntimeError("401 key revoked"))

    with pytest.raises(belief.BeliefSourceError):
        belief.get_belief(*CASES[1], settings=s)

    # The first, genuine belief survives; no keyword belief was written.
    assert belief.cache_provenance(s) == {"openai": 1}
    belief.assert_llm_only(s)


def test_working_directory_does_not_change_where_beliefs_land(
        belief, config, make_settings, fake_openai, tmp_path, monkeypatch):
    """The regression that would silently split the cache in two."""
    fake_openai({"hot": .5, "warm": .3, "cold": .2, "needs_human": .1})
    rel = "week1/deliverables/when-to-escalate/data/_test_cache.json"
    monkeypatch.setenv("BELIEF_CACHE_PATH", rel)
    monkeypatch.setenv("BELIEF_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")

    origin = os.getcwd()
    try:
        os.chdir(config.find_repo_root())
        a = config.load_settings(reload=True, load_env_files=False)
        os.chdir(tmp_path)
        b = config.load_settings(reload=True, load_env_files=False)
    finally:
        os.chdir(origin)

    assert a.cache_path == b.cache_path
    if a.cache_path.exists():
        a.cache_path.unlink()


def test_config_errors_surface_before_any_api_call(belief, config, monkeypatch,
                                                   fake_openai):
    """A contradictory setup must cost nothing."""
    rec = fake_openai({"hot": 1, "warm": 0, "cold": 0, "needs_human": 0})
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "false")
    with pytest.raises(config.ConfigError):
        config.load_settings(reload=True, load_env_files=False)
    assert rec.call_count == 0


def test_cache_is_readable_json_for_auditing(belief, make_settings, fake_openai):
    """The cache is audit data, so it has to be legible without this codebase."""
    fake_openai({"hot": .5, "warm": .3, "cold": .2, "needs_human": .1})
    s = make_settings(provider="openai", openai_api_key="sk-x")
    for cid, m in CASES:
        belief.get_belief(cid, m, settings=s)

    text = s.cache_path.read_text()
    assert "\n" in text, "cache should be indented, not one line"
    data = json.loads(text)
    assert list(data) == sorted(data), "keys should be sorted for stable diffs"
    for entry in data.values():
        assert entry["generated_at"].endswith("+00:00"), "timestamps must be UTC"


def test_belief_carries_no_provenance_into_the_policy(belief, make_settings, fake_openai):
    """Locked design: the policy reasons over the distribution and nothing else."""
    fake_openai({"hot": .5, "warm": .3, "cold": .2, "needs_human": .1})
    s = make_settings(provider="openai", openai_api_key="sk-x")
    b, meta = belief.get_belief("c", "hi", settings=s)
    assert set(b.to_dict()) == {"readiness", "needs_human"}
    assert not hasattr(b, "provider") and meta.provider == "openai"
