# Screens

Original sketches: `docs/sketches/`.

| # | Screen | Sketch | Route (frontend) |
|---|---|---|---|
| 1 | Sign in: username, password, keep me signed in, OK/Cancel | `1-login.jpeg` | `/` |
| 2 | Set up migration: source system + format, target system + database + output; Inspect, Run canonical layer, Run target, Get data; runs & versions; request a change | `2-setup.jpeg` | `/workspace` |
| 3 | Canonical review: entities list, all canonical fields with source column, sample, status; OK/Cancel | `3-canonical-fields.jpeg` | `/canonical` |
| 4 | Target values: entity → target file, preview, validation counts; Get data/Cancel | `4-target-values.jpeg` | `/target` |

Design note from the sketch: *"We can request data via UI, as staff may not
be technical."* Keep all labels in plain English, and let change requests be
free text.

Open question: sketch 3 has a note that reads like "costs / cost more". Decide
whether pricing or per-entity cost belongs on that screen.
