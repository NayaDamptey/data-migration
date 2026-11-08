"""
The standard data quality checks (validation/standard_checks.py):
  * all PASS on the clean baseline
  * all FAIL on the legacy DB, which has planted examples of every one (skipped without SQL Server)
  * every planted defect of a check's kind is caught by that check (not just by some rule)
"""

import csv

import pytest

from validation.baseline_rules import RULES
from validation.standard_checks import STANDARD_CHECKS, evaluate
from validation.validator import MANIFEST, load_csv_baseline


def _evaluate(con):
    results, ran = {}, set()
    for r in RULES:
        rows = con.execute(r.sql).fetchall()
        ran.add(r.id)
        if rows:
            results[r.id] = rows
    return evaluate(results, ran), results


def test_all_standard_checks_pass_on_clean_baseline():
    checks, _ = _evaluate(load_csv_baseline())
    failing = {c["name"]: c["violations"] for c in checks if c["status"] != "pass"}
    assert not failing, failing


@pytest.fixture(scope="module")
def legacy():
    pyodbc = pytest.importorskip("pyodbc")
    from validation.validator import load_sqlserver
    try:
        return _evaluate(load_sqlserver())
    except pyodbc.Error as e:
        pytest.skip(f"SQL Server not reachable: {e}")


def test_legacy_source_is_clean_outside_the_standard_checks(legacy):
    """Fixed at source: in the legacy DB, every rule that is not part of a standard check finds nothing."""
    _, results = legacy
    standard = set().union(*(c.rule_ids for c in STANDARD_CHECKS))
    extra = {rid: len(rows) for rid, rows in results.items() if rid not in standard}
    assert not extra, f"problems outside the standard checks: {extra}"


def test_every_standard_check_fails_on_legacy(legacy):
    checks, _ = legacy
    passing = [c["name"] for c in checks if c["status"] != "fail"]
    assert not passing, f"no planted problem found for: {passing}"


# planted-defect category -> the standard check that must catch it
EXPECTED = {
    "DUPLICATE_PERSON": "duplicate_people", "DUPLICATE_ASSOCIATE": "duplicate_people",
    "DUPLICATE_ACCOUNT": "duplicate_entities", "DUPLICATE_JOB": "duplicate_entities",
    "DUPLICATE_TRANSACTION": "duplicate_entities", "SPLIT_HISTORY": "duplicate_entities",
    "SOFT_DELETE_CONFLICT": "deleted_still_active", "ORPHAN_CONTACT": "orphaned_contacts",
    "PLACEMENT_ON_DELETED": "placements_on_deleted", "ORPHAN_DOCUMENT": "orphaned_documents", "ORPHAN_NOTE": "orphaned_notes",
}


def test_each_planted_defect_is_caught_by_its_standard_check(legacy):
    _, results = legacy
    table_of = {r.id: r.table for r in RULES}
    by_check = {c.id: {(table_of[rid], str(row[0])) for rid in c.rule_ids for row in results.get(rid, [])}
                for c in STANDARD_CHECKS}
    missed = [f"{m['defect_id']} {m['category']} {m['table']} pk={m['pk_value']} -> {EXPECTED[m['category']]}"
              for m in csv.DictReader(open(MANIFEST, encoding="utf-8")) if m["category"] in EXPECTED
              and (m["table"], m["pk_value"]) not in by_check[EXPECTED[m["category"]]]]
    assert not missed, "\n".join(missed)
