"""
The committed case set.

data/cases.json is the experiment's input and the thing the reported numbers are
computed over. These tests are the guard on it: a hand-edited label, a lost case,
or a split that stops being balanced would otherwise change published results
with nothing to notice.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

CASES_PATH = Path(__file__).resolve().parents[1] / "data" / "cases.json"

#: The distribution approved before the cases were written. Changing a number
#: here means the reported set changed shape, which is a decision, not a tweak.
APPROVED = {1: 10, 2: 8, 3: 8, 4: 16, 5: 12, 6: 8, 7: 8, 8: 8, 9: 6, 10: 10, 11: 6}
READINESS = {"hot", "warm", "cold"}


@pytest.fixture(scope="module")
def data():
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cases(data):
    return data["cases"]


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #

def test_file_exists_and_is_valid_json(data):
    assert data["schema_version"] == 1


def test_exactly_one_hundred_cases(cases, data):
    assert len(cases) == 100 == data["n_cases"]


def test_distribution_matches_what_was_approved(cases):
    assert dict(sorted(Counter(c["archetype"] for c in cases).items())) == APPROVED


def test_case_ids_are_unique(cases):
    ids = [c["case_id"] for c in cases]
    assert len(set(ids)) == len(ids)


def test_every_case_has_the_full_schema(cases):
    expected = {"case_id", "archetype", "archetype_name", "variant", "message",
                "context", "labels", "split", "notes"}
    for c in cases:
        assert set(c) == expected, c["case_id"]


def test_messages_are_non_empty(cases):
    for c in cases:
        assert c["message"].strip(), c["case_id"]


def test_archetype_names_are_consistent(cases):
    by_num = {}
    for c in cases:
        by_num.setdefault(c["archetype"], set()).add(c["archetype_name"])
    for num, names in by_num.items():
        assert len(names) == 1, f"archetype {num} has multiple names: {names}"


# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #

def test_readiness_labels_are_valid(cases):
    for c in cases:
        assert c["labels"]["readiness"] in READINESS, c["case_id"]


def test_needs_human_is_boolean(cases):
    for c in cases:
        assert isinstance(c["labels"]["needs_human"], bool), c["case_id"]


def test_no_readiness_class_is_degenerate(cases):
    """A class that barely appears cannot support a calibration claim."""
    counts = Counter(c["labels"]["readiness"] for c in cases)
    assert set(counts) == READINESS
    assert min(counts.values()) >= 20, counts


def test_the_majority_class_is_no_human(cases):
    """Guards the reason the set is weighted as it is: an always-escalate policy
    must not score well by default."""
    n_true = sum(c["labels"]["needs_human"] for c in cases)
    assert n_true == 42
    assert n_true < len(cases) - n_true


def test_both_awkward_combinations_are_present(cases):
    """Hot-and-needs-human and cold-and-needs-human are what break a policy that
    collapses readiness and needs_human into one score."""
    pairs = {(c["labels"]["readiness"], c["labels"]["needs_human"]) for c in cases}
    assert ("hot", True) in pairs
    assert ("cold", True) in pairs
    assert ("hot", False) in pairs


def test_the_hard_constraint_cases_exist(cases):
    """Archetype 5a: never send legal or land documents, at any price."""
    restricted = [c for c in cases if c["variant"] == "5a-restricted"]
    assert len(restricted) == 8
    assert all(c["labels"]["needs_human"] for c in restricted)


def test_public_legal_cases_are_not_escalations(cases):
    """Archetype 5b exists so the belief is tested on legal-sounding but public
    information. If these were all needs_human, archetype 5 would be trivial."""
    public = [c for c in cases if c["variant"] == "5b-public"]
    assert len(public) == 4
    assert not any(c["labels"]["needs_human"] for c in public)


# --------------------------------------------------------------------------- #
# Context
# --------------------------------------------------------------------------- #

def test_context_fields_are_non_negative_ints(cases):
    for c in cases:
        ctx = c["context"]
        assert set(ctx) == {"turn_index", "repeat_count"}
        assert isinstance(ctx["turn_index"], int) and ctx["turn_index"] >= 0, c["case_id"]
        assert isinstance(ctx["repeat_count"], int) and ctx["repeat_count"] >= 0, c["case_id"]


def test_context_dependent_archetypes_actually_carry_context(cases):
    """Archetypes 1, 3 and 11 are the evidence for research-file question 8. If
    their variants stopped differing in context, that evidence would vanish."""
    for archetype in (1, 3, 11):
        sub = [c for c in cases if c["archetype"] == archetype]
        signatures = {(c["context"]["turn_index"] > 0, c["context"]["repeat_count"] > 0)
                      for c in sub}
        assert len(signatures) > 1, f"archetype {archetype} has uniform context"


def test_blast_variant_is_marked_by_repetition(cases):
    blast = [c for c in cases if c["variant"] == "1b-blast"]
    assert len(blast) == 4
    assert all(c["context"]["repeat_count"] >= 3 for c in blast)


# --------------------------------------------------------------------------- #
# The split — reproducibility depends on this staying fixed and balanced
# --------------------------------------------------------------------------- #

def test_split_is_fifty_fifty(cases):
    assert Counter(c["split"] for c in cases) == {"dev": 50, "test": 50}


def test_split_values_are_valid(cases):
    assert {c["split"] for c in cases} == {"dev", "test"}


def test_every_archetype_appears_in_both_halves(cases):
    """The reason the split is stratified: with 100 cases a random draw could put
    an entire archetype in one half."""
    for archetype in APPROVED:
        halves = {c["split"] for c in cases if c["archetype"] == archetype}
        assert halves == {"dev", "test"}, f"archetype {archetype} only in {halves}"


def test_every_sub_variant_appears_in_both_halves(cases):
    for variant in {c["variant"] for c in cases}:
        halves = {c["split"] for c in cases if c["variant"] == variant}
        assert halves == {"dev", "test"}, f"variant {variant} only in {halves}"


def test_needs_human_is_balanced_across_halves(cases):
    """Otherwise one half could not show the cost asymmetry at all."""
    per_half = {s: sum(c["labels"]["needs_human"] for c in cases if c["split"] == s)
                for s in ("dev", "test")}
    assert per_half["dev"] == per_half["test"] == 21


def test_the_seed_is_recorded(data):
    """Without it the split cannot be regenerated and the set is not reproducible."""
    assert isinstance(data["seed"], int)


# --------------------------------------------------------------------------- #
# Public boundary
# --------------------------------------------------------------------------- #

def test_no_case_carries_contact_details(cases):
    """Synthetic messages must not look like scraped real ones."""
    import re
    phone = re.compile(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b")
    email = re.compile(r"[\w.\-]+@[\w\-]+\.\w+")
    for c in cases:
        assert not phone.search(c["message"]), c["case_id"]
        assert not email.search(c["message"]), c["case_id"]


def test_the_known_approximation_is_documented(data):
    """Decision 27: non-leads labelled cold. It must surface in the file itself,
    not only in the build log, or a reader of data/ would never see it."""
    assert "approximation" in data["note"].lower()
