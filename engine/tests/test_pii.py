"""Personal data detection, tagging and masking (privacy/pii.py). No database needed."""

import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE / "privacy"))
sys.path.insert(0, str(ENGINE / "transform"))
pytest.importorskip("presidio_analyzer")
sys.path.insert(0, str(ENGINE / "sample_data"))
import pii as P  # noqa: E402


@pytest.mark.parametrize("column,values,expected", [
    ("email", ["laura.mitchell3@yahoo.co.uk", "a.b@outlook.com"], "email"),
    ("contact_ref", ["laura.mitchell3@yahoo.co.uk", "a.b@outlook.com"], "email"),          # found by its values
    ("NI_number", ["WP963308B", "PN270948A"], "ni_number"),
    ("SortCode", ["11-27-76", "37-29-74"], "sort_code"),
    ("mobile", ["+44 7847 572790", "+44 7757 446928"], "phone"),
    ("DOB", ["1991-02-03"], "dob"),
    ("first_name", ["Laura"], "name"),
    ("postcode", ["CF14 2HU"], "address"),
    ("job_title", ["Senior Analyst", "Data Engineer"], None),
    ("email_ok", ["1", "0"], None),                                                         # a consent flag, not an email
    ("description", ["Purchase order for recruitment services"], None),
])
def test_suggestions(column, values, expected):
    got = P.suggest(column, values)
    assert (got or {}).get("category") == expected


def test_masking_keeps_only_the_last_two_characters():
    assert P.mask("WP963308B") == "•••••••8B"
    assert P.mask("11-27-76") == "••-••-76"
    assert P.mask(None) is None


def test_only_high_sensitivity_fields_are_masked():
    row = {"candidate_id": "301", "email": "a@b.com", "sort_code": "11-27-76"}
    out = P.mask_row(row, {"email": "email", "sort_code": "sort_code"})
    assert out["email"] == "a@b.com" and out["sort_code"] == "••-••-76" and out["candidate_id"] == "301"


def test_tags_flow_to_target_and_source():
    import build_dbt as B
    from build_source_db import load_schema
    middle, target = B.load_spec("middle"), B.load_spec("target")
    tags = {"candidate_profiles": {"sort_code": {"category": "sort_code", "status": "confirmed"}},
            "candidates": {"email": {"category": "email", "status": "confirmed"}}}
    tgt = P.target_categories(target, middle, tags)
    assert tgt["Employment_Details"]["SortCode"] == "sort_code"
    assert tgt["Comms"]["Value"] == "email"
    src = P.source_categories(middle, load_schema(), tags)
    assert src["Emp_Profile"]["SortCode"] == "sort_code" and src["Person"]["DOB"] == "dob"
