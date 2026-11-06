"""
Every defect planted in the legacy SQL Server DB (sql/source/defect_manifest.csv)
must be caught by at least one data-quality rule.

Needs the Cobaltdesk_Legacy database (python sample_data/build_source_db.py --load).
Skipped automatically when pyodbc or the server is unavailable (e.g. in CI).
"""

import os

import pytest

pyodbc = pytest.importorskip("pyodbc")

from validation.validator import DEFAULT_DB, DEFAULT_SERVER, load_sqlserver, run_rules, score  # noqa: E402

SERVER = os.getenv("SOURCE_SQL_SERVER", DEFAULT_SERVER)
DATABASE = os.getenv("SOURCE_SQL_DATABASE", DEFAULT_DB)


@pytest.fixture(scope="session")
def scored():
    try:
        con = load_sqlserver(SERVER, DATABASE)
    except pyodbc.Error as e:
        pytest.skip(f"SQL Server {SERVER}/{DATABASE} not reachable: {e}")
    return score(run_rules(con))


def test_every_planted_defect_is_detected(scored):
    missed = [f"{m['defect_id']} {m['category']} {m['table']}.{m['column']} pk={m['pk_value']}" for m in scored["missed"]]
    assert not missed, f"{len(missed)} planted defect(s) not detected:\n" + "\n".join(missed)


STANDARD_CATEGORIES = {
    "DUPLICATE_PERSON", "DUPLICATE_ASSOCIATE", "DUPLICATE_ACCOUNT", "DUPLICATE_JOB", "DUPLICATE_TRANSACTION",
    "SPLIT_HISTORY", "SOFT_DELETE_CONFLICT",
    "ORPHAN_CONTACT", "ORPHAN_CANDIDATE", "ORPHAN_DOCUMENT", "ORPHAN_NOTE",
}


def test_only_standard_check_problems_are_planted(scored):
    """Everything outside the standard checks is fixed at source; only those problems are planted."""
    categories = {m["category"] for m in scored["manifest"]}
    assert categories == STANDARD_CATEGORIES, categories ^ STANDARD_CATEGORIES
