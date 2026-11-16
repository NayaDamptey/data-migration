"""
transform/runs.py

Migration runs: each run is a version. It holds its own source Parquet, its DuckDB warehouse (staging,
mid, target, audit), a copy of the mapping spec and merges it was built with, and run.json (what it was,
row counts, test results, the changes made in it).

    storage/projects/<project>/runs/<run>/            one run
    storage/projects/<project>/runs/CURRENT           the run the app shows

A new run is started by a fresh ingest (Run canonical layer) or a change that affects the data (a
duplicate decision); field edits rebuild the current run's affected models and are logged in it.
(File-based for now; runs, changes and approvals move to Postgres with the API workers.)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
REPO = ENGINE.parent
sys.path.insert(0, str(ENGINE / "ingest"))
sys.path.insert(0, str(HERE))
import build_dbt  # noqa: E402
from to_parquet import from_csv, from_sqlserver  # noqa: E402

DBT = HERE / "dbt"
PROJECT = "harrow-finch-cobaltdesk-beaconfield"
_lock = threading.RLock()
_cons: dict[str, object] = {}


def root(project: str = PROJECT) -> Path:
    return REPO / "storage" / "projects" / project / "runs"


def run_dir(run: str, project: str = PROJECT) -> Path:
    return root(project) / run


def current(project: str = PROJECT) -> str | None:
    f = root(project) / "CURRENT"
    if f.exists():
        rid = f.read_text().strip()
        if (run_dir(rid, project) / "warehouse.duckdb").exists():
            return rid
    return None


def _set_current(run: str, project: str = PROJECT):
    root(project).mkdir(parents=True, exist_ok=True)
    (root(project) / "CURRENT").write_text(run)


def info(run: str, project: str = PROJECT) -> dict:
    f = run_dir(run, project) / "run.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _save(run: str, data: dict, project: str = PROJECT):
    (run_dir(run, project) / "run.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def history(project: str = PROJECT) -> list[dict]:
    out = []
    if root(project).exists():
        for d in root(project).iterdir():
            if d.is_dir() and (d / "run.json").exists():
                out.append(info(d.name, project))
    return sorted(out, key=lambda r: r.get("created", ""), reverse=True)


def new_run(message: str, source: str = "legacy", csv_dir: Path | None = None, project: str = PROJECT) -> str:
    """Start a run. source: 'legacy' (ingest the restored database), 'csv' (ingest csv_dir) or 'copy'
    (reuse the current run's Parquet, for a change that doesn't touch the source)."""
    with _lock:
        rid = time.strftime("r%Y%m%d-%H%M%S")
        while run_dir(rid, project).exists():
            time.sleep(1)
            rid = time.strftime("r%Y%m%d-%H%M%S")
        rd = run_dir(rid, project)
        src = rd / "source"
        prev = current(project)
        if source == "copy" and prev:
            shutil.copytree(run_dir(prev, project) / "source", src)
        elif source == "csv" and csv_dir:
            from_csv(csv_dir, src)
        else:
            from_sqlserver(src)
        _save(rid, {"id": rid, "message": message, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "previous": prev,
                    "source": source, "changes": [], "layers": []}, project)
        return rid


def connect(run: str, project: str = PROJECT):
    """A DuckDB connection to a run's warehouse (one per run, shared in this process)."""
    import duckdb
    path = str(run_dir(run, project) / "warehouse.duckdb")
    if path not in _cons:
        _cons[path] = duckdb.connect(path)
    return _cons[path]


def build(run: str, layer: str = "all", select: list[str] | None = None, project: str = PROJECT) -> dict:
    """Generate the dbt project from the spec and merges, then dbt build part of it on the run's warehouse.
    layer: 'middle' (seeds, staging, mid), 'target' (target, audit) or 'all'; select overrides it."""
    with _lock:
        rd = run_dir(run, project)
        built = build_dbt.build(rd / "source")
        # keep what this run was built from
        snap = rd / "built_from"
        shutil.rmtree(snap, ignore_errors=True)
        snap.mkdir(parents=True)
        for f in (HERE / "spec").glob("*"):
            shutil.copy(f, snap / f.name)
        for f in (DBT / "seeds").glob("*.csv"):
            shutil.copy(f, snap / f.name)
        os.environ.update({"MIGRYR_SOURCE_DIR": (rd / "source").as_posix(), "MIGRYR_WAREHOUSE": (rd / "warehouse.duckdb").as_posix(),
                           "MIGRYR_DBT_TARGET": (rd / "dbt_target").as_posix(), "MIGRYR_DBT_LOGS": (rd / "dbt_logs").as_posix()})
        args = ["build", "--project-dir", str(DBT), "--profiles-dir", str(DBT), "--quiet"]
        if select:
            args += ["--select", *select]
        elif layer == "middle":
            args += ["--select", "path:seeds", "path:models/staging", "path:models/mid"]
        elif layer == "target":
            args += ["--select", "path:models/target", "path:models/audit"]
        from dbt.cli.main import dbtRunner
        res = dbtRunner().invoke(args)
        results = []
        for r in (res.result or []):
            node = getattr(r, "node", None)
            results.append({"name": getattr(node, "name", "?"), "status": str(r.status), "message": r.message})
        failed = [r for r in results if r["status"] not in ("success", "pass")]
        con = connect(run, project)
        counts = {s: {t: con.execute(f'SELECT COUNT(*) FROM {s}."{t}"').fetchone()[0]
                      for (t,) in con.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{s}'").fetchall()}
                  for s in ("mid", "target")}
        if layer in ("target", "all") or select:
            out = rd / "target"
            out.mkdir(exist_ok=True)
            for t in counts["target"]:
                con.execute(f"COPY target.\"{t}\" TO '{(out / f'{t}.parquet').as_posix()}' (FORMAT parquet)")
        data = info(run, project)
        data["layers"] = sorted(set(data.get("layers", [])) | ({"middle", "target"} if layer == "all" else {layer} if not select else set()))
        data.update({"built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": res.success and not failed, "failed": failed,
                     "counts": counts, "built": built, "reconciliation": reconciliation(run, project)})
        _save(run, data, project)
        if not select or res.success:
            _set_current(run, project)
        if not res.success or failed:
            msg = "; ".join(f"{f['name']}: {str(f['message'])[:300]}" for f in failed) or str(res.exception)
            raise RuntimeError(msg)
        return data


def log_change(run: str, text: str, project: str = PROJECT):
    data = info(run, project)
    data.setdefault("changes", []).append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "change": text})
    _save(run, data, project)


def reconciliation(run: str, project: str = PROJECT) -> list[dict]:
    """Row counts per entity: source table(s) -> middle tier table -> the target tables it loads."""
    con = connect(run, project)
    src = run_dir(run, project) / "source"
    middle, target = build_dbt.load_spec("middle"), build_dbt.load_spec("target")

    def count(sql):
        try:
            return con.execute(sql).fetchone()[0]
        except Exception:                                    # noqa: BLE001 — not built yet
            return None
    feeds: dict[str, list[str]] = {}
    for t in target["entities"]:
        for s in t["selects"]:
            m = re.search(r"\bmid__(\w+)", s["from"])
            if m and t["table"] not in feeds.setdefault(m.group(1), []):
                feeds[m.group(1)].append(t["table"])
    out = []
    for e in middle["entities"]:
        sources = sorted({re.search(r"\bsrc__(\w+)", s["from"]).group(1) for s in e["selects"]})
        out.append({
            "entity": e["label"],
            "source": [{"table": s, "rows": count(f"SELECT COUNT(*) FROM read_parquet('{(src / f'{s}.parquet').as_posix()}')")} for s in sources],
            "middle": {"table": f"mid.{e['table']}", "rows": count(f'SELECT COUNT(*) FROM mid."{e["table"]}"')},
            "target": [{"table": t, "rows": count(f'SELECT COUNT(*) FROM target."{t}"')} for t in feeds.get(e["table"], [])],
        })
    return out


def merges_of(run: str, project: str = PROJECT) -> list[dict]:
    """The merges a run was built with (built_from/merges.csv)."""
    import csv
    f = run_dir(run, project) / "built_from" / "merges.csv"
    if not f.exists():
        return []
    with open(f, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
