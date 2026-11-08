"""
frontend/scripts/make_demo_data.py

Snapshots the API's answers for the legacy sample data into frontend/public/demo/, so the
frontend can run as a self-contained demo (NEXT_PUBLIC_DEMO=1) with no API or database —
e.g. a portfolio site on Vercel.

    # with the API running (cd backend && APP_ENV=development uvicorn app.main:app --port 8000)
    python frontend/scripts/make_demo_data.py [--api http://127.0.0.1:8000]

Writes
    public/demo/report.json        GET /dq/report?source=legacy
    public/demo/duplicates.json    GET /dq/duplicates?source=legacy
    public/demo/rules/<id>.json    GET /dq/rules/<id>?source=legacy   (every failing rule)
    public/demo/uploads.json       the source tables shown as already-uploaded files

Real organisations that appear in the generated notes are replaced with fictional ones.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "public" / "demo"

# real organisation -> fictional stand-in (applied to every text value)
REPLACE = {
    "BAE Systems": "Northgate Defence", "BAE": "Northgate",
    "Barclays": "Bramwell Bank", "NatWest": "Westgate Bank", "HSBC": "Harbourline Bank",
    "Lloyds": "Larchmont Bank", "RBS": "Royal Borough Bank", "Santander": "Sandford Bank",
    "KPMG": "Kestler Audit", "Deloitte": "Dellmont Advisory", "PwC": "Pemberly Waite",
    "IBM": "Ionic Systems", "Accenture": "Ascent Consulting", "Capgemini": "Capstone Digital",
    "Thoughtworks": "Thinkwell Consulting", "Michael Page": "Mitchell Pace Recruitment",
    "NHS Digital": "Civic Health Digital", "NHS": "public health", "BBC": "Broadcast North", "ITV": "Channel North",
    "Vodafone": "Vocalis Mobile", "National Grid": "Northern Grid", "GlaxoSmithKline": "Glenmore Pharma",
    "AstraZeneca": "Astrid Life Sciences", "Rolls-Royce": "Royce Engineering", "Network Rail": "Northline Rail",
}
PATTERN = re.compile(r"\b(" + "|".join(sorted(map(re.escape, REPLACE), key=len, reverse=True)) + r")\b")


def scrub(value):
    if isinstance(value, str):
        return PATTERN.sub(lambda m: REPLACE[m.group(1)], value)
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


def get(api: str, path: str):
    with urllib.request.urlopen(api + path, timeout=600) as r:
        return scrub(json.loads(r.read()))


def post(api: str, path: str):
    req = urllib.request.Request(api + path, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def write(name: str, data):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    api = ap.parse_args().api.rstrip("/")
    shutil.rmtree(OUT, ignore_errors=True)

    report = get(api, "/dq/report?source=legacy&refresh=true")
    # the demo has no "real" decisions: start every pair undecided
    dups = get(api, "/dq/duplicates?source=legacy")
    for p in dups["pairs"]:
        p["decision"] = None
    for e in dups["entities"].values():
        e["to_review"] = e["total"]
    report["duplicate_review"].update(merged=0, not_duplicate=0, to_review=report["duplicate_review"]["total"])

    size = write("report.json", report) + write("duplicates.json", dups)
    for r in report["rules"]:
        size += write(f"rules/{r['id']}.json", get(api, f"/dq/rules/{urllib.parse.quote(r['id'])}?source=legacy&limit=200"))

    for layer in ("middle", "target"):
        post(api, f"/layers/{layer}/run")
        summary = get(api, f"/layers/{layer}/summary")
        size += write(f"layers/{layer}_summary.json", summary) + write(f"layers/{layer}.json", get(api, f"/layers/{layer}"))
        for entity in summary["entities"]:
            size += write(f"layers/{layer}/{entity}.json", get(api, f"/layers/{layer}/{urllib.parse.quote(entity)}/rows?limit=300"))
    size += write("layers/target_rejects.json", get(api, "/layers/target/rejects"))

    uploads = [{"name": f"{t['table']}.csv", "rows": t["rows"], "size": max(200, t["rows"] * 140),
                "columns": t["columns"]} for t in sorted(report["tables"], key=lambda t: t["table"].lower())]
    size += write("uploads.json", uploads)
    leftovers = [k for k in REPLACE if re.search(rf"\b{re.escape(k)}\b", "".join(p.read_text(encoding="utf-8") for p in OUT.rglob("*.json")))]
    print(f"Demo data: {len(report['rules'])} rules, {len(dups['pairs'])} duplicate pairs, {len(uploads)} tables, "
          f"{size // 1024} KB -> {OUT}")
    print("Real names left:", leftovers or "none")


if __name__ == "__main__":
    main()
