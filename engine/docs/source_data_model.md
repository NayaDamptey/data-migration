# Source data model and validation

The legacy source (`Cobaltdesk_Legacy`) is built in three layers:

| Layer | Where | Guarantee |
|---|---|---|
| Clean baseline | `sample_data/source/*.csv` | Passes every rule in `validation/baseline_rules.py` (0 violations) |
| Relational DB | `sql/source/01..03_*.sql` | 156 FKs created `WITH CHECK` on the baseline |
| Legacy defects | `sql/source/04_inject_legacy_defects.sql` | Every row of `defect_manifest.csv` is caught by at least one rule |

## Roles

The legacy schema stores everyone in `Person`. The baseline gives every person a clear role:

| Role | Who | Appears in |
|---|---|---|
| **Contact** (client side) | Persons with an `Associates` row. Each belongs to an account (`AccountAssociates`), uses that account's office address, and has one `Contact` row in `AssociateTypeRelation`. | `Req.AssociateID` (hiring manager), `Req_Hired.Associate_ID`, `Leads.Associate_ID`, `Schedule` (Person_Type = Contact), interviewer columns of `Interview_Feedback` |
| **Candidate** | Persons without an `Associates` row | `Emp_Profile`, `CV_Docs`, `BackgroundChecks`, `ObjectHotlist`, `Interview_Feedback.Interviewee_ID`, `Schedule` (Person_Type = Candidate), `Req_Hired.Invoiced_PersonID` (the person placed), `TimesheetItems.Person_ID` (the contractor placed on that job) |
| **Dual role** (edge case) | 5 people who are both, listed in `sql/source/edge_cases.csv` | Valid data. Common in recruitment. Must survive the migration and must not be "cleaned". |

`Person.Associate` and `Person.Emp` flags mirror these roles.

## Consistency rules the baseline satisfies

* **Integrity:** PKs unique, all 156 FKs and the 4 polymorphic links (`Notes`, `Documents`, `TagEntity`, `Log`) resolve.
* **Contacts:** every contact is linked to an account. The title matches the first-name gender. The address is the account office. The office email uses the account's website domain. Any contact on a job, placement, lead or meeting belongs to that account.
* **Jobs and placements:** a placement's account is its job's account, and it starts on or after the job was raised. Meetings about a job are with that job's client. Each timesheet line belongs to a contractor placed on that job.
* **Finance:** line = qty × price, net = sum of lines, gross = net + 20% VAT. Paid and balance follow the status. An invoice's PO and a PO's job belong to the invoiced client.
* **Formats and ranges:** email, UK postcode, phone, NI number and sort code formats. Coded values come from fixed lists. Names have no padding or ALL-CAPS. DOB is between 1940 and 16 years ago. Rates are positive with a positive margin. Lead score is 1–5. Hours are in (0, 24]. Geocodes are inside the UK. No mojibake.
* **Soft deletes:** no deleted parent with live children.

## Running it

```bash
python sample_data/build_source_db.py                         # rebuild baseline + SQL scripts
python -m validation.validator                                # rules on the clean CSVs (must be 0)
python sample_data/build_source_db.py --load                  # build Cobaltdesk_Legacy in SQL Server
python -m validation.validator --source sqlserver --score     # rules on the legacy DB vs the answer key
pytest tests/ -v                                              # both of the above as tests
```

Violations on the legacy DB that are not in the answer key are **collateral**: the same rules return 0 on the baseline, so every one is caused by a planted defect. For example, an orphaned `Req_Hired.Req_ID` also leaves that job's timesheet lines without a placed contractor.

## Timesheets

* A timesheet covers one Monday–Sunday week, for one contractor and one job, and falls inside that contractor's placement dates.
* Lines carry the timesheet's type. Hours = clock span minus a 30-minute break for shifts of 6 hours or more.
* The schema has no work date on a line, so `TimesheetItems.CreatedAt` records the day worked.
* Hourly rates = the job's day rate / 7.5, × 1.5 for Overtime. Non-billable types (Training, Sick Leave, Bank Holiday) bill 0, and Sick Leave and Bank Holiday also pay 0.
* An approved timesheet has an approver and an approval date after the week ends. Any other status has neither.
* 5 timesheets are empty (created, never filled in). They are kept as realistic legacy data.

## Tracing one entity end to end

`sql/profiling/02_entity_trace.sql` follows one placement (default `Req_HiredID = 98`) through 30+ tables in 27 queries. Every link has a `chk_*` column showing ✔ or ✘ with a reason. To trace another placement, replace `Req_HiredID = 98` throughout the file.

* On `Cobaltdesk_Clean` (the baseline with no defects), all 310 placements pass all 14,007 checks.
* On `Cobaltdesk_Legacy`, the failures come only from planted defects. Placement 98 is untouched by defects and passes all 143 of its checks.

## Known limits (not yet modelled)

* `Emp_Profile.Profile_Notes` starts with the right name, but the rest of the AI-written text may describe a different background.
* Some real organisations (e.g. BAE Systems, Barclays, NHS Digital) appear with invented details.
