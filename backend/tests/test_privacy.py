"""Personal data in what the API returns (app/privacy.py). Needs a built run; skipped without one."""

import pytest


@pytest.fixture(scope="module")
def apps():
    pytest.importorskip("presidio_analyzer")
    from app import engine_bridge, layers, privacy
    try:
        layers.rows("middle", "candidate_profiles", limit=1)
    except Exception as e:                                 # noqa: BLE001
        pytest.skip(f"No run available: {e}")
    return layers, privacy, engine_bridge


def test_sort_codes_are_masked_in_middle_tier_and_target(apps):
    layers, _, _ = apps
    mid = layers.rows("middle", "candidate_profiles", limit=20)["rows"]
    tgt = layers.rows("target", "Employment_Details", limit=20)["rows"]
    assert mid and all((r["sort_code"] or "").startswith("••-••-") for r in mid if r["sort_code"])
    assert tgt and all((r["SortCode"] or "").startswith("••-••-") for r in tgt if r["SortCode"])


def test_contact_details_stay_visible(apps):
    layers, _, _ = apps
    rows = layers.rows("middle", "candidates", limit=20)["rows"]
    assert any("@" in (r["email"] or "") for r in rows)


def test_searching_cannot_find_a_masked_value(apps):
    layers, _, _ = apps
    raw = layers.rows("middle", "candidate_profiles", limit=1, raw=True)["rows"][0]["sort_code"]
    assert layers.rows("middle", "candidate_profiles", q=raw)["matched"] == 0


def test_dates_of_birth_are_masked_in_data_quality(apps):
    _, _, eb = apps
    rows = eb.rule_rows("legacy", "dob.range")["rows"]
    assert rows and all("•" in r["detail"] for r in rows)
    assert all("•" in (r["record"] or {}).get("DOB", "•") for r in rows if r["record"] and r["record"].get("DOB"))
