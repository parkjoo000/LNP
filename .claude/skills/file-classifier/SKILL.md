# Skill: file-classifier

## Purpose

Detect the assay type of an incoming CSV file by analyzing its header row using
pattern matching against known instrument output signatures defined in
`references/column_patterns.md`.

## Trigger Condition

Called at **STEP 2**. Receives the step1 JSON path.
The `assay_type_hint` from the filename is used as a prior, but header-based
classification is **authoritative** when they disagree.

## Input

- `step1_json_path`: path to the step1 JSON produced by file-receiver
- `column_patterns.md`: header pattern dictionary (loaded from `references/`)

## Output

Step2 JSON (extends step1 data):

```json
{
  "original_path": "...",
  "batch_id": "LNP-2024-001",
  "assay_type_hint": "physical",
  "assay_type_confirmed": "physical",
  "classification_confidence": "HIGH",
  "matched_pattern": "Zetasizer_v3",
  "header_row": ["Sample Name", "Z-Ave (d.nm)", "PDI", "Zeta Potential (mV)"],
  "timestamp": "20240315_143022",
  "file_size_bytes": 4096,
  "sha256": "abc123...",
  "status": "classified"
}
```

## Steps

1. Read step1 JSON; get `original_path`.
2. Open CSV file; read first 20 lines.
3. Identify header row: scan for a line containing instrument-specific keywords.
4. Normalize header: strip whitespace, lowercase each column name.
5. Match against `column_patterns.md` signature dictionary.
6. Assign confidence:
   - **HIGH**: all required columns present (exact or alias match)
   - **MEDIUM**: ≥60% of required columns match
   - **LOW**: <60% match — escalate as `CLASSIFY_FAIL`
7. Cross-check `assay_type_confirmed` vs `assay_type_hint` from filename.
   - If mismatch: log `HINT_MISMATCH: filename says {hint}, header says {confirmed}`.
   - Use header-based result as authoritative.
8. Write step2 JSON.

## Classification Decision Table

| Confirmed Type  | Required Headers (any subset sufficient)                    |
|-----------------|-------------------------------------------------------------|
| `physical`      | Z-Avg, PDI, Zeta Potential OR Size (nm), PdI                |
| `invivo_fluc`   | Total Flux, ROI, Living Image OR Radiance                   |
| `invivo_epo`    | OD 450, Sample, Dilution Factor OR Concentration, Well      |
| `toxicity`      | ALT, AST, BUN OR Alanine aminotransferase, Aspartate aminotransferase |

## Error Handling

| Condition        | Action                                                                                    |
|------------------|-------------------------------------------------------------------------------------------|
| CLASSIFY_FAIL    | Move file to `input/raw/unclassified/`. Write error JSON. Emit SSE `pipeline_halted`.    |
| Encoding error   | Try `utf-8` → `cp949` → `latin-1`. If all fail: log `ENCODING_ERROR`, treat as FAIL.    |
| Empty header row | Log `EMPTY_HEADER`, treat as CLASSIFY_FAIL.                                              |
| MEDIUM confidence| Set `classification_confidence: "MEDIUM"` in JSON. Continue pipeline with flag for review.|
