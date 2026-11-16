"""Review by records (app/review.py). Needs the middle tier on SQL Server; skipped without it."""

import pytest


@pytest.fixture(scope="module")
def R():
    pytest.importorskip("pyodbc")
    from app import review
    try:
        review.records("candidates")
    except Exception as e:                                 # noqa: BLE001
        pytest.skip(f"SQL Server / middle tier not available: {e}")
    return review


def test_flagged_records_come_first(R):
    recs = R.records("candidates")["records"]
    flags = [r["flags"] for r in recs]
    assert flags == sorted(flags, reverse=True)


def test_record_has_fields_flags_and_related(R):
    first = R.records("placements")["records"][0]
    rec = R.record("placements", first["id"])
    assert rec["fields"] and rec["title"]
    assert {g["label"] for g in rec["related"]} >= {"Candidate", "Job", "Company"}


def test_orphan_contact_is_flagged_in_plain_words(R):
    flagged = [r for r in R.records("contacts", flagged_only=True)["records"]]
    assert flagged
    messages = [f["message"] for f in R.record("contacts", flagged[0]["id"])["flags"]]
    assert any("company" in m.lower() for m in messages)


def test_value_traces_back_to_its_source_row(R):
    cand = R.records("candidates")["records"][-1]["id"]
    src = R.source("candidates", cand, "first_name")
    assert src["sources"][0]["table"] == "Person" and src["sources"][0]["key"] == cand
    assert src["sources"][0]["raw"] == src["value"]


def test_unknown_entity_is_rejected(R):
    with pytest.raises(KeyError):
        R.records("nope")
