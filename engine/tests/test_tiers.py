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
    ("Position_Details", "PositionID", "Position", "ID", ""),
    ("Offer", "PlacementID", "Placements", "ID", ""),
    ("Deal", "PlacementID", "Placements", "ID", ""),
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


def test_jobs_without_a_company_are_rejected(loaded):
    assert loaded.execute("SELECT COUNT(*) FROM dbo.Position WHERE CompanyID IS NULL").fetchone()[0] == 0
    n = loaded.execute("SELECT COUNT(*) FROM dbo.MigrationRejects WHERE target_table = 'Position' "
                       "AND reason = 'job linked to no company'").fetchone()[0]
    assert n > 0


def test_placements_without_a_job_are_rejected(loaded):
    assert loaded.execute("SELECT COUNT(*) FROM dbo.Placements WHERE PositionID IS NULL").fetchone()[0] == 0
    n = loaded.execute("SELECT COUNT(*) FROM dbo.MigrationRejects WHERE target_table = 'Placements' "
                       "AND reason = 'linked to no job, or to a job with no company'").fetchone()[0]
    assert n > 0


def test_merged_duplicates_are_gone(loaded):
    from validation.duplicates import merges
    for mg in merges("legacy"):
        if mg["table"] == "Person":
            assert loaded.execute("SELECT COUNT(*) FROM dbo.Applicant WHERE ApplicantID = ?", mg["duplicate"]).fetchone()[0] == 0
