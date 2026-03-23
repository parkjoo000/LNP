# Report Format Reference

## File Naming

```
output/logs/run_{batch_id}_{assay_type}_{YYYYMMDD_HHMMSS}.log
```

Example: `run_LNP-2024-001_physical_20240315_143022.log`

---

## Markdown Template

```markdown
# LNP Data Pipeline — Run Report

| Field           | Value                                      |
|-----------------|--------------------------------------------|
| Run ID          | {run_id}                                   |
| Timestamp       | {YYYY-MM-DD HH:MM:SS}                      |
| Source File     | {original_filename}                        |
| Batch ID        | {batch_id}                                 |
| Assay Type      | {assay_type_confirmed} ({confidence})      |
| Matched Pattern | {matched_pattern}                          |
| Overall Status  | {SUCCESS / PARTIAL / FAILED}               |

---

## Classification

- Assay type: **{assay_type_confirmed}**
- Confidence: {HIGH / MEDIUM / LOW}
- Matched instrument pattern: `{matched_pattern}`
- Header columns found: `{header_row_list}`

{If HINT_MISMATCH:}
> **Warning:** Filename hint was `{assay_type_hint}`, but header-based classification
> returned `{assay_type_confirmed}`. Header result is used as authoritative.

---

## Parse Warnings

{If no warnings:}
No parse warnings. All columns resolved without issues.

{If warnings:}
| Row | Field | Issue |
|-----|-------|-------|
| {row_index} | {field_name} | {warning_message} |
...

---

## Validation Flags

| Field                  | Value         | Flag                                       |
|------------------------|---------------|--------------------------------------------|
| {field_name}           | {value} {unit}| {OK / WARN: ... / ERROR: ...}              |
...

{If all OK:}
All fields within acceptable ranges.

---

## Database Write Summary

| Metric          | Count |
|-----------------|-------|
| Rows attempted  | {n}   |
| Rows inserted   | {n}   |
| Rows skipped    | {n}   |

{If rows_skipped > 0:}
Skipped result IDs (UNIQUE conflict — already in database):
{list of skipped result_ids}

{If study_auto_created:}
> **Note:** No `InVivo_study` record existed for `batch_id={batch_id}`.
> A new study record was automatically created with `operator_inferred=1`.
> Review and update the study metadata via the web interface.

---

## Overall Status: {SUCCESS / PARTIAL / FAILED}

{SUCCESS:}
Pipeline completed successfully. {rows_inserted} rows written to {table_name}.

{PARTIAL:}
Pipeline completed with warnings. {rows_inserted} rows written; {rows_skipped} skipped.
Review validation flags above before accepting these results.

{FAILED:}
Pipeline halted at Step {N}: {error_message}

{If FK_MISSING:}
**Action required:** Register Batch ID `{batch_id}` in the database before re-submitting this file.
Steps: web interface → Batches → New Batch → enter formulation and batch metadata.

{If CLASSIFY_FAIL:}
**Action required:** The following headers were found but did not match any known pattern:
`{header_row_list}`
Check that the CSV was exported from a supported instrument or contact the data team.

{If PARSE_ERROR:}
**Action required:** Parsing failed at column `{column}`, row {row_number}: {detail}.
Inspect the source file for formatting issues (merged cells, missing header, unit rows).

---

## Recommended Actions

{List only items that have actionable follow-up. Omit section if none.}

- [ ] {action item 1}
- [ ] {action item 2}
```

---

## Status Definitions

| Status    | Condition                                                         |
|-----------|-------------------------------------------------------------------|
| `SUCCESS` | FK valid, no parse errors, all flags OK or WARN, all rows written |
| `PARTIAL` | FK valid, rows written, but at least one WARN or rows_skipped > 0 |
| `FAILED`  | Pipeline halted at any step (FK_MISSING, CLASSIFY_FAIL, PARSE_ERROR) |
