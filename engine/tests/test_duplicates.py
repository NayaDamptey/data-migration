"""
Duplicate review (validation/duplicates.py): pairs, decisions, and how the migration applies merges.
Uses a temporary decisions file, so the real mapping/merge_decisions.json is never touched.
"""

import sys
from pathlib import Path

import pytest

from validation import duplicates as D

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mapping"))

RESULTS = {
    "dup.person": [(10005, "duplicate of 502"), (10003, "duplicate of 351")],
    "dup.account": [(202, "duplicate of 134")],
    "dup.account.split_history": [(321, "on duplicate account 202")],
    "dup.timesheet_line": [(806, "copy of 12")],
}


@pytest.fixture(autouse=True)
def temp_decisions(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DECISIONS_FILE", tmp_path / "merge_decisions.json")


def test_pairs_are_built_from_rule_rows():
    pairs = D.pairs_from_results(RESULTS)
    assert {p["key"] for p in pairs} == {"person:502:10005", "person:351:10003", "company:134:202", "timesheet_line:12:806"}
    assert all(p["a"] != p["b"] for p in pairs)


def test_decided_pairs_stop_counting():
    D.save_decision("legacy", "person:502:10005", "merge", keep="a", fields={"DOB": "b"})
    D.save_decision("legacy", "company:134:202", "not_duplicate")
    left = D.apply_decisions(RESULTS, D.load_decisions("legacy"))
    assert left["dup.person"] == [(10003, "duplicate of 351")]
    assert "dup.account" not in left
    assert "dup.account.split_history" not in left          # its company pair was decided
    assert left["dup.timesheet_line"] == RESULTS["dup.timesheet_line"]


def test_undo_restores_the_pair():
    D.save_decision("legacy", "person:502:10005", "not_duplicate")
    D.save_decision("legacy", "person:502:10005", "undecided")
    assert D.apply_decisions(RESULTS, D.load_decisions("legacy")) == RESULTS


def test_merge_instructions_name_survivor_and_fields_from_duplicate():
    D.save_decision("legacy", "company:134:202", "merge", keep="b", fields={"Account_name": "a", "Website": "b"})
    (mg,) = D.merges("legacy")
    assert mg == {"table": "Accounts", "survivor": "202", "duplicate": "134", "take_from_duplicate": ["Account_name"]}


@pytest.mark.parametrize("args", [
    ("person:502:10005", "merge", None, None),               # merge needs keep
    ("person:502:10005", "merge", "a", {"NoSuchColumn": "a"}),
    ("robot:1:2", "not_duplicate", None, None),
    ("person:502:10005", "maybe", None, None),
])
def test_invalid_decisions_are_refused(args):
    with pytest.raises(ValueError):
        D.save_decision("legacy", *args)


def test_generator_applies_a_merge():
    D.save_decision("legacy", "company:134:202", "merge", keep="b", fields={"Account_name": "a"})
    import generate_sql as G
    from engine import load_mapping
    g = G.Generator(load_mapping())
    keymap = g.keymap()
    assert "source_key = N'202'" in keymap and "d.source_key = N'134'" in keymap      # 134 resolves to 202's new id
    company = next(m for m in load_mapping()["tables"] if m["target_table"] == "Company")
    script = g.load_script(company, 1)
    assert "DELETE FROM #stage WHERE CAST([__src_key] AS NVARCHAR(200)) IN (N'134')" in script
    assert "[CompanyName] = dp.[CompanyName]" in script                                   # name taken from 134
    assert "N'merged'" in script
