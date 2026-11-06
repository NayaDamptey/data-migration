"""
dashboard/app.py — Migration Mapping UI

    streamlit run dashboard/app.py

Pages
  Overview     coverage, flag counts and the target relationship graph
  Map a table  edit the mapping for one target table (source, joins, filter, column grid) with live flags
  Flags        every issue the validator raises, with how to fix it
  Generate SQL write the T-SQL migration from the saved mapping, run it, see the reconciliation

All edits are saved to mapping/migration_mapping.json — the only input of mapping/generate_sql.py.
"""

from __future__ import annotations

import copy
import difflib
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mapping"))
sys.path.insert(0, str(ROOT / "sample_data"))

import engine as E  # noqa: E402

st.set_page_config(page_title="Migration Mapping", page_icon="🔀", layout="wide")

SEV_ICON = {"error": "🔴", "warn": "🟠", "info": "🔵"}
CODE_HELP = {
    "M01": "Target table does not exist", "M02": "Source table does not exist", "M03": "Join / filter refers to unknown table or column",
    "M04": "Primary key not mapped correctly", "M06": "Mapping not approved yet", "M07": "Referenced table has no mapping",
    "M08": "Same source mapped twice", "M09": "Target table has no mapping", "M10": "Target columns left empty",
    "M11": "Source columns not migrated", "C01": "Target column does not exist", "C02": "Target column mapped twice",
    "C03": "Source column does not exist", "C04": "Transform unknown or parameters missing", "C05": "Type mismatch",
    "C06": "Foreign key not mapped relationally", "C07": "fk_lookup on a non-key column", "C08": "Legacy ID copied as plain value",
    "C10": "Custom SQL needs review", "C11": "Low confidence, not reviewed", "D04": "Duplicate key values in the data",
    "D05": "Values too long for the target column", "D06": "Rows reference parents that are not migrated",
    "D07": "Values that cannot be cast", "D09": "Values not covered by value map",
    "T00": "Target table has no primary key", "T01": "Target FK to missing column", "T02": "Target FK type mismatch",
}


# ══════════════════════════════════════════════════════════════════════════════
# state & cached resources
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner="Loading schemas…")
def schemas():
    return E.load_source_model(), E.load_target_schema()


@st.cache_resource(show_spinner="Reading legacy data for data checks…")
def data_probe(source: str):
    from validation.validator import load_csv_baseline, load_sqlserver
    if source == "SQL Server (RecruitCRM_Legacy)":
        try:
            return E.DataProbe(load_sqlserver()), None
        except Exception as e:                                 # noqa: BLE001
            return E.DataProbe(load_csv_baseline()), f"SQL Server not reachable ({e}); using the CSV baseline."
    if source == "CSV baseline":
        return E.DataProbe(load_csv_baseline()), None
    return None, None


SRC, TGT = schemas()

if "mapping" not in st.session_state:
    st.session_state.mapping = E.load_mapping()
    st.session_state.editor_version = 0
    st.session_state.dirty = False


def mapping() -> dict:
    return st.session_state.mapping


def save():
    E.save_mapping(mapping(), user="ui")
    st.session_state.dirty = False
    st.session_state.editor_version += 1
    st.toast("Mapping saved to mapping/migration_mapping.json", icon="💾")


def flags_for(mp: dict):
    probe, _ = data_probe(st.session_state.get("data_source", "SQL Server (RecruitCRM_Legacy)"))
    return E.validate(mp, SRC, TGT, probe)


def table_status(flags, table: str) -> str:
    sev = {f.severity for f in flags if f.target_table == table and f.code not in ("M09", "T00")}
    if not any(m["target_table"] == table for m in mapping()["tables"]):
        return "unmapped"
    return "error" if "error" in sev else "warn" if "warn" in sev else "ok"


STATUS_ICON = {"ok": "🟢", "warn": "🟠", "error": "🔴", "unmapped": "⚪"}


# ══════════════════════════════════════════════════════════════════════════════
# sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("🔀 Mapping")
    page = st.radio("Page", ["Overview", "Map a table", "Flags", "Generate SQL"], label_visibility="collapsed", key="page")
    st.selectbox("Data checks run against", ["SQL Server (RecruitCRM_Legacy)", "CSV baseline", "Off (schema only)"],
                 key="data_source", help="Data checks catch truncation, duplicate keys, orphans and unmapped values.")
    _, warn = data_probe(st.session_state.data_source)
    if warn:
        st.warning(warn)
    st.caption(f"Source **{E.SOURCE_DB}** → Target **{E.TARGET_DB}**")
    if st.session_state.dirty:
        st.warning("Unsaved changes")
    if st.button("Reload saved mapping", width="stretch"):
        st.session_state.mapping = E.load_mapping()
        st.session_state.editor_version += 1
        st.session_state.dirty = False
        st.rerun()

FLAGS = flags_for(mapping())


# ══════════════════════════════════════════════════════════════════════════════
# Overview
# ══════════════════════════════════════════════════════════════════════════════

def relationship_dot(flags, focus: str | None = None) -> str:
    status = {t: table_status(flags, t) for t in TGT.tables}
    colour = {"ok": "#2e7d32", "warn": "#ef6c00", "error": "#c62828", "unmapped": "#9e9e9e"}
    fill = {"ok": "#e8f5e9", "warn": "#fff3e0", "error": "#ffebee", "unmapped": "#f5f5f5"}
    broken = {(f.target_table, f.target_column) for f in flags if f.code in ("C06", "D06") and f.severity in ("error", "warn")}
    mapped = {m["target_table"] for m in mapping()["tables"]}
    used_fk = {(m["target_table"], c.get("target")) for m in mapping()["tables"] for c in m.get("columns", [])}
    nodes, edges = set(), []
    for t, cols in TGT.tables.items():
        for c in cols.values():
            if not c.fk_to or c.fk_to[0] == "User" and c.name in E.TARGET_AUDIT_COLUMNS:
                continue
            p = c.fk_to[0]
            if focus and focus not in (t, p):
                continue
            if t not in mapped and p not in mapped and not focus:
                continue
            nodes |= {t, p}
            mapped_edge = (t, c.name) in used_fk
            col = "#c62828" if (t, c.name) in broken else ("#455a64" if mapped_edge else "#cfd8dc")
            style = "solid" if mapped_edge else "dashed"
            edges.append(f'"{p}" -> "{t}" [color="{col}", style={style}, tooltip="{t}.{c.name} → {p}", penwidth={2 if (t, c.name) in broken else 1}]')
    lines = ['digraph G { rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];',
             'edge [arrowsize=0.6];']
    for n in sorted(nodes):
        s = status.get(n, "unmapped")
        src = ", ".join(sorted({m["source_table"] for m in mapping()["tables"] if m["target_table"] == n}))
        label = f"{n}\\n← {src}" if src else n
        pen = 3 if n == focus else 1
        lines.append(f'"{n}" [label="{label}", color="{colour[s]}", fillcolor="{fill[s]}", penwidth={pen}];')
    lines += edges
    lines.append("}")
    return "\n".join(lines)


if page == "Overview":
    st.header("Mapping overview")
    mapped = {m["target_table"] for m in mapping()["tables"]}
    stats = {s: sum(1 for t in TGT.tables if table_status(FLAGS, t) == s) for s in STATUS_ICON}
    c = st.columns(5)
    c[0].metric("Target tables mapped", f"{len(mapped)} / {len(TGT.tables)}")
    c[1].metric("Table mappings", len(mapping()["tables"]))
    c[2].metric("🔴 Errors", sum(f.severity == "error" for f in FLAGS))
    c[3].metric("🟠 Warnings", sum(f.severity == "warn" for f in FLAGS))
    c[4].metric("Approved mappings", sum(m.get("status") == "approved" for m in mapping()["tables"]))

    st.subheader("Relationships between target tables")
    st.caption("Arrow = parent → child foreign key. Solid = mapped, dashed = not mapped, **red = mapped wrongly**. "
               "Box colour = table status (🟢 ok · 🟠 warnings · 🔴 errors · ⚪ not mapped). Audit links to User hidden.")
    st.graphviz_chart(relationship_dot(FLAGS), width="stretch")

    st.subheader("Target tables")
    rows = []
    for t in sorted(TGT.tables, key=lambda t: (["error", "warn", "ok", "unmapped"].index(table_status(FLAGS, t)), t)):
        tf = [f for f in FLAGS if f.target_table == t]
        rows.append({"": STATUS_ICON[table_status(FLAGS, t)], "Target table": t,
                     "Mapped from": ", ".join(m["source_table"] for m in mapping()["tables"] if m["target_table"] == t),
                     "Errors": sum(f.severity == "error" for f in tf), "Warnings": sum(f.severity == "warn" for f in tf),
                     "Approved": " / ".join("✔" if m.get("status") == "approved" else "draft"
                                            for m in mapping()["tables"] if m["target_table"] == t)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=560)


# ══════════════════════════════════════════════════════════════════════════════
# Map a table
# ══════════════════════════════════════════════════════════════════════════════

def source_options(m: dict, joins: list[dict]) -> list[str]:
    al = {E.DRIVING_ALIAS: m["source_table"], **{j["alias"]: j["table"] for j in joins if j.get("alias") and j.get("table")}}
    opts = [""]
    for a, t in al.items():
        opts += [f"{a}.{c}" for c in SRC.tables.get(t, {})]
    return opts


def column_frame(m: dict, tt: str) -> pd.DataFrame:
    by_target = {c["target"]: c for c in m.get("columns", [])}
    rows = []
    for name, col in TGT.tables[tt].items():
        c = by_target.get(name, {})
        key = "PK" if col.pk else (f"FK → {col.fk_to[0]}" if col.fk_to else "")
        rows.append({"target": name, "type": col.type, "key": key, "source": c.get("source", ""),
                     "transform": c.get("transform", "") if c else "",
                     "params": json.dumps(c["params"], ensure_ascii=False) if c.get("params") else "",
                     "status": c.get("status", "draft") if c else "", "notes": c.get("notes", "")})
    return pd.DataFrame(rows)


def frame_to_columns(df: pd.DataFrame, old: list[dict]) -> tuple[list[dict], list[str]]:
    old_by = {c["target"]: c for c in old}
    out, errors = [], []
    for r in df.to_dict("records"):
        if not (r.get("transform") or r.get("source")):
            continue
        c = {k: v for k, v in old_by.get(r["target"], {}).items() if k in ("confidence",)}
        c.update({"target": r["target"], "source": r.get("source") or "", "transform": r.get("transform") or "direct",
                  "status": r.get("status") or "draft", "notes": r.get("notes") or ""})
        if (r.get("params") or "").strip():
            try:
                c["params"] = json.loads(r["params"])
            except json.JSONDecodeError as e:
                errors.append(f"{r['target']}: params is not valid JSON ({e.msg})")
                c["params"] = {}
        out.append(c)
    return out, errors


def suggest(m: dict, df: pd.DataFrame, joins) -> pd.DataFrame:
    """Fill empty rows with the closest-named source column (by name similarity)."""
    opts = [o for o in source_options(m, joins) if o]
    names = {o.split(".", 1)[1].lower().replace("_", ""): o for o in opts}
    df = df.copy()
    for i, r in df.iterrows():
        if r["source"] or r["transform"]:
            continue
        hit = difflib.get_close_matches(r["target"].lower().replace("_", ""), list(names), n=1, cutoff=0.82)
        if hit:
            col = TGT.col(m["target_table"], r["target"])
            df.at[i, "source"] = names[hit[0]]
            df.at[i, "transform"] = "key" if col.pk else "fk_lookup" if col.fk_to else "direct"
            df.at[i, "status"] = "draft"
            df.at[i, "notes"] = "suggested by name"
    return df


if page == "Map a table":
    st.header("Map a table")
    tables = sorted(TGT.tables, key=lambda t: (["error", "warn", "ok", "unmapped"].index(table_status(FLAGS, t)), t))
    tt = st.selectbox("Target table", tables, format_func=lambda t: f"{STATUS_ICON[table_status(FLAGS, t)]}  {t}",
                      key="target_table")
    existing = [m for m in mapping()["tables"] if m["target_table"] == tt]
    choice = st.radio("Mapping", [E.mapping_id(m) for m in existing] + ["＋ New mapping"], horizontal=True, key=f"mchoice_{tt}")

    if choice == "＋ New mapping":
        with st.form(f"new_{tt}"):
            st.write(f"Which legacy table produces **{tt}** rows?")
            src_t = st.selectbox("Driving source table", sorted(SRC.tables))
            if st.form_submit_button("Create mapping"):
                pk = TGT.pk(tt)
                cols = [{"target": pk, "source": f"s.{SRC.pk(src_t)}", "transform": "key", "status": "draft"}] if pk else []
                mapping()["tables"].append({"id": f"{src_t}->{tt}", "target_table": tt, "source_table": src_t, "joins": [],
                                            "filter": "", "status": "draft", "notes": "", "columns": cols})
                st.session_state.dirty = True
                st.session_state[f"mchoice_{tt}"] = f"{src_t}->{tt}"
                st.rerun()
        st.stop()

    m = next(x for x in existing if E.mapping_id(x) == choice)
    v = st.session_state.editor_version
    key = f"{choice}|{v}"

    left, right = st.columns([3, 2])
    with left:
        c1, c2, c3 = st.columns([2, 2, 1])
        src_t = c1.selectbox("Driving source table (alias s)", sorted(SRC.tables), index=sorted(SRC.tables).index(m["source_table"]),
                             key=f"src_{key}")
        status = c2.selectbox("Mapping status", ["draft", "approved"], index=["draft", "approved"].index(m.get("status", "draft")),
                              key=f"status_{key}")
        flt = st.text_input("Filter (T-SQL on the aliases, e.g. s.Deleted = 0)", m.get("filter", ""), key=f"filter_{key}")
        st.markdown("**Joins** — bring in related legacy tables (e.g. Person for a contact's name)")
        jdf = st.data_editor(pd.DataFrame(m.get("joins") or [], columns=["alias", "table", "type", "on"]), num_rows="dynamic",
                             width="stretch", key=f"joins_{key}",
                             column_config={"table": st.column_config.SelectboxColumn(options=sorted(SRC.tables)),
                                            "type": st.column_config.SelectboxColumn(options=["LEFT", "INNER"], default="LEFT"),
                                            "on": st.column_config.TextColumn(help="e.g. p.Person_ID = s.Person_ID", width="large")})
        joins = [{k: (r[k] if pd.notna(r[k]) else "") for k in ("alias", "table", "type", "on")} for r in jdf.to_dict("records")
                 if r.get("alias") and r.get("table")]
        notes = st.text_area("Notes", m.get("notes", ""), height=68, key=f"notes_{key}")

    with right:
        st.markdown(f"**Relationships of {tt}**")
        rel = []
        for c in TGT.tables[tt].values():
            if c.fk_to:
                rel.append({"": STATUS_ICON[table_status(FLAGS, c.fk_to[0])], "direction": "parent",
                            "via": f"{tt}.{c.name}", "table": c.fk_to[0],
                            "loaded from": ", ".join(sorted(E.Context(SRC, TGT, mapping()).parent_sources(c.fk_to[0]))) or "— not mapped"})
        for c in TGT.children_of(tt):
            if c.name in E.TARGET_AUDIT_COLUMNS:
                continue
            rel.append({"": STATUS_ICON[table_status(FLAGS, c.table)], "direction": "child", "via": f"{c.table}.{c.name}",
                        "table": c.table, "loaded from": ", ".join(sorted(E.Context(SRC, TGT, mapping()).parent_sources(c.table))) or "— not mapped"})
        st.dataframe(pd.DataFrame(rel), hide_index=True, width="stretch", height=260)
        st.graphviz_chart(relationship_dot(FLAGS, focus=tt), width="stretch")

    st.markdown("**Columns** — every target column; pick a source column and a transform. Leave both empty to skip a column.")
    base = column_frame(m, tt)
    if st.button("✨ Suggest unmapped columns by name", key=f"suggest_{key}"):
        st.session_state[f"suggested_{choice}"] = suggest({**m, "source_table": src_t}, base, joins)
        st.session_state.editor_version += 1
        st.rerun()
    if f"suggested_{choice}" in st.session_state:
        base = st.session_state.pop(f"suggested_{choice}")
        st.session_state.dirty = True
    opts = source_options({**m, "source_table": src_t}, joins)
    edited = st.data_editor(
        base, hide_index=True, width="stretch", height=min(38 * (len(base) + 1), 720), key=f"cols_{key}",
        disabled=["target", "type", "key"],
        column_config={
            "source": st.column_config.SelectboxColumn(options=opts, width="medium"),
            "transform": st.column_config.SelectboxColumn(options=[""] + list(E.TRANSFORMS), width="small",
                                                          help="\n".join(f"{t.name}: {t.label}" for t in E.TRANSFORMS.values())),
            "params": st.column_config.TextColumn(help='JSON, e.g. {"map": {"1": "Active"}} or {"table": "Roles", "key": "Role_ID", "value": "Description"}'),
            "status": st.column_config.SelectboxColumn(options=["", "draft", "approved"], width="small"),
            "notes": st.column_config.TextColumn(width="medium")})

    new_cols, json_errors = frame_to_columns(edited, m.get("columns", []))
    candidate = copy.deepcopy(mapping())
    cm = next(x for x in candidate["tables"] if E.mapping_id(x) == choice)
    cm.update({"source_table": src_t, "status": status, "filter": flt, "joins": joins, "notes": notes, "columns": new_cols,
               "id": f"{src_t}->{tt}"})
    live = [f for f in flags_for(candidate) if f.mapping == E.mapping_id(cm) or (f.target_table == tt and not f.mapping)]
    changed = json.dumps(cm, sort_keys=True) != json.dumps(m, sort_keys=True)

    st.markdown("**Flags for this mapping** (live — reflect unsaved edits)")
    for e in json_errors:
        st.error(e)
    if live:
        st.dataframe(pd.DataFrame([{"": SEV_ICON[f.severity], "column": f.target_column, "code": f.code,
                                    "problem": f.message, "how to fix": f.hint} for f in live]),
                     hide_index=True, width="stretch")
    else:
        st.success("No flags — this mapping is clean.")
    errs = sum(f.severity == "error" for f in live)
    b1, b2, b3 = st.columns([1, 1, 4])
    if b1.button("💾 Save", type="primary", disabled=not changed and not st.session_state.dirty, key=f"save_{key}"):
        idx = next(i for i, x in enumerate(mapping()["tables"]) if E.mapping_id(x) == choice)
        mapping()["tables"][idx] = cm
        save()
        st.session_state[f"mchoice_{tt}"] = E.mapping_id(cm)
        st.rerun()
    if b2.button("🗑 Delete mapping", key=f"del_{key}"):
        mapping()["tables"] = [x for x in mapping()["tables"] if E.mapping_id(x) != choice]
        save()
        st.rerun()
    b3.caption(("🔴 This mapping has errors — the SQL generator will **block** it until they are fixed."
                if errs else "🟢 No errors — this mapping will be generated.") + (" · unsaved edits" if changed else ""))

    with st.expander(f"Source data preview — {src_t}"):
        probe, _ = data_probe(st.session_state.data_source)
        if probe:
            try:
                st.dataframe(probe.con.execute(f'SELECT * FROM "{src_t}" LIMIT 20').df(), width="stretch")
            except Exception as e:                       # noqa: BLE001
                st.info(f"Preview unavailable: {e}")
        st.dataframe(pd.DataFrame([{"column": c.name, "type": c.type, "key": "PK" if c.pk else (f"FK → {c.fk_to[0]}" if c.fk_to else "")}
                                   for c in SRC.tables[src_t].values()]), hide_index=True, width="stretch")

    with st.expander("Transform reference"):
        st.dataframe(pd.DataFrame([{"transform": t.name, "what it does": t.label, "parameters": ", ".join(t.params), "notes": t.help}
                                   for t in E.TRANSFORMS.values()]), hide_index=True, width="stretch")


# ══════════════════════════════════════════════════════════════════════════════
# Flags
# ══════════════════════════════════════════════════════════════════════════════

if page == "Flags":
    st.header("Flags")
    c1, c2, c3 = st.columns(3)
    sev = c1.multiselect("Severity", ["error", "warn", "info"], default=["error", "warn"])
    codes = sorted({f.code for f in FLAGS})
    code = c2.multiselect("Code", codes, format_func=lambda c: f"{c} — {CODE_HELP.get(c, '')}")
    tbl = c3.multiselect("Target table", sorted({f.target_table for f in FLAGS}))
    shown = [f for f in FLAGS if f.severity in sev and (not code or f.code in code) and (not tbl or f.target_table in tbl)]
    st.caption(f"{len(shown)} of {len(FLAGS)} flags. 🔴 errors block SQL generation for that mapping; "
               "🟠 warnings are generated but should be reviewed; 🔵 info is for completeness.")
    st.dataframe(pd.DataFrame([{"": SEV_ICON[f.severity], "code": f.code, "target": f"{f.target_table}.{f.target_column}".rstrip("."),
                                "mapping": f.mapping, "problem": f.message, "how to fix": f.hint} for f in shown]),
                 hide_index=True, width="stretch", height=620)
    with st.expander("What the codes mean"):
        st.dataframe(pd.DataFrame([{"code": k, "meaning": v} for k, v in CODE_HELP.items()]), hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# Generate SQL
# ══════════════════════════════════════════════════════════════════════════════

if page == "Generate SQL":
    import generate_sql as G
    st.header("Generate the migration SQL")
    st.write("Uses the **saved** mapping. Mappings with 🔴 errors, or whose parent tables are not migrated, are blocked.")
    if st.session_state.dirty:
        st.warning("You have unsaved changes — save them on the *Map a table* page first.")
    approved_only = st.checkbox("Only mappings marked approved")
    if st.button("⚙️ Generate scripts", type="primary"):
        probe, _ = data_probe(st.session_state.data_source)
        g = G.Generator(E.load_mapping(), approved_only=approved_only, data=probe)
        st.session_state.generated = {"paths": [str(p) for p in g.write()], "blocked": dict(g.blocked), "live": len(g.live)}
    gen = st.session_state.get("generated")
    if gen:
        c = st.columns(3)
        c[0].metric("Mappings generated", gen["live"])
        c[1].metric("Blocked", len(gen["blocked"]))
        c[2].metric("Scripts", len(gen["paths"]))
        if gen["blocked"]:
            st.subheader("🔴 Blocked")
            st.dataframe(pd.DataFrame([{"mapping": k, "why": " · ".join(dict.fromkeys(v))} for k, v in sorted(gen["blocked"].items())]),
                         hide_index=True, width="stretch")
        st.subheader("Scripts (sql/target)")
        pick = st.selectbox("Preview", [Path(p).name for p in gen["paths"]])
        st.code(Path(G.OUT / pick).read_text(encoding="utf-8")[:20000], language="sql")
        st.divider()
        st.write(f"Run against **localhost\\SQLEXPRESS**: drops and recreates **{E.TARGET_DB}**, loads it, adds FKs, reconciles.")
        if st.button("▶️ Run migration on SQL Server"):
            import subprocess
            import pyodbc
            log = []
            ok = True
            with st.status("Running scripts…", expanded=True) as s:
                for p in gen["paths"]:
                    name = Path(p).name
                    if name.startswith("90_"):
                        continue
                    r = subprocess.run(["sqlcmd", "-S", G.SERVER, "-E", "-b", "-f", "65001", "-i", p], capture_output=True, text=True)
                    st.write(("✅ " if r.returncode == 0 else "❌ ") + name)
                    if r.returncode:
                        st.code((r.stdout + r.stderr)[-3000:])
                        ok = False
                        break
                s.update(label="Done" if ok else "Failed", state="complete" if ok else "error")
            if ok:
                cn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={G.SERVER};DATABASE={E.TARGET_DB};Trusted_Connection=yes;")
                sql = (G.OUT / "90_reconcile.sql").read_text(encoding="utf-8").split(f"USE [{E.TARGET_DB}];", 1)[1]
                cur = cn.cursor()
                cur.execute(sql)
                titles = ["Reconciliation per mapping", "Foreign keys", "Rejected / nulled / truncated values"]
                i = 0
                while True:
                    cols = [d[0] for d in cur.description]
                    st.subheader(titles[i] if i < len(titles) else f"Result {i + 1}")
                    st.dataframe(pd.DataFrame.from_records(cur.fetchall(), columns=cols), hide_index=True, width="stretch")
                    i += 1
                    if not cur.nextset():
                        break
