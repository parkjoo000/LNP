# Skill: db-writer

## Purpose

Insert validated, flagged rows into the correct SQLite table and optionally
export the full database to a multi-sheet Excel workbook.

## Trigger Conditions

- `write_db.py` called at **STEP 6** after STEP 4 (FK valid) and STEP 5 (range checked)
- `export_excel.py` called on demand via `POST /export` API endpoint or scheduled job

## Input

`write_db.py`:
- `step5_json_path`: output of validate_range (rows include `validation_flag`)
- `db_path`: `output/lnp_data.db`
- `tmp_dir`: `output/tmp/`

`export_excel.py`:
- `db_path`: `output/lnp_data.db`
- `exports_dir`: `output/exports/`

## Output

### write_db (step6.json)

```json
{
  "assay_type": "physical",
  "batch_id": "LNP-2024-001",
  "rows_inserted": 3,
  "rows_skipped": 1,
  "skipped_result_ids": ["LNP-2024-001_physical_20240315_0001"],
  "status": "ok"
}
```

### export_excel

Returns path to the generated `.xlsx` file: `output/exports/export_{YYYYMMDD}.xlsx`

## Schema Initialization

`write_db.py` executes `CREATE TABLE IF NOT EXISTS` for all tables on every run.
This makes it safe to call on an empty or existing database (idempotent).
Schema changes require manual `ALTER TABLE` — no migration tool is provided.

## Database Tables

| Table                  | Primary FK target      |
|------------------------|------------------------|
| `Material`             | (root)                 |
| `Formulation`          | `Material`             |
| `FormulationComponent` | `Formulation`, `Material` |
| `Batch`                | `Formulation`          |
| `AssayResults_Physical`| `Batch`                |
| `InVivo_study`         | `Batch`                |
| `InVivo_FLUC`          | `InVivo_study`         |
| `InVivo_EPO`           | `InVivo_study`         |
| `Toxicity`             | `Batch`                |

## Insertion Rules

- Open connection with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`
- Use `INSERT OR IGNORE` for all assay result tables
- `result_id` format: `{batch_id}_{assay_type}_{YYYYMMDD_HHMMSS}_{row_idx:04d}`
  (row_idx prevents collision when multiple rows share the same second)
- When a row is skipped due to UNIQUE conflict: log `UNIQUE_SKIP: {result_id}`
- Count and report `rows_inserted` and `rows_skipped` in step6 JSON

## InVivo study_id Resolution

For `invivo_fluc` and `invivo_epo` rows where `study_id` is `null` (as set by parser):
1. Look up `InVivo_study` where `batch_id = row["batch_id"]` (latest by rowid)
2. If found: use that `study_id`
3. If not found: auto-create with `operator_inferred=1`; log `STUDY_AUTO_CREATED`
4. Set `study_id` on row before INSERT

## Error Handling

| Condition                 | Action                                              |
|---------------------------|-----------------------------------------------------|
| DB locked                 | Retry up to 3 times with 500ms backoff, then raise  |
| FK constraint violation   | Log, re-raise, halt (should not happen post STEP 4) |
| Non-UNIQUE constraint fail| Log full error, re-raise, halt                      |
| openpyxl not installed    | Log `EXPORT_DEPENDENCY_MISSING`, return error dict  |
