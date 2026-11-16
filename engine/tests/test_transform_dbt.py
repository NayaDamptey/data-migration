"""The dbt transformation (transform/): ingest the clean baseline CSVs to Parquet, generate the project
from the mapping spec, `dbt build` on DuckDB. Runs without SQL Server, so it runs in CI too."""

import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE / "transform"))

pytest.importorskip("dbt")
import duckdb  # noqa: E402
import run as R  # noqa: E402


@pytest.fixture(scope="module")
def built():
    summary = R.run("ci-test", "baseline", csv_dir=ENGINE / "sample_data" / "source")
    yield summary, R.run_dir("ci-test", "baseline")


def test_build_and_all_dbt_tests_pass(built):
    summary, _ = built
    assert summary["ok"], summary["failed"]
    assert summary["built"]["middle"] == 25 and summary["built"]["target"] == 37


def test_every_target_table_is_loaded(built):
    summary, _ = built
    assert len(summary["target_rows"]) == 37
    assert summary["target_rows"]["Applicant"] > 200 and summary["target_rows"]["Placements"] > 200


def test_clean_baseline_loads_without_rejects(built):
    """The clean baseline has no planted problems: nothing it holds is rejected."""
    _, rd = built
    con = duckdb.connect(str(rd / "warehouse.duckdb"))
    reasons = con.execute("SELECT reason, COUNT(*) FROM audit.migration_rejects GROUP BY reason").fetchall()
    con.close()
    assert not [r for r in reasons if "no company" in r[0] or "no job" in r[0]], reasons


def test_target_exported_as_parquet(built):
    _, rd = built
    assert len(list((rd / "target").glob("*.parquet"))) == 37
