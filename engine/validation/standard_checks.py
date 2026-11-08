"""
validation/standard_checks.py

The standard data quality checks every migration is held to. Each one is a named,
plain-English check made of one or more rules from validation/baseline_rules.py,
so the dashboard, the tests and the reports all use the same definition.

A check PASSES when none of its rules find a problem, FAILS otherwise, and is
NOT RUN when none of its rules could run (e.g. the tables were not uploaded).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from validation.baseline_rules import RULES, Rule

# candidate-side links: a record that belongs to a candidate whose person is missing
CANDIDATE_LINKS = {
    "fk.Emp_Profile.Person_ID", "fk.CV_Docs.CV_AssocID", "fk.BackgroundChecks.Person_ID", "fk.ObjectHotlist.Person_ID",
    "fk.Interview_Feedback.Interviewee_ID", "fk.Req_Hired.Invoiced_PersonID", "fk.TimesheetItems.Person_ID",
    "fk.EmpHist.Emp_ID", "fk.EmpEdu.Emp_ID", "fk.EmpRef.EmpNo", "fk.EmpRef.Ref_ID", "fk.Emp_Documents.Emp_ID",
    "fk.Emp_Documents.Person_ID", "fk.Schedule.Person_ID", "fk.GDPR_Consent.Person_ID",
}
# document links: a document reference that points nowhere, or a document attached to nothing
DOCUMENT_LINKS = {
    "fk.Req_Documents.Req_ID", "fk.Req_Documents.Document_ID", "fk.Emp_Documents.Document_ID",
    "fk.RecruiterDocuments.Recruiter_ID", "fk.RecruiterDocuments.Document_ID", "fk.BackgroundChecks.Doc_ID",
    "fk.Leads.Document_ID", "fk.Invoice.Document_ID", "fk.ComplianceItems.Comp_DocID", "fk.Documents.Typeid",
    "poly.Documents.Doc_AssocID", "attached.document", "attached.cv",
}
NOTE_LINKS = {"poly.Notes.ObjectId", "attached.note"}


@dataclass(frozen=True)
class StandardCheck:
    id: str
    name: str
    why: str
    rule_ids: frozenset = field(default_factory=frozenset)


def _ids(pred) -> frozenset:
    return frozenset(r.id for r in RULES if pred(r))


def _cat(*cats) -> frozenset:
    return _ids(lambda r: r.category in cats)


STANDARD_CHECKS: list[StandardCheck] = [
    StandardCheck("duplicate_people", "Duplicate people",
                  "The same person twice splits their history, CVs and consent across two records.",
                  _cat("DUPLICATE_PERSON", "DUPLICATE_ASSOCIATE")),
    StandardCheck("duplicate_entities", "Duplicate companies, jobs and transactions",
                  "Duplicate clients and jobs split placements and invoices; double-entered timesheets overbill.",
                  _cat("DUPLICATE_ACCOUNT", "DUPLICATE_JOB", "DUPLICATE_TRANSACTION", "SPLIT_HISTORY")),
    StandardCheck("deleted_still_active", "Deleted records still active",
                  "A record marked deleted that still has open jobs, live placements or active contacts.",
                  _cat("SOFT_DELETE_CONFLICT")),
    StandardCheck("placements_on_deleted", "Placements on deleted jobs or companies",
                  "A live placement whose job or company is soft-deleted.",
                  _cat("PLACEMENT_ON_DELETED")),
    StandardCheck("orphaned_contacts", "Orphaned contacts",
                  "A contact linked to no company.",
                  frozenset({"orphan.contact"})),
    StandardCheck("orphaned_documents", "Orphaned documents",
                  "A document or CV linked to no record.",
                  frozenset({"orphan.document", "orphan.cv"})),
    StandardCheck("orphaned_notes", "Orphaned notes",
                  "A note linked to no record.",
                  frozenset({"orphan.note"})),
]

_known = {r.id for r in RULES}
for _c in STANDARD_CHECKS:
    _missing = set(_c.rule_ids) - _known
    assert not _missing, f"standard check {_c.id} names unknown rules: {_missing}"
    assert _c.rule_ids, f"standard check {_c.id} has no rules"


def evaluate(results: dict[str, list], applicable: set[str]) -> list[dict]:
    """results: rule id -> violating rows [(pk, detail), ...] for rules that failed;
    applicable: ids of every rule that ran. Returns one summary per standard check."""
    rule_table = {r.id: r.table for r in RULES}
    out = []
    for c in STANDARD_CHECKS:
        ran = [rid for rid in c.rule_ids if rid in applicable]
        failing = [rid for rid in ran if results.get(rid)]
        records = {(rule_table[rid], str(row[0])) for rid in failing for row in results[rid]}
        out.append({
            "id": c.id, "name": c.name, "why": c.why,
            "status": "not_run" if not ran else ("fail" if failing else "pass"),
            "rules": len(c.rule_ids), "rules_run": len(ran), "rules_failing": len(failing),
            "violations": sum(len(results[rid]) for rid in failing), "records": len(records),
            "rule_ids": sorted(c.rule_ids), "failing_rule_ids": sorted(failing),
        })
    return out
