"""
mapping/seed_from_canonical.py

Builds the first draft of mapping/migration_mapping.json by composing the two
reviewed stages that already exist:

    approved_source_to_canonical.json   (legacy table/column -> canonical field)
  o approved_canonical_to_target.json   (canonical field     -> target table/column)
  = legacy column -> target column

Rules
  * target primary key           -> transform 'key'
  * target foreign key           -> transform 'fk_lookup'
  * named lookups (lookup_role…) -> generic 'lookup' with explicit table/key/value
  * anything else keeps its stage transform; unknown names are left as-is so the
    validator flags them (the AI draft named transforms that were never defined)

Run once:  python mapping/seed_from_canonical.py [--force]
After that, edit the mapping in the web UI (frontend, Schema mapping).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import MAPPING_FILE, ROOT, load_target_schema, save_mapping  # noqa: E402

S2C = ROOT / "mapping" / "approved_source_to_canonical.json"
C2T = ROOT / "mapping" / "approved_canonical_to_target.json"

LOOKUPS = {
    "lookup_role": {"table": "Roles", "key": "Role_ID", "value": "Description"},
    "lookup_roles_table": {"table": "Roles", "key": "Role_ID", "value": "Description"},
    "lookup_account_type": {"table": "AccountType", "key": "AccountTypeID", "value": "Description"},
    "lookup_division": {"table": "Division", "key": "DivisionID", "value": "Division_Name"},
    "lookup_doc_type": {"table": "DocumentType", "key": "Doc_TypeID", "value": "Desc"},
    "lookup_inv_type": {"table": "InvoiceTypes", "key": "InvoiceType_ID", "value": "Type_Name"},
    "lookup_ts_type": {"table": "TimesheetType", "key": "Timesheet_TypeID", "value": "Desc"},
}


def compose() -> dict:
    s2c = json.loads(S2C.read_text(encoding="utf-8"))["mappings"]
    c2t = json.loads(C2T.read_text(encoding="utf-8"))["mappings"]
    tgt = load_target_schema()
    tables = []
    for source_table, sm in s2c.items():
        entity = sm["canonical_entity"]
        for key, tm in c2t.items():
            if not (key == entity or key.startswith(entity.replace("canonical_", "canonical_") + "_to_")):
                continue
            target_table = tm["target_table"]
            by_canonical = {c["canonical"]: c for c in tm["columns"]}
            cols, used = [], set()
            for sc in sm["columns"]:
                tc = by_canonical.get(sc["canonical"])
                if not tc or tc["target"] in used:
                    continue
                used.add(tc["target"])
                tcol = tgt.col(target_table, tc["target"])
                t1, t2 = sc.get("transform", "direct"), tc.get("transform", "direct")
                transform = t2 if t2 != "direct" else t1
                params = None
                if tcol and tcol.pk:
                    transform = "key"
                elif tcol and tcol.fk_to:
                    transform = "fk_lookup"
                elif transform in LOOKUPS:
                    params, transform = dict(LOOKUPS[transform]), "lookup"
                col = {"target": tc["target"], "source": f"s.{sc['source']}", "transform": transform,
                       "confidence": round(min(sc.get("confidence", 1), tc.get("confidence", 1)), 2),
                       "status": "approved" if "approved" == sc.get("decision") == tc.get("decision") else "draft",
                       "notes": " | ".join(n for n in (sc.get("notes"), tc.get("notes")) if n)}
                if params:
                    col["params"] = params
                cols.append(col)
            tables.append({"id": f"{source_table}->{target_table}", "target_table": target_table,
                           "source_table": source_table, "joins": [], "filter": sm.get("filter") or "",
                           "status": "draft", "notes": f"Seeded from canonical entity {entity}", "columns": cols})
    return {"_meta": {"seeded_from": [S2C.name, C2T.name]}, "tables": tables}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite an existing migration_mapping.json")
    args = ap.parse_args()
    if MAPPING_FILE.exists() and not args.force:
        sys.exit(f"{MAPPING_FILE} exists — edit it in the UI, or pass --force to re-seed (loses UI edits)")
    m = compose()
    save_mapping(m, user="seed")
    print(f"Seeded {len(m['tables'])} table mappings, {sum(len(t['columns']) for t in m['tables'])} columns -> {MAPPING_FILE}")
