# Mapping specs

A mapping spec says how one source becomes the canonical model. The AI
proposes it, people approve it, and code turns it into SQLMesh models.

- `<system>.example.yaml`: a starting point for a known source system
- Project specs are stored in Postgres with a version number; each run uses one version.

## Field entry

```yaml
mobile:
  from: CANDIDATE.MobileTel
  transform: normalise_uk_phone
  confidence: 0.94
  status: approved        # proposed | needs_review | approved | rejected
  reason: "92% of values match a UK mobile pattern"
```

## Transforms (the only ones the AI may use)

| Transform | Example |
|---|---|
| `copy` | direct copy (default) |
| `concat` | `[Forename, Surname]` with a separator |
| `split_address` | one address blob → line 1, line 2, city, postcode |
| `parse_date` | with a list of formats, e.g. `[DD/MM/YYYY, YYYY-MM-DD]` |
| `invert_boolean` | `Disabled` → `is_active` |
| `value_map` | enum mapping, see below |
| `strip_rich_text` | remove RTF/HTML from notes |
| `normalise_uk_phone` | to `+44 …` |
| `normalise_postcode` | upper case, single space |
| `lookup` | take a value from another table via a key |
| `constant` | fixed value |

Keeping this list closed means every spec can be checked and turned into SQL.

## Questions

When the AI can't be sure about business meaning, it adds a question instead
of guessing. The UI shows it to the agency.
