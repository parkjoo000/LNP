# Skill: db-validator

## Purpose

Two-stage validation of parsed data before DB insertion:
1. **FK integrity** (`validate_fk.py`): `batch_id` must exist in `Batch` table.
2. **Numeric range checking** (`validate_range.py`): apply `config/validation_rules.yaml`.

## Trigger Conditions

- `validate_fk.py` called at **STEP 4** immediately after data-parser
- `validate_range.py` called at **STEP 5** after FK validation passes

## Input

**validate_fk.py**:
- `step3_json_path`: output of data-parser
- `db_path`: `output/lnp_data.db`
- `tmp_dir`: `output/tmp/`

**validate_range.py**:
- `step3_json_path`: same data-parser output (reads rows)
- `rules_path`: `config/validation_rules.yaml`
- `tmp_dir`: `output/tmp/`

## Output

### validate_fk (step4.json)

```json
{
  "fk_valid": true,
  "batch_id": "LNP-2024-001",
  "assay_type": "physical",
  "study_id": null,
  "study_auto_created": false,
  "error": null
}
```

On failure:
```json
{
  "fk_valid": false,
  "batch_id": "LNP-2024-001",
  "error": "FK_MISSING: batch_id LNP-2024-001 not found in Batch table"
}
```

### validate_range (step5.json)

Same as step3 JSON with `validation_flag` field added to each row:

```json
{
  "assay_type": "physical",
  "batch_id": "LNP-2024-001",
  "rows": [
    {
      "batch_id": "LNP-2024-001",
      "z_avg_nm": 120.4,
      "pdi": 0.45,
      "validation_flag": "{\"z_avg_nm\": \"OK\", \"pdi\": \"WARN: 0.45 > threshold 0.3\"}"
    }
  ],
  "parse_warnings": []
}
```

## FK Validation Logic

1. Connect to `output/lnp_data.db` with `PRAGMA foreign_keys=ON`.
2. `SELECT 1 FROM Batch WHERE batch_id = ? LIMIT 1`.
3. If not found: raise `ValueError("FK_MISSING: ...")`, write error JSON, halt pipeline.
4. For `invivo_fluc` / `invivo_epo` assays additionally:
   - `SELECT study_id FROM InVivo_study WHERE batch_id = ? LIMIT 1`
   - If not found: auto-create with `operator_inferred=1`, return `study_auto_created: true`

## Range Validation Logic

1. Load `config/validation_rules.yaml`. If missing: log warning, skip, continue.
2. Map `assay_type` → table name:
   ```
   physical    → AssayResults_Physical
   invivo_fluc → InVivo_FLUC
   invivo_epo  → InVivo_EPO
   toxicity    → Toxicity
   ```
3. For each row, for each field in `table_rules`:
   - If value is `null`: `validation_flag[field] = "SKIP: null value"`
   - If `value < min` or `value > max`:
     - If `warn_only: true`: `"WARN: {value} out of range [{min},{max}] {unit}"`
     - Else: `"ERROR: {value} out of range [{min},{max}] {unit}"`
   - If `warn_threshold` set and `value > warn_threshold`: `"WARN: {value} {unit} > threshold {warn_threshold}"`
   - Else: `"OK"`
4. Serialize `validation_flag` as JSON string before storing in row.

## Error Handling

| Condition              | Action                                                         |
|------------------------|----------------------------------------------------------------|
| FK missing             | Write step4 JSON with error. Halt. Emit SSE `pipeline_halted`.|
| DB file not found      | Create empty DB via `write_db.py init`, then check FK.        |
| Rules file missing     | Log `RULES_MISSING`, skip range check, write step5 as-is.    |
| YAML parse error       | Log `RULES_PARSE_ERROR`, skip range check, continue.          |
