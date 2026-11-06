"""
mapping/generate_sql.py

Turns the saved mapping (mapping/migration_mapping.json, edited in the UI) into
T-SQL that migrates Cobaltdesk_Legacy -> RecruitPlatform_Target.

    sql/target/00_create_target_db.sql   target tables (from Target Schema.csv) + mig schema
    sql/target/10_keymap.sql             new IDs for every migrated row (mig.KeyMap crosswalk)
    sql/target/20_load_NN_<map>.sql      one script per table mapping, parents before children
    sql/target/80_foreign_keys.sql       target FKs added WITH CHECK (result logged, never aborts)
    sql/target/90_reconcile.sql          source vs loaded vs rejected, per mapping and per table
    sql/target/generation_report.md      what was generated, what was blocked and why

A table mapping is BLOCKED (not generated) when the validator raises an error on it,
or when a table it references through fk_lookup is blocked / unmapped.

Run
  python mapping/generate_sql.py                 # write scripts
  python mapping/generate_sql.py --run           # write + execute on localhost\\SQLEXPRESS + print reconciliation
  python mapping/generate_sql.py --approved-only # only mappings marked approved in the UI
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))      # engine root: validation.duplicates
from engine import (DRIVING_ALIAS, ROOT, SOURCE_DB, TARGET_DB, TRANSFORMS, Schema, aliases,  # noqa: E402
                    load_mapping, load_order, load_source_model, load_target_schema, mapping_id,
                    referenced_source_table, resolve_ref, type_kind, validate)

OUT = ROOT / "sql" / "target"
SERVER = r"localhost\SQLEXPRESS"


def q(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    return "N'" + str(v).replace("'", "''") + "'"


SRC = f"{q(SOURCE_DB)}.dbo."


def src_ref(ref: str) -> str:
    """'p.First_Name' -> 'p.[First_Name]'"""
    a, c = ref.strip().split(".", 1)
    return f"{a}.{q(c)}"


def qualify_sql(expr: str, m: dict) -> str:
    """Bracket alias.Column references inside free SQL (join ON / filter / custom)."""
    al = aliases(m)
    return re.sub(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b",
                  lambda mt: f"{mt.group(1)}.{q(mt.group(2))}" if mt.group(1) in al else mt.group(0), expr or "")


def final_cast(expr: str, ttype: str) -> str:
    kind, size = type_kind(ttype)
    if kind == "string":
        return f"CAST(CAST({expr} AS NVARCHAR(MAX)) AS {ttype})" if size is None else \
               f"CAST(LEFT(CAST({expr} AS NVARCHAR(MAX)), {size}) AS {ttype})"
    return f"TRY_CONVERT({ttype}, {expr})"


# ══════════════════════════════════════════════════════════════════════════════

class Generator:
    def __init__(self, mapping: dict, approved_only: bool = False, data=None, source: str = "legacy"):
        self.mapping = mapping
        self.src: Schema = load_source_model()
        self.tgt: Schema = load_target_schema()
        # same checks as the UI, including the data checks (truncation, duplicate keys, ...)
        self.flags = validate(mapping, self.src, self.tgt, data)
        self.blocked: dict[str, list[str]] = defaultdict(list)
        maps = mapping.get("tables", [])
        for f in self.flags:
            if f.severity == "error" and f.mapping:
                self.blocked[f.mapping].append(f"{f.code} {f.target_column or ''}: {f.message}".replace(" :", ":"))
        if approved_only:
            for m in maps:
                if m.get("status") != "approved":
                    self.blocked[mapping_id(m)].append("not approved (generated with --approved-only)")
        # cascade: a mapping whose fk_lookup parent table has no generated mapping is blocked too
        changed = True
        while changed:
            changed = False
            live = {m["target_table"] for m in maps if mapping_id(m) not in self.blocked}
            for m in maps:
                mid = mapping_id(m)
                if mid in self.blocked:
                    continue
                for c in m.get("columns", []):
                    tcol = self.tgt.col(m["target_table"], c.get("target", ""))
                    if c.get("transform") == "fk_lookup" and tcol and tcol.fk_to and tcol.fk_to[0] not in live:
                        self.blocked[mid].append(f"parent {tcol.fk_to[0]} is not migrated (blocked or unmapped) — {c['target']}")
                        changed = True
                        break
        self.live = [m for m in maps if mapping_id(m) not in self.blocked]
        # reviewer's duplicate decisions (dashboard -> Duplicates): merged pairs load as one record
        from validation.duplicates import merges
        self.merges = defaultdict(list)
        for mg in merges(source):
            self.merges[mg["table"]].append(mg)

    # ── 00 ────────────────────────────────────────────────────────────────────
    def create_db(self) -> str:
        out = [f"-- Generated by mapping/generate_sql.py at {datetime.now():%Y-%m-%d %H:%M} — do not edit by hand.",
               "SET NOCOUNT ON;", "USE master;", "GO",
               f"IF DB_ID(N'{TARGET_DB}') IS NOT NULL BEGIN ALTER DATABASE {q(TARGET_DB)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE {q(TARGET_DB)}; END",
               "GO", f"CREATE DATABASE {q(TARGET_DB)};", "GO", f"ALTER DATABASE {q(TARGET_DB)} SET AUTO_CLOSE OFF;", "GO",
               f"USE {q(TARGET_DB)};", "GO", "EXEC (N'CREATE SCHEMA mig');", "GO",
               """CREATE TABLE mig.KeyMap (
    target_table sysname NOT NULL, source_table sysname NOT NULL, source_key NVARCHAR(200) NOT NULL,
    target_id NVARCHAR(50) NOT NULL, mapping_id NVARCHAR(200) NOT NULL,
    CONSTRAINT PK_KeyMap PRIMARY KEY (target_table, source_table, source_key));
CREATE INDEX IX_KeyMap_target ON mig.KeyMap (target_table, target_id);
CREATE TABLE mig.Rejects (
    reject_id INT IDENTITY PRIMARY KEY, mapping_id NVARCHAR(200) NOT NULL, target_table sysname NOT NULL,
    target_column sysname NULL, source_table sysname NOT NULL, source_key NVARCHAR(200) NULL,
    action NVARCHAR(20) NOT NULL,            -- rejected | nulled | truncated
    reason NVARCHAR(400) NOT NULL, logged_at DATETIME2 DEFAULT SYSDATETIME());
CREATE TABLE mig.LoadLog (
    log_id INT IDENTITY PRIMARY KEY, mapping_id NVARCHAR(200) NULL, step NVARCHAR(60) NOT NULL,
    row_count INT NULL, detail NVARCHAR(400) NULL, logged_at DATETIME2 DEFAULT SYSDATETIME());""", "GO"]
        for t, cols in self.tgt.tables.items():
            lines = [f"    {q(c.name)} {c.type} {'NOT NULL' if c.pk else 'NULL'}" for c in cols.values()]
            pk = self.tgt.pk(t)
            if pk:
                lines.append(f"    CONSTRAINT {q('PK_' + t)} PRIMARY KEY ({q(pk)})")
            out.append(f"CREATE TABLE dbo.{q(t)} (\n" + ",\n".join(lines) + "\n);")
        out.append("GO")
        return "\n".join(out)

    # ── 10 ────────────────────────────────────────────────────────────────────
    def keymap(self) -> str:
        out = [f"-- Generated by mapping/generate_sql.py — new IDs for every row that will be migrated.",
               "SET NOCOUNT ON;", f"USE {q(TARGET_DB)};", "GO"]
        for m in self.live:
            mid, tt, st = mapping_id(m), m["target_table"], m["source_table"]
            pkc = next(c for c in m["columns"] if c["target"] == self.tgt.pk(tt))
            kind = type_kind(self.tgt.col(tt, pkc["target"]).type)[0]
            strategy = (pkc.get("params") or {}).get("strategy", "new")
            src_key = f"CAST({src_ref(pkc['source'])} AS NVARCHAR(200))"
            if strategy == "keep":
                new_id = src_key
            elif kind == "int":
                new_id = (f"CAST((SELECT ISNULL(MAX(CAST(target_id AS INT)), 0) FROM mig.KeyMap WHERE target_table = {lit(tt)}) "
                          f"+ ROW_NUMBER() OVER (ORDER BY {src_ref(pkc['source'])}) AS NVARCHAR(50))")
            else:
                new_id = "LOWER(CONVERT(NVARCHAR(50), NEWID()))"
            out.append(f"-- {mid}  ({strategy} {kind} keys)")
            out.append(f"INSERT INTO mig.KeyMap (target_table, source_table, source_key, target_id, mapping_id)\n"
                       f"SELECT {lit(tt)}, {lit(st)}, {src_key}, {new_id}, {lit(mid)}\n"
                       f"FROM {self._from(m)}\n"
                       f"WHERE {src_ref(pkc['source'])} IS NOT NULL{self._filter(m)}\n"
                       f"  AND NOT EXISTS (SELECT 1 FROM mig.KeyMap x WHERE x.target_table = {lit(tt)} "
                       f"AND x.source_table = {lit(st)} AND x.source_key = {src_key});")
            out.append(f"INSERT INTO mig.LoadLog (mapping_id, step, row_count) VALUES ({lit(mid)}, N'keys', @@ROWCOUNT);")
            for mg in self.merges.get(st, []):
                out.append(f"-- merged duplicate: legacy {st} {mg['duplicate']} -> the new id of {mg['survivor']} "
                           "(everything attached to the duplicate links to the kept record)")
                out.append(f"UPDATE d SET d.target_id = s.target_id FROM mig.KeyMap d JOIN mig.KeyMap s "
                           f"ON s.target_table = d.target_table AND s.source_table = d.source_table AND s.source_key = {lit(mg['survivor'])} "
                           f"WHERE d.target_table = {lit(tt)} AND d.source_table = {lit(st)} AND d.source_key = {lit(mg['duplicate'])};")
            out.append("GO")
        return "\n".join(out)

    def _from(self, m: dict) -> str:
        parts = [f"{SRC}{q(m['source_table'])} {DRIVING_ALIAS}"]
        for j in m.get("joins", []) or []:
            parts.append(f"{j.get('type', 'LEFT').upper()} JOIN {SRC}{q(j['table'])} {j['alias']} ON {qualify_sql(j['on'], m)}")
        return "\n     ".join(parts)

    def _filter(self, m: dict) -> str:
        return f" AND ({qualify_sql(m['filter'], m)})" if (m.get("filter") or "").strip() else ""

    # ── 20 ────────────────────────────────────────────────────────────────────
    def expr(self, m: dict, c: dict, fk_alias: str | None) -> str:
        t, p = c.get("transform", "direct"), c.get("params") or {}
        s = src_ref(c["source"]) if TRANSFORMS[t].needs_source and c.get("source") else "NULL"
        tcol = self.tgt.col(m["target_table"], c["target"])
        if t == "direct":
            return s
        if t == "key":
            return "k.target_id"
        if t == "fk_lookup":
            return f"{fk_alias}.target_id"
        if t == "cast_to_nvarchar":
            return f"CAST({s} AS NVARCHAR(MAX))"
        if t == "cast_to_int":
            return f"TRY_CAST({s} AS INT)"
        if t == "cast_to_decimal":
            kind, ps = type_kind(tcol.type)
            return f"TRY_CAST({s} AS DECIMAL({ps[0]},{ps[1]}))" if kind == "decimal" else f"TRY_CAST({s} AS DECIMAL(18,4))"
        if t == "cast_to_float":
            return f"TRY_CAST({s} AS FLOAT)"
        if t == "cast_to_date":
            return f"TRY_CAST({s} AS DATE)"
        if t == "trim":
            return f"LTRIM(RTRIM({s}))"
        if t == "truncate":
            return f"CAST({s} AS NVARCHAR(MAX))"          # cut to size by final_cast, logged as 'truncated'
        if t == "invert_bool":
            return f"CASE WHEN {s} = 1 THEN 0 WHEN {s} = 0 THEN 1 END"
        if t == "value_map":
            whens = " ".join(f"WHEN {lit(str(k))} THEN {lit(v)}" for k, v in (p.get("map") or {}).items())
            return f"CASE CAST({s} AS NVARCHAR(200)) {whens} ELSE {lit(p.get('default'))} END"
        if t == "lookup":
            return (f"(SELECT TOP 1 lk.{q(p['value'])} FROM {SRC}{q(p['table'])} lk WHERE lk.{q(p['key'])} = {s})")
        if t == "coalesce":
            return "COALESCE(" + ", ".join([s] + [src_ref(o) for o in p.get("others", [])]) + ")"
        if t == "concat":
            return f"CONCAT_WS({lit(p.get('sep', ' '))}, " + ", ".join(src_ref(x) for x in p.get("parts", [])) + ")"
        if t == "constant":
            return lit(p.get("value"))
        if t == "custom":
            return f"({qualify_sql(p['sql'], m)})"
        raise ValueError(t)

    def load_script(self, m: dict, n: int) -> str:
        mid, tt, st = mapping_id(m), m["target_table"], m["source_table"]
        pkc = next(c for c in m["columns"] if c["target"] == self.tgt.pk(tt))
        selects = [f"{src_ref(pkc['source'])} AS [__src_key]"]
        joins, rejects, nulls, inserts = [], [], [], []
        for i, c in enumerate(m["columns"]):
            tcol = self.tgt.col(tt, c["target"])
            fk_alias = None
            if c.get("transform") == "fk_lookup":
                fk_alias = f"fk{i}"
                parent = tcol.fk_to[0]
                ref_tbl = referenced_source_table(m, c["source"], self.src)
                joins.append(f"LEFT JOIN mig.KeyMap {fk_alias} ON {fk_alias}.target_table = {lit(parent)} "
                             f"AND {fk_alias}.source_table = {lit(ref_tbl)} "
                             f"AND {fk_alias}.source_key = CAST({src_ref(c['source'])} AS NVARCHAR(200))")
                selects.append(f"CAST({src_ref(c['source'])} AS NVARCHAR(200)) AS {q('__raw_' + c['target'])}")
                rejects.append((c["target"], f"no {parent} migrated for legacy {ref_tbl} "))
            elif c.get("transform", "").startswith("cast_to_") and c.get("transform") != "cast_to_nvarchar":
                selects.append(f"CAST({src_ref(c['source'])} AS NVARCHAR(200)) AS {q('__raw_' + c['target'])}")
                nulls.append((c["target"], f"cannot convert to {tcol.type}: "))
            selects.append(f"{self.expr(m, c, fk_alias)} AS {q(c['target'])}")
            inserts.append((c["target"], tcol.type))

        out = [f"-- Generated by mapping/generate_sql.py — {mid}", f"-- {m.get('notes', '')}".rstrip(),
               "SET NOCOUNT ON;", f"USE {q(TARGET_DB)};", f"DECLARE @mid NVARCHAR(200) = {lit(mid)};",
               "IF OBJECT_ID('tempdb..#stage') IS NOT NULL DROP TABLE #stage;",
               "-- 1. stage: source rows with every target value computed",
               "SELECT " + ",\n       ".join(selects),
               "INTO #stage",
               f"FROM {self._from(m)}",
               f"JOIN mig.KeyMap k ON k.target_table = {lit(tt)} AND k.source_table = {lit(st)} "
               f"AND k.source_key = CAST({src_ref(pkc['source'])} AS NVARCHAR(200))"]
        out += joins
        out.append(f"WHERE 1 = 1{self._filter(m)};")
        out.append(f"INSERT INTO mig.LoadLog (mapping_id, step, row_count) VALUES (@mid, N'staged', @@ROWCOUNT);")
        merged = self.merges.get(st, [])
        if merged:
            out.append("-- 1b. merged duplicates: copy the values the reviewer took from the duplicate, then drop it")
            for mg in merged:
                cols = [c["target"] for c in m["columns"] for src_col in mg["take_from_duplicate"]
                        if (c.get("source") or "").strip() == f"s.{src_col}" and c.get("transform") not in ("key",)]
                if cols:
                    out.append("UPDATE sv SET " + ", ".join(f"{q(t)} = dp.{q(t)}" for t in cols)
                               + " FROM #stage sv JOIN #stage dp ON CAST(dp.[__src_key] AS NVARCHAR(200)) = "
                               + f"{lit(mg['duplicate'])} WHERE CAST(sv.[__src_key] AS NVARCHAR(200)) = {lit(mg['survivor'])};")
            out.append("DELETE FROM #stage WHERE CAST([__src_key] AS NVARCHAR(200)) IN ("
                       + ", ".join(lit(mg["duplicate"]) for mg in merged) + ");")
            out.append("INSERT INTO mig.LoadLog (mapping_id, step, row_count) VALUES (@mid, N'merged', @@ROWCOUNT);")
        if rejects:
            out.append("-- 2. reject rows whose parent was not migrated (would break the FK)")
            for col, why in rejects:
                out.append(f"INSERT INTO mig.Rejects (mapping_id, target_table, target_column, source_table, source_key, action, reason)\n"
                           f"SELECT @mid, {lit(tt)}, {lit(col)}, {lit(st)}, CAST([__src_key] AS NVARCHAR(200)), N'rejected', "
                           f"{lit(col + ': ' + why)} + {q('__raw_' + col)}\n"
                           f"FROM #stage WHERE {q('__raw_' + col)} IS NOT NULL AND {q(col)} IS NULL;")
            out.append(f"-- children of rejected rows must not find them: drop their keys")
            out.append(f"DELETE k FROM mig.KeyMap k WHERE k.target_table = {lit(tt)} AND k.target_id IN ("
                       f"SELECT k2.target_id FROM mig.KeyMap k2 WHERE k2.target_table = {lit(tt)} AND k2.source_table = {lit(st)} "
                       f"AND k2.source_key IN (SELECT source_key FROM mig.Rejects WHERE mapping_id = @mid AND action = N'rejected'));")
        for col, why in nulls:
            out.append(f"INSERT INTO mig.Rejects (mapping_id, target_table, target_column, source_table, source_key, action, reason)\n"
                       f"SELECT @mid, {lit(tt)}, {lit(col)}, {lit(st)}, CAST([__src_key] AS NVARCHAR(200)), N'nulled', "
                       f"{lit(col + ': ' + why)} + {q('__raw_' + col)} FROM #stage WHERE {q('__raw_' + col)} IS NOT NULL AND {q(col)} IS NULL;")
        for col, ttype in inserts:
            kind, size = type_kind(ttype)
            if kind == "string" and size:
                out.append(f"INSERT INTO mig.Rejects (mapping_id, target_table, target_column, source_table, source_key, action, reason)\n"
                           f"SELECT @mid, {lit(tt)}, {lit(col)}, {lit(st)}, CAST([__src_key] AS NVARCHAR(200)), N'truncated', "
                           f"{lit(f'{col}: longer than {size} characters, cut to fit')} FROM #stage "
                           f"WHERE LEN(CAST({q(col)} AS NVARCHAR(MAX))) > {size};")
        out.append("-- 3. load")
        out.append(f"INSERT INTO dbo.{q(tt)} (" + ", ".join(q(c) for c, _ in inserts) + ")\n"
                   "SELECT " + ",\n       ".join(final_cast(q(c), t) for c, t in inserts) + "\nFROM #stage s\n"
                   "WHERE NOT EXISTS (SELECT 1 FROM mig.Rejects r WHERE r.mapping_id = @mid AND r.action = N'rejected' "
                   "AND r.source_key = CAST(s.[__src_key] AS NVARCHAR(200)));")
        out.append(f"INSERT INTO mig.LoadLog (mapping_id, step, row_count) VALUES (@mid, N'loaded', @@ROWCOUNT);")
        out.append("DROP TABLE #stage;")
        out.append("GO")
        return "\n".join(out)

    # ── 80 ────────────────────────────────────────────────────────────────────
    def foreign_keys(self) -> str:
        out = ["-- Generated by mapping/generate_sql.py — target foreign keys, validated against the loaded data.",
               "-- Each FK is attempted separately; the outcome is written to mig.LoadLog (step = 'fk').",
               "SET NOCOUNT ON;", f"USE {q(TARGET_DB)};", "GO"]
        for t, cols in self.tgt.tables.items():
            for c in cols.values():
                if not c.fk_to:
                    continue
                parent = self.tgt.col(*c.fk_to)
                name = f"FK_{t}_{c.name}"
                if not parent or not parent.pk:
                    out.append(f"INSERT INTO mig.LoadLog (step, detail) VALUES (N'fk', {lit(name + ': skipped, parent is not a key')});")
                elif type_kind(parent.type)[0] != type_kind(c.type)[0]:
                    out.append(f"INSERT INTO mig.LoadLog (step, detail) VALUES (N'fk', "
                               f"{lit(f'{name}: skipped, type {c.type} vs {parent.type} (target schema issue)')});")
                else:
                    out.append(f"BEGIN TRY\n  ALTER TABLE dbo.{q(t)} WITH CHECK ADD CONSTRAINT {q(name)} FOREIGN KEY ({q(c.name)}) "
                               f"REFERENCES dbo.{q(c.fk_to[0])} ({q(c.fk_to[1])});\n"
                               f"  INSERT INTO mig.LoadLog (step, detail) VALUES (N'fk', {lit(name + ': ok')});\n"
                               f"END TRY BEGIN CATCH\n  INSERT INTO mig.LoadLog (step, detail) VALUES (N'fk', "
                               f"{lit(name + ': FAILED - ')} + LEFT(ERROR_MESSAGE(), 300));\nEND CATCH;")
        out.append("GO")
        return "\n".join(out)

    # ── 90 ────────────────────────────────────────────────────────────────────
    def reconcile(self) -> str:
        rows = []
        for m in self.live:
            mid, st = mapping_id(m), m["source_table"]
            rows.append(f"SELECT {lit(mid)} AS mapping_id, {lit(m['target_table'])} AS target_table, "
                        f"(SELECT COUNT(*) FROM {self._from(m).replace(chr(10), ' ')} WHERE 1 = 1{self._filter(m)}) AS source_rows")
        out = ["-- Generated by mapping/generate_sql.py — reconciliation: source vs loaded vs rejected.",
               "SET NOCOUNT ON;", f"USE {q(TARGET_DB)};"]
        if rows:
            out.append("WITH src AS (\n  " + "\n  UNION ALL ".join(rows) + "\n)\n"
                       "SELECT src.mapping_id, src.target_table, src.source_rows,\n"
                       "       ISNULL((SELECT SUM(row_count) FROM mig.LoadLog l WHERE l.mapping_id = src.mapping_id AND l.step = N'loaded'), 0) AS loaded,\n"
                       "       (SELECT COUNT(DISTINCT source_key) FROM mig.Rejects r WHERE r.mapping_id = src.mapping_id AND r.action = N'rejected') AS rejected,\n"
                       "       ISNULL((SELECT SUM(row_count) FROM mig.LoadLog l WHERE l.mapping_id = src.mapping_id AND l.step = N'merged'), 0) AS merged,\n"
                       "       (SELECT COUNT(*) FROM mig.Rejects r WHERE r.mapping_id = src.mapping_id AND r.action = N'nulled') AS values_nulled,\n"
                       "       (SELECT COUNT(*) FROM mig.Rejects r WHERE r.mapping_id = src.mapping_id AND r.action = N'truncated') AS values_truncated,\n"
                       "       CASE WHEN src.source_rows = ISNULL((SELECT SUM(row_count) FROM mig.LoadLog l WHERE l.mapping_id = src.mapping_id AND l.step = N'loaded'), 0)\n"
                       "                 + (SELECT COUNT(DISTINCT source_key) FROM mig.Rejects r WHERE r.mapping_id = src.mapping_id AND r.action = N'rejected')\n"
                       "                 + ISNULL((SELECT SUM(row_count) FROM mig.LoadLog l WHERE l.mapping_id = src.mapping_id AND l.step = N'merged'), 0)\n"
                       "            THEN N'balanced' ELSE N'MISMATCH' END AS status\n"
                       "FROM src ORDER BY src.target_table;")
        out.append("SELECT detail AS foreign_key_result FROM mig.LoadLog WHERE step = N'fk' ORDER BY "
                   "CASE WHEN detail LIKE N'%FAILED%' THEN 0 WHEN detail LIKE N'%skipped%' THEN 1 ELSE 2 END, detail;")
        out.append("SELECT action, target_table, target_column, COUNT(*) AS n, MIN(reason) AS example "
                   "FROM mig.Rejects GROUP BY action, target_table, target_column ORDER BY action, n DESC;")
        return "\n".join(out)

    # ── write ─────────────────────────────────────────────────────────────────
    def write(self) -> list[Path]:
        OUT.mkdir(parents=True, exist_ok=True)
        for old in OUT.glob("*.sql"):
            old.unlink()
        files = {"00_create_target_db.sql": self.create_db(), "10_keymap.sql": self.keymap()}
        by_table = defaultdict(list)
        for m in self.live:
            by_table[m["target_table"]].append(m)
        n = 0
        for t in load_order({"tables": self.live}, self.tgt):
            for m in by_table[t]:
                n += 1
                safe = re.sub(r"[^A-Za-z0-9_]+", "_", mapping_id(m))
                files[f"20_load_{n:02d}_{safe}.sql"] = self.load_script(m, n)
        files["80_foreign_keys.sql"] = self.foreign_keys()
        files["90_reconcile.sql"] = self.reconcile()
        paths = []
        for name, body in files.items():
            (OUT / name).write_text(body + "\n", encoding="utf-8")
            paths.append(OUT / name)
        (OUT / "generation_report.md").write_text(self.report(), encoding="utf-8")
        return paths

    def report(self) -> str:
        lines = [f"# Target SQL generation report", "", f"Generated {datetime.now():%Y-%m-%d %H:%M} from `mapping/migration_mapping.json`.", "",
                 f"* Generated: **{len(self.live)}** table mappings", f"* Blocked: **{len(self.blocked)}**", ""]
        if self.blocked:
            lines += ["## Blocked mappings (fix in the mapping UI, then regenerate)", ""]
            for mid, why in sorted(self.blocked.items()):
                lines.append(f"### {mid}")
                lines += [f"* {w}" for w in dict.fromkeys(why)]
                lines.append("")
        warns = [f for f in self.flags if f.severity == "warn" and f.mapping in {mapping_id(m) for m in self.live}]
        if warns:
            lines += ["## Generated with warnings", ""]
            lines += [f"* `{f.mapping}` {f.target_column}: {f.message}" for f in warns]
        return "\n".join(lines) + "\n"


def data_probe():
    """DataProbe over the legacy SQL Server DB (what will actually be migrated); CSV baseline if unreachable."""
    from engine import DataProbe
    sys.path.insert(0, str(ROOT))
    from validation.validator import load_csv_baseline, load_sqlserver
    try:
        return DataProbe(load_sqlserver())
    except Exception as e:                                   # noqa: BLE001
        print(f"  (SQL Server unavailable: {e}; data checks use the CSV baseline)")
        return DataProbe(load_csv_baseline())


def run(paths: list[Path]):
    import pyodbc
    for p in paths:
        if p.suffix != ".sql" or p.name.startswith("90_"):
            continue
        r = subprocess.run(["sqlcmd", "-S", SERVER, "-E", "-b", "-f", "65001", "-i", str(p)], capture_output=True, text=True)
        status = "ok" if r.returncode == 0 else "FAILED"
        print(f"  {status:6} {p.name}")
        if r.returncode:
            print((r.stdout + r.stderr)[-1500:])
            sys.exit(1)
    cn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={TARGET_DB};Trusted_Connection=yes;")
    cur = cn.cursor()
    cur.execute((OUT / "90_reconcile.sql").read_text(encoding="utf-8").split(f"USE {q(TARGET_DB)};", 1)[1])
    while True:
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print("\n  " + " | ".join(cols))
        for r in rows:
            print("  " + " | ".join("" if v is None else str(v) for v in r))
        if not cur.nextset():
            break


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="execute the scripts against SQL Server")
    ap.add_argument("--approved-only", action="store_true")
    ap.add_argument("--no-data", action="store_true", help="skip data checks (truncation etc.) — not recommended")
    args = ap.parse_args()
    g = Generator(load_mapping(), approved_only=args.approved_only, data=None if args.no_data else data_probe())
    paths = g.write()
    print(f"Generated {len(g.live)} table mappings into {OUT.relative_to(ROOT)} ({len(paths)} scripts); "
          f"{len(g.blocked)} blocked — see sql/target/generation_report.md")
    for mid, why in sorted(g.blocked.items()):
        print(f"  BLOCKED {mid}: {why[0]}")
    if args.run:
        run(paths)


if __name__ == "__main__":
    main()
