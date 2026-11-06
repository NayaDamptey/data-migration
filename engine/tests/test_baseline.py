"""
The clean baseline (sample_data/source/*.csv) must satisfy every data-quality rule.

One test per rule, so a failure names the exact rule and shows the offending keys.
Runs anywhere (DuckDB only, no SQL Server) — this is what CI runs.
"""

import pytest

from validation.baseline_rules import RULES
from validation.validator import load_csv_baseline


@pytest.fixture(scope="session")
def baseline():
    return load_csv_baseline()


@pytest.mark.parametrize("rule", RULES, ids=[r.id for r in RULES])
def test_rule_holds_on_clean_baseline(baseline, rule):
    rows = baseline.execute(rule.sql).fetchall()
    assert not rows, f"{rule.description}: {len(rows)} violation(s), e.g. {rows[:5]}"


def test_edge_cases_exist_and_are_dual_role(baseline):
    """The deliberate dual-role people really are both a contact and a candidate."""
    rows = baseline.execute("""
        SELECT e.person_id,
               e.person_id IN (SELECT Person_ID FROM Associates)  AS is_contact,
               e.person_id IN (SELECT Person_ID FROM Emp_Profile) AS is_candidate
        FROM edge_cases e""").fetchall()
    assert rows, "sql/source/edge_cases.csv is missing or empty"
    assert all(c and k for _, c, k in rows), rows
