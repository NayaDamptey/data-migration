"""The middle tier and target scripts (mapping/tiers.py), run on SQL Server.

Skipped when SQL Server isn't reachable (e.g. on CI)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mapping"))
import tiers as T  # noqa: E402

# every link in the target that must point at a loaded row: (child table, column, parent table, parent key, extra filter)
LINKS = [
    ("Placements", "ApplicantID", "Applicant", "ApplicantID", ""),
    ("Placements", "PositionID", "Position", "ID", ""),
    ("Position", "CompanyID", "Company", "ID", ""),
    ("Contact", "CompanyID", "Company", "ID", ""),
    ("Comms", "ObjectID", "Applicant", "ApplicantID", ""),
    ("Notes", "ApplicantID", "Applicant", "ApplicantID", ""),
    ("Notes", "ContactID", "Contact", "ID", ""),
    ("Notes", "CompanyID", "Company", "ID", ""),
    ("Notes", "PositionID", "Position", "ID", ""),
    ("Position_Applicant", "ApplicantID", "Applicant", "ApplicantID", ""),
    ("Position_Applicant", "PositionID", "Position", "ID", ""),
    ("Work_History", "ApplicationID", "Applicant", "ApplicantID", ""),
    ("References", "ApplicantID", "Applicant", "ApplicantID", ""),
    ("Employment_Details", "ApplicantID", "Applicant", "ApplicantID", ""),
    ("ApplicantAttachment", "ApplicantID", "Applicant", "ApplicantID", ""),
    ("ContactAttachment", "ContactID", "Contact", "ID", ""),
    ("PositionAttachment", "PositionID", "Position", "ID", ""),
    ("TaskItem", "ObjectID", "Applicant", "ApplicantID", "x.ObjectType = 'Applicant'"),
    ("TaskItem", "ObjectID", "Contact", "ID", "x.ObjectType = 'Contact'"),
]


@pytest.fixture(scope="module")
def loaded():
    pytest.importorskip("pyodbc")
    try:
        T.run(T.MIDDLE)
        T.run(T.TARGET)
    except Exception as e:                                 # noqa: BLE001
        pytest.skip(f"SQL Server not reachable: {e}")
    cn = T._connect(T.TARGET_DB)
    yield cn.cursor()
    cn.close()


@pytest.mark.parametrize("child,col,parent,key,where", LINKS, ids=[f"{c}.{k}->{p}" for c, k, p, _, w in LINKS])
def test_no_broken_links(loaded, child, col, parent, key, where):
    n = loaded.execute(
        f"SELECT COUNT(*) FROM dbo.{T.q(child)} x WHERE x.{col} IS NOT NULL{' AND ' + where if where else ''} "
        f"AND NOT EXISTS (SELECT 1 FROM dbo.{T.q(parent)} p WHERE CAST(p.{key} AS NVARCHAR(200)) = CAST(x.{col} AS NVARCHAR(200)))").fetchone()[0]
    assert n == 0, f"{n} {child}.{col} value(s) point at no {parent}"


def test_orphans_are_rejected_not_loaded(loaded):
    assert loaded.execute("SELECT COUNT(*) FROM dbo.Contact WHERE CompanyID IS NULL").fetchone()[0] == 0
    assert loaded.execute("SELECT COUNT(*) FROM dbo.Notes WHERE ApplicantID IS NULL AND ContactID IS NULL "
                          "AND CompanyID IS NULL AND PositionID IS NULL").fetchone()[0] == 0
    reasons = {r[0] for r in loaded.execute("SELECT DISTINCT reason FROM dbo.MigrationRejects WHERE action = 'rejected'")}
    assert "contact linked to no company (orphan)" in reasons
    assert "linked to no migrated record (orphan)" in reasons


def test_deleted_parents_are_flagged(loaded):
    flagged = {r[0] for r in loaded.execute("SELECT DISTINCT reason FROM dbo.MigrationRejects WHERE action = 'flagged'")}
    assert {"live placement on a deleted job", "live placement on a deleted company"} <= flagged


def test_merged_duplicates_are_gone(loaded):
    from validation.duplicates import merges
    for mg in merges("legacy"):
        if mg["table"] == "Person":
            assert loaded.execute("SELECT COUNT(*) FROM dbo.Applicant WHERE ApplicantID = ?", mg["duplicate"]).fetchone()[0] == 0
