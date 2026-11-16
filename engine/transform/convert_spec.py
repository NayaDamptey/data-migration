"""
transform/convert_spec.py  (one-off)

Converts the prototype's T-SQL mapping (mapping/tiers.py) into the mapping spec the platform runs on:
DuckDB SQL, one YAML file per layer (spec/middle.yml, spec/target.yml). From here on the spec is the
source of truth; dbt models are generated from it (transform/build_dbt.py).

Source tables are written as src__<Table> and middle-tier tables as mid__<Table>; the generator turns
them into dbt source() / ref() calls.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "mapping"))
import tiers as T  # noqa: E402


def _stringy(n: exp.Expression) -> bool:
    if isinstance(n, exp.Literal) and n.is_string:
        return True
    if isinstance(n, exp.Cast) and n.to.this in (exp.DataType.Type.TEXT, exp.DataType.Type.VARCHAR, exp.DataType.Type.NVARCHAR):
        return True
    if isinstance(n, exp.Column) and n.name.lower() in {"fullname"}:
        return True
    if isinstance(n, (exp.Upper, exp.Lower, exp.Substring, exp.Left, exp.Right, exp.Trim, exp.Initcap)):
        return True
    return isinstance(n, (exp.DPipe, exp.Concat)) or (isinstance(n, exp.Add) and (_stringy(n.left) or _stringy(n.right)))


def _fix(node: exp.Expression) -> exp.Expression:
    # T-SQL joins text with '+'; DuckDB uses '||'
    def tx(n):
        if isinstance(n, exp.Add) and (_stringy(n.left) or _stringy(n.right)):
            return exp.DPipe(this=n.left, expression=n.right, safe=True)
        return n
    return node.transform(tx)


def _sql(node: exp.Expression) -> str:
    s = node.sql("duckdb")
    s = re.sub(r"\bTEXT\(\d+\)", "VARCHAR", s)
    return s


def _ph(layer, s: str) -> str:
    pre = "src__" if layer is T.MIDDLE else "mid__"
    return re.sub(r"\{src\}\[?(\w+)\]?", lambda m: f"{pre}{m.group(1)}", s)


def convert(layer) -> dict:
    o = T.load_overrides()
    entities = []
    for e in layer.entities:
        inserts = []
        for n, ins in enumerate(e.inserts):
            cols = list(ins.columns)
            body = ",\n".join(f"{_ph(layer, T.expression(layer, e, n, c, o))} AS {c}" for c in cols)
            sql = f"SELECT {body} FROM {_ph(layer, ins.source)} " + " ".join(_ph(layer, j) for j in ins.joins)
            if ins.where:
                sql += f" WHERE {_ph(layer, ins.where)}"
            tree = _fix(sqlglot.parse_one(sql, read="tsql"))
            columns = {p.alias: _sql(p.this) for p in tree.expressions}
            frm = _sql(tree.args["from"].this)
            joins = []
            for j in tree.args.get("joins") or []:
                js = _sql(j)
                if "LATERAL" in js and " ON " not in js.split(")")[-1]:
                    js += " ON TRUE"
                joins.append(js)
            where = _sql(tree.args["where"].this) if tree.args.get("where") else ""
            checks = []
            for c in ins.checks:
                ct = _fix(sqlglot.parse_one(f"SELECT 1 WHERE {_ph(layer, c.cond)}", read="tsql"))
                checks.append({"condition": _sql(ct.args["where"].this), "reason": c.reason, "action": c.action})
            item = {"from": frm, "joins": joins, "where": where, "columns": columns}
            if checks:
                item["checks"] = checks
            inserts.append(item)
        ent = {"key": e.key, "table": e.table, "label": e.label, "selects": inserts}
        if e.types:
            ent["types"] = {c: t.replace("NVARCHAR(MAX)", "VARCHAR").replace("NVARCHAR(200)", "VARCHAR").replace("NVARCHAR(50)", "VARCHAR")
                            .replace("DATETIME2(0)", "TIMESTAMP").replace("BIT", "BOOLEAN") for c, t in e.types.items()}
        entities.append(ent)
    return {"layer": layer.name, "entities": entities}


def main():
    out = HERE / "spec"
    out.mkdir(exist_ok=True)
    for layer in (T.MIDDLE, T.TARGET):
        spec = convert(layer)
        (out / f"{layer.name}.yml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")
        print(f"{layer.name}: {len(spec['entities'])} entities -> spec/{layer.name}.yml")


if __name__ == "__main__":
    main()
