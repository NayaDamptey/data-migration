# AI mapping for unknown sources

The model never guesses from column names alone. Code gathers evidence, the
LLM reasons over it, and people approve anything uncertain.

## 1. Profile (no AI)
`pipeline/profiling/profile_source.py` records, for every column: row count,
null rate, distinct count, min/max length, top values, samples, and detected
patterns (email, UK phone, postcode, date formats, URL, money, HTML/RTF).

## 2. Discover structure (no AI)
- Primary keys: unique, never null.
- Foreign keys: ≥ 95% of values found in another table's key.
- Link tables and polymorphic links (`LinkType` + `LinkID`).
This gives a relationship graph. Tables referenced by jobs and contacts are
probably Clients; a table joining candidates to jobs with dates and a fee is
probably Placements.

## 3. Classify tables → canonical entities (LLM)
Input: table profiles, relationships, `canonical/model.yaml` descriptions.
Output (JSON): `{table, entity | "split" | "ignore", confidence, reason}`.

## 4. Match fields (retrieval, then LLM)
Narrow the candidates cheaply first:
- name similarity (embeddings): `Forename` ≈ `first_name`
- value-pattern match: an email field needs a mostly-email column
- past approved mappings for this source system

Then the LLM picks from the top 3–5 candidates and may propose a transform
(see the list in `mappings/README.md`).

## 5. Map values
For enum fields, send distinct values + counts; get a value → canonical-value
table. Anything the model can't place is flagged, not forced.

## 6. Output a spec, not data
Everything lands in a mapping spec (see `mappings/tracker.example.yaml`).
Code generates SQLMesh models from it.

## 7. Validate, then review
Run the mapping and check it: do mapped emails pass validation, do foreign
keys join, did row counts survive? Failures lower confidence. Anything under
the threshold (default 0.85) shows as "Needs review" in the UI.

## 8. Learn
Store every approved or corrected mapping, keyed by source system + column
profile. Retrieval finds these before the LLM is asked, so repeat systems
mostly map themselves.

## Where AI is weak: ask instead of guessing
Business meaning ("Status = 3"), duplicates across tables, inconsistently
used fields. The model writes a **question** into the spec, which the UI shows
to a (possibly non-technical) staff member:

> Values 1–5 appear in `CANDIDATE.Stage`. Which one means *Placed*?

## Data protection
Send profiles and masked samples (e.g. `a****@mail.example`), never full
tables. Keep an allow-list of what may leave the platform.
