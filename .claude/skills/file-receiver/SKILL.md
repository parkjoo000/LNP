# Skill: file-receiver

## Purpose

Receive an incoming CSV file from `input/raw/`, validate the filename convention,
extract metadata, and confirm physical file integrity before the pipeline proceeds.

## Trigger Condition

Called at **STEP 1** immediately after watchdog `FileCreatedEvent` fires.

## Input

- Absolute path to the newly created file (string)
- `tmp_dir`: path to `output/tmp/` for writing the step1 JSON

## Output

JSON file written to `output/tmp/`:

```json
{
  "original_path": "/absolute/path/to/LNP-2024-001_physical_20240315.csv",
  "batch_id": "LNP-2024-001",
  "assay_type_hint": "physical",
  "date_str": "20240315",
  "timestamp": "20240315_143022",
  "file_size_bytes": 4096,
  "sha256": "abc123...",
  "status": "received"
}
```

Output filename: `{batch_id}_{assay_type_hint}_{timestamp}_step1.json`

## Steps

1. Assert file exists and is readable.
2. Parse filename: expected pattern `{batch_id}_{assay_type}_{YYYYMMDD}.csv`
   - `batch_id`: alphanumeric + hyphens, e.g. `LNP-2024-001`
   - `assay_type`: one of `physical`, `invivo_fluc`, `invivo_epo`, `toxicity`
   - `date`: 8-digit `YYYYMMDD`
3. If filename does not match pattern: log `FILENAME_INVALID`, escalate.
4. Assert file is not zero bytes.
5. Compute SHA256 of full file contents.
6. Record `file_size_bytes`.
7. Write step1 JSON to `output/tmp/`.
8. Return JSON path to orchestrator.

## Error Handling

| Condition              | Action                                              |
|------------------------|-----------------------------------------------------|
| File not found         | Raise `FileNotFoundError`, log, halt pipeline       |
| Filename pattern fail  | Log `FILENAME_INVALID: {actual_name}`, halt         |
| Zero-byte file         | Log `EMPTY_FILE: {path}`, halt                      |
| Permission denied      | Log `PERMISSION_ERROR`, halt                        |

## Example

Input filename: `LNP-2024-001_physical_20240315.csv`
Output JSON keys: `batch_id = "LNP-2024-001"`, `assay_type_hint = "physical"`
