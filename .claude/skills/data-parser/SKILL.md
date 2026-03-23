# Skill: data-parser

## Purpose

Parse normalized measurement values from classified CSV files into structured
JSON, applying column aliasing and unit standardization for downstream DB insertion.

## Trigger Condition

Called at **STEP 3**. Receives step2 JSON path.
Routes to the correct `parse_*.py` script based on `assay_type_confirmed`.

## Routing Table

| assay_type_confirmed | Script                |
|----------------------|-----------------------|
| `physical`           | `parse_physical.py`   |
| `invivo_fluc`        | `parse_invivo_fluc.py`|
| `invivo_epo`         | `parse_invivo_epo.py` |
| `toxicity`           | `parse_toxicity.py`   |

## Output (step3 JSON)

Each parser produces a normalized row list. Example for `physical`:

```json
{
  "assay_type": "physical",
  "batch_id": "LNP-2024-001",
  "rows": [
    {
      "batch_id": "LNP-2024-001",
      "measured_at": "2024-03-15T14:30:00",
      "z_avg_nm": 120.4,
      "pdi": 0.12,
      "zeta_potential_mv": -18.2,
      "ee_percent": 85.3,
      "concentration_mg_ml": 1.2,
      "source_file": "LNP-2024-001_physical_20240315.csv",
      "operator": null,
      "notes": null
    }
  ],
  "parse_warnings": []
}
```

For `invivo_fluc` and `invivo_epo` rows: `study_id` is set to `null` by the parser.
The db-writer resolves or auto-creates the `InVivo_study` record at STEP 6.

## Column Aliasing

Each parser maintains a `COLUMN_MAP` dict mapping known device column names
(lowercase, stripped) to canonical DB field names.
Unknown columns are silently ignored.
Missing required columns produce a parse warning (not an error).

## Error Handling

| Condition                        | Action                                              |
|----------------------------------|-----------------------------------------------------|
| Cannot locate header row         | Raise `PARSE_ERROR`, halt pipeline                  |
| Required column missing          | Set field to `null`, append to `parse_warnings`     |
| Non-numeric value in numeric col | Set field to `null`, append to `parse_warnings`     |
| Zero data rows after parsing     | Raise `PARSE_ERROR: no data rows found`, halt       |
| Encoding error                   | Retry with `cp949`, then `latin-1` before failing   |

All `parse_warnings` are collected and passed to result-reporter at STEP 7.

## Header Row Detection Strategy

Many lab instrument exports prepend metadata rows before the actual column header.
Parsers scan up to the first 30 lines for a line containing a primary keyword
(e.g. "z-ave", "total flux", "od 450", "alt") before treating it as the header.
