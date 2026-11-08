"""Version review on Dolt: every run of the middle tier and the target is committed to a Dolt database,
so each version, and every row that changed between versions, can be seen.

    storage/dolt/migration       the Dolt repository (tables mid_<Entity> and the target tables)

After a layer runs, its tables are copied from SQL Server into Dolt and committed with a message
(e.g. "Target run" or "Changed target Applicant.Status"). Dolt is found on PATH, in DOLT_BIN, or in tools/dolt.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from app import engine_bridge as bridge

REPO = bridge.STORAGE / "dolt" / "migration"
_lock = threading.Lock()


def dolt_bin() -> str | None:
    if os.getenv("DOLT_BIN") and Path(os.environ["DOLT_BIN"]).exists():
        return os.environ["DOLT_BIN"]
    found = shutil.which("dolt")
    if found:
        return found
    local = list((bridge.REPO / "tools" / "dolt").glob("**/dolt.exe")) + list((bridge.REPO / "tools" / "dolt").glob("**/bin/dolt"))
    return str(local[0]) if local else None


def available() -> bool:
    return dolt_bin() is not None


def _dolt(*args: str, check: bool = True) -> str:
    r = subprocess.run([dolt_bin(), *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-800:])
    return r.stdout


def _sql(query: str) -> list[dict]:
    out = _dolt("sql", "-r", "json", "-q", query)
    return json.loads(out).get("rows", []) if out.strip() else []


def _ensure_repo():
    if (REPO / ".dolt").exists():
        return
    REPO.mkdir(parents=True, exist_ok=True)
    _dolt("init", "--name", "Migryr", "--email", "migryr@localhost")


def _esc(s: str) -> str:
    return s.replace("'", "''")


def _lit(v) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def snapshot(message: str, only: list[tuple[str, str]] | None = None) -> str | None:
    """Copy layer tables from SQL Server into Dolt (one SQL batch) and commit. `only` = [(layer, entity key)]
    limits it. Returns the new commit hash, or None if nothing changed (or Dolt isn't installed)."""
    if not available():
        return None
    import tiers as TI                                   # engine/mapping/tiers.py
    with _lock:
        _ensure_repo()
        sql = []
        for layer in (TI.MIDDLE, TI.TARGET):
            for e in layer.entities:
                if only and (layer.name, e.key) not in only:
                    continue
                name = f"mid_{e.table}" if layer is TI.MIDDLE else e.table
                try:
                    rows = TI.read(layer, e.key)
                except Exception:                        # layer not run yet
                    continue
                cols = list(e.inserts[0].columns)
                defs = ", ".join(f"`{c}` VARCHAR(200) NOT NULL" if i == 0 else f"`{c}` LONGTEXT" for i, c in enumerate(cols))
                sql.append(f"CREATE TABLE IF NOT EXISTS `{name}` ({defs}, PRIMARY KEY (`{cols[0]}`));")
                sql.append(f"DELETE FROM `{name}`;")
                seen = set()
                vals = []
                for r in rows:
                    k = r.get(cols[0])
                    if k is None or k in seen:           # the key is the row's identity in Dolt
                        continue
                    seen.add(k)
                    vals.append("(" + ", ".join(_lit(r.get(c)) for c in cols) + ")")
                col_list = ", ".join(f"`{c}`" for c in cols)
                for i in range(0, len(vals), 500):
                    sql.append(f"INSERT INTO `{name}` ({col_list}) VALUES " + ", ".join(vals[i:i + 500]) + ";")
        # row counts per entity (source -> middle tier -> target), kept with every version
        try:
            recon = TI.reconciliation()
        except Exception:                                # noqa: BLE001
            recon = []
        sql.append("CREATE TABLE IF NOT EXISTS `reconciliation` (`n` INT NOT NULL, `entity` VARCHAR(200) NOT NULL, "
                   "`counts` LONGTEXT, PRIMARY KEY (`entity`));")
        sql.append("DELETE FROM `reconciliation`;")
        if recon:
            sql.append("INSERT INTO `reconciliation` (`n`, `entity`, `counts`) VALUES " + ", ".join(
                f"({i}, {_lit(r['entity'])}, {_lit(json.dumps(r))})" for i, r in enumerate(recon)) + ";")
        # the duplicate merges in force (resolved to candidate / contact / company / job records),
        # so a version can show which records it merged
        try:
            applied = TI.resolved_merges()
        except Exception:                                # noqa: BLE001
            applied = []
        sql.append("DROP TABLE IF EXISTS `merge_log`;" if not _has_column("merge_log", "entity") else "SELECT 1;")
        sql.append("CREATE TABLE IF NOT EXISTS `merge_log` (`merge_key` VARCHAR(200) NOT NULL, `source_table` VARCHAR(100), "
                   "`entity` VARCHAR(100), `id_column` VARCHAR(100), `survivor` VARCHAR(200), `duplicate` VARCHAR(200), "
                   "`fields` LONGTEXT, PRIMARY KEY (`merge_key`));")
        sql.append("DELETE FROM `merge_log`;")
        if applied:
            sql.append("INSERT INTO `merge_log` VALUES " + ", ".join(
                f"({_lit(m['merge_key'])}, {_lit(m['source_table'])}, {_lit(m['entity'])}, {_lit(m['id_column'])}, "
                f"{_lit(m['survivor'])}, {_lit(m['duplicate'])}, {_lit(json.dumps(m['take_from_duplicate']))})" for m in applied) + ";")
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
            f.write("\n".join(sql))
            batch = f.name
        try:
            with open(batch, encoding="utf-8") as fh:
                r = subprocess.run([dolt_bin(), "sql"], cwd=REPO, stdin=fh, capture_output=True, text=True, encoding="utf-8")
            if r.returncode != 0:
                raise RuntimeError((r.stderr or r.stdout).strip()[-800:])
        finally:
            os.unlink(batch)
        _dolt("add", "-A")
        if not _sql("SELECT * FROM dolt_status"):
            return None
        _dolt("commit", "-m", message)
        return _sql("SELECT HASHOF('HEAD') AS h")[0]["h"]


def snapshot_async(message: str, only: list[tuple[str, str]] | None = None, wait_for: threading.Lock | None = None):
    """Snapshot in the background. `wait_for` is the lock the layer runs hold: the snapshot waits for any run
    in progress, so it never reads a table that is being emptied and reloaded."""
    def go():
        if wait_for is None:
            _safe(snapshot, message, only)
            return
        with wait_for:
            _safe(snapshot, message, only)
    threading.Thread(target=go, daemon=True).start()


def _safe(fn, *a):
    try:
        fn(*a)
    except Exception as e:                               # noqa: BLE001 — versioning must never break a run
        print(f"[versions] snapshot failed: {e}")


def log(limit: int = 50) -> dict:
    if not available():
        return {"available": False, "commits": []}
    if not (REPO / ".dolt").exists():
        return {"available": True, "commits": []}
    commits = _sql(f"SELECT commit_hash, committer, message, date FROM dolt_log ORDER BY date DESC LIMIT {int(limit)}")
    out = []
    for c in commits:
        parents = _sql(f"SELECT parent_hash FROM dolt_commit_ancestors WHERE commit_hash = '{_esc(c['commit_hash'])}'")
        parent = parents[0].get("parent_hash") if parents else None
        stats = []
        if parent:
            for s in _sql(f"SELECT * FROM dolt_diff_stat('{_esc(parent)}', '{_esc(c['commit_hash'])}')"):
                stats.append({"table": s["table_name"], "added": s.get("rows_added", 0), "deleted": s.get("rows_deleted", 0),
                              "modified": s.get("rows_modified", 0)})
        try:
            recon = [json.loads(r["counts"]) for r in
                     _sql(f"SELECT counts FROM reconciliation AS OF '{_esc(c['commit_hash'])}' ORDER BY n")]
        except Exception:                                # noqa: BLE001 — versions saved before counts were kept
            recon = []
        out.append({"hash": c["commit_hash"], "parent": parent, "message": c["message"],
                    "date": str(c["date"])[:16], "tables": [t for t in stats if t["table"] not in ("reconciliation", "merge_log")],
                    "counts": recon, "merges": _merges_in(c["commit_hash"], parent) if parent else []})
    return {"available": True, "commits": [c for c in out if c["parent"]]}   # the empty init commit is hidden


def _rows_as_of(table: str, ref: str, idc: str, ids: list[str]) -> dict[str, dict]:
    cols = [r["Field"] for r in _sql(f"DESCRIBE `{table}`")]
    found = _sql(f"SELECT * FROM `{table}` AS OF '{_esc(ref)}' WHERE `{idc}` IN ({', '.join(_lit(i) for i in ids)})")
    return {r.get(idc): {c: r.get(c) for c in cols} for r in found}


def _has_column(table: str, column: str) -> bool:
    try:
        return any(r["Field"] == column for r in _sql(f"DESCRIBE `{table}`"))
    except Exception:                                    # noqa: BLE001
        return False


def _merges_in(commit: str, parent: str) -> list[dict]:
    """Merges this version applied: both records as they were, and the one record they became."""
    import tiers as TI
    try:
        now = {r["merge_key"]: r for r in _sql(f"SELECT * FROM merge_log AS OF '{_esc(commit)}'")}
    except Exception:                                    # noqa: BLE001 — version saved before merges were kept
        return []
    try:
        before = {r["merge_key"] for r in _sql(f"SELECT merge_key FROM merge_log AS OF '{_esc(parent)}'")}
    except Exception:                                    # noqa: BLE001
        before = set()
    out = []
    for k, m in now.items():
        if k in before:
            continue
        key = m.get("entity") or TI.MERGE_TARGETS.get(m["source_table"], (None,))[0]
        idc = m.get("id_column") or TI.MERGE_TARGETS.get(m["source_table"], (None, None))[1]
        if not key:
            continue
        e = TI.MIDDLE.entity(key)
        table = f"mid_{e.table}"
        try:
            was = _rows_as_of(table, parent, idc, [m["survivor"], m["duplicate"]])
            merged = _rows_as_of(table, commit, idc, [m["survivor"]]).get(m["survivor"])
        except Exception:                                # noqa: BLE001
            continue
        out.append({"entity": e.label, "id_column": idc, "kept": was.get(m["survivor"]), "duplicate": was.get(m["duplicate"]),
                    "merged": merged, "taken_from_duplicate": json.loads(m.get("fields") or "[]")})
    return out


def diff(commit: str, table: str, limit: int = 500) -> dict:
    parents = _sql(f"SELECT parent_hash FROM dolt_commit_ancestors WHERE commit_hash = '{_esc(commit)}'")
    if not parents or not parents[0].get("parent_hash"):
        raise KeyError(commit)
    rows = _sql(f"SELECT * FROM dolt_diff('{_esc(parents[0]['parent_hash'])}', '{_esc(commit)}', '{_esc(table)}') LIMIT {int(limit)}")
    # Dolt leaves NULL values out of its JSON, so the columns come from the table itself
    cols = [r["Field"] for r in _sql(f"DESCRIBE `{table.replace('`', '')}`")]
    changes = []
    for r in rows:
        changes.append({"type": r.get("diff_type"),
                        "before": {c: r.get(f"from_{c}") for c in cols},
                        "after": {c: r.get(f"to_{c}") for c in cols}})
    return {"table": table, "columns": cols, "changes": changes}
