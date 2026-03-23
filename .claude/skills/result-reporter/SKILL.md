# Skill: result-reporter

## Purpose

Generate a human-readable processing summary after pipeline completion or failure.
Writes a Markdown log file to `output/logs/` and emits the final SSE event to the client.

## Trigger Condition

Called at **STEP 7**. Receives step6 JSON path (or an error dict if the pipeline halted early).

## Input

- `step6_json_path` (or error dict)
- `step3_json_path` (for `parse_warnings` list)
- `step5_json_path` (for per-field `validation_flag` details)
- `logs_dir`: `output/logs/`

## Output

- Markdown report written to: `output/logs/run_{batch_id}_{assay_type}_{YYYYMMDD_HHMMSS}.log`
- SSE event payload:
  ```json
  {
    "event": "pipeline_complete",
    "run_id": "...",
    "status": "SUCCESS",
    "log_file": "run_LNP-2024-001_physical_20240315_143022.log",
    "rows_inserted": 3,
    "rows_skipped": 1
  }
  ```

## Report Sections

See `references/report_format.md` for the full template.

1. **Run Metadata** — timestamp, file processed, batch_id, run_id
2. **Classification Result** — assay type, confidence, matched pattern
3. **Parse Warnings** — list of row-level issues found by the parser (if any)
4. **Validation Flags** — per-field OK / WARN / ERROR status table
5. **DB Write Summary** — rows inserted, rows skipped (with reason)
6. **Overall Status** — `SUCCESS`, `PARTIAL` (inserted with warnings), or `FAILED`
7. **Recommended Actions** — actionable next steps for any warnings or failures

## LLM Prompt Instructions

When generating the report narrative:
- Use plain, technical language appropriate for lab scientists.
- No emojis. No marketing language.
- Be specific: name each flagged field and its measured value.
- If `FK_MISSING`: explain that the Batch record must be registered before re-submitting.
- If `CLASSIFY_FAIL`: list the headers that were found and state which patterns they failed to match.
- If `PARSE_ERROR`: identify the column and row number where parsing failed.
- If all flags are OK and no warnings: keep the report brief (no padding).

## Error Handling

| Condition              | Action                                                          |
|------------------------|-----------------------------------------------------------------|
| step6 JSON missing     | Generate FAILED report using whatever steps are available       |
| logs_dir not writable  | Log `REPORT_WRITE_ERROR` to stderr; still emit SSE event       |
| step5/step3 missing    | Report validation/parse sections as "unavailable"              |
