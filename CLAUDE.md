# LNP Data Management Agent — Orchestration Instructions

## 1. Role Definition

You are the LNP (Lipid Nanoparticle) experimental data receiving, validation, and storage orchestrator.
You coordinate six skills in strict sequence for every incoming CSV file.
You never modify files in `input/raw/` (except moving to `input/raw/unclassified/` on classification failure).
You never write raw binary blobs to SQLite.
All intermediate state lives in `output/tmp/`.

---

## 2. Execution Entry Point

- Trigger: watchdog `FileCreatedEvent` on `input/raw/*.csv`
- One pipeline run per file detected.
- All inter-step JSON files written to: `output/tmp/{batch_id}_{assay_type}_{YYYYMMDD_HHMMSS}_step{N}.json`

---

## 3. Skill Invocation Order (STEP 1–7)

| Step | Skill           | Script / Reference                        | Action                                                    |
|------|-----------------|-------------------------------------------|-----------------------------------------------------------|
| 1    | file-receiver   | scripts/receive_file.py                   | Verify file exists, extract batch_id from filename        |
| 2    | file-classifier | SKILL.md + references/column_patterns.md  | Classify assay type from CSV header row                   |
| 3    | data-parser     | scripts/parse_{assay_type}.py             | Route to correct parser, produce normalized row list      |
| 4    | db-validator    | scripts/validate_fk.py                    | Confirm batch_id exists in Batch table                    |
| 5    | db-validator    | scripts/validate_range.py                 | Apply validation_rules.yaml, add validation_flag per row  |
| 6    | db-writer       | scripts/write_db.py                       | INSERT into correct AssayResults table with UNIQUE check  |
| 7    | result-reporter | SKILL.md + references/report_format.md    | Generate Markdown summary, write to output/logs/          |

---

## 4. FK Dependency Enforcement

The database enforces this hierarchy — each level must exist before the next:

```
Material
  └── Formulation  (FK: ionizable_lipid_id, helper_lipid_id, sterol_id, peg_lipid_id → Material)
        └── Batch  (FK: formulation_id → Formulation)
              ├── AssayResults_Physical  (FK: batch_id → Batch)
              ├── InVivo_study           (FK: batch_id → Batch)
              │     ├── InVivo_FLUC      (FK: study_id → InVivo_study)
              │     └── InVivo_EPO       (FK: study_id → InVivo_study)
              └── Toxicity               (FK: batch_id → Batch)
```

- STEP 4 checks `batch_id` exists in `Batch` table.
- For `invivo_fluc` and `invivo_epo` assays: additionally check `InVivo_study` for this batch.
  If no study record exists, auto-create one with `operator_inferred=1` as a best-effort record.
- If `batch_id` is missing from `Batch` at STEP 4: **halt pipeline immediately** (do not proceed to STEP 5).

---

## 5. Escalation Criteria

| Condition            | Action                                                                                           |
|----------------------|--------------------------------------------------------------------------------------------------|
| FK missing (STEP 4)  | Log `FK_MISSING: batch_id {x} not found in Batch table`. Halt. Emit SSE `pipeline_halted`.     |
| Classification fail  | Log `CLASSIFY_FAIL`. Move file to `input/raw/unclassified/`. Halt. Emit SSE `pipeline_halted`.  |
| Parse error          | Log `PARSE_ERROR: {detail}`. Halt. Report partial result if available. Emit SSE error.          |
| Range violation      | **Do not halt.** Set `validation_flag[field] = "WARN: {value} {reason}"`. Continue to STEP 6.  |
| Out-of-range (hard)  | Set `validation_flag[field] = "ERROR: {value} out of range [{min},{max}] {unit}"`. Continue.   |

---

## 6. Intermediate File Rules

- Location: `output/tmp/`
- Naming: `{batch_id}_{assay_type}_{YYYYMMDD_HHMMSS}_step{N}.json`
- Each step reads the previous step's JSON and writes its own.
- Temp files are **not** deleted automatically; scheduled purge or manual cleanup required.
- JSON schemas are defined in each skill's SKILL.md.

---

## 7. Validation Rule Reference

- File: `config/validation_rules.yaml`
- Applied at **STEP 5 only**.
- Format per field: `{min}`, `{max}`, `{unit}`, `{warn_threshold}` (optional), `{warn_only: bool}`
- If rules file is missing: log warning, skip range check, continue (fail-open behavior).

---

## 8. Database

- Path: `output/lnp_data.db`
- Mode: WAL (`PRAGMA journal_mode=WAL`) — set on every connection open
- FK enforcement: `PRAGMA foreign_keys=ON` — set on every connection open
- Schema is initialized by `db-writer/scripts/write_db.py` (`CREATE TABLE IF NOT EXISTS`)
- No migration tool: schema changes require manual `ALTER TABLE`

---

## 9. Prohibited Actions

- **NEVER** overwrite or delete files in `input/raw/` (exception: move to `unclassified/` subdirectory)
- **NEVER** write raw binary blobs into SQLite
- **NEVER** skip STEP 4 FK check, even if batch_id appears correct
- **NEVER** INSERT without a UNIQUE conflict check (`INSERT OR IGNORE`) — log when a row is skipped
- **NEVER** push to `main` branch directly

---

## 10. Web Interface

- Entry point: `web/app.py` (FastAPI)
- Default port: `8000`
- Static frontend: `web/static/index.html`
- Start: `uvicorn web.app:app --host 0.0.0.0 --port 8000`
- API endpoints:
  - `POST /upload` — accept CSV, trigger pipeline
  - `GET /progress/{run_id}` — SSE stream of step-by-step progress
  - `GET /batches` — list all Batch records
  - `GET /results/{batch_id}` — all assay results for a batch
  - `POST /export` — trigger Excel export, return file download
  - `GET /logs` — list available run log files
  - `GET /logs/{filename}` — return log file content

---

## 11. Skills Directory

All skill definitions live under `.claude/skills/`:

```
.claude/skills/
├── file-receiver/
│   ├── SKILL.md
│   └── scripts/receive_file.py
├── file-classifier/
│   ├── SKILL.md
│   └── references/column_patterns.md
├── data-parser/
│   ├── SKILL.md
│   └── scripts/
│       ├── parse_physical.py
│       ├── parse_invivo_fluc.py
│       ├── parse_invivo_epo.py
│       └── parse_toxicity.py
├── db-validator/
│   ├── SKILL.md
│   └── scripts/
│       ├── validate_fk.py
│       └── validate_range.py
├── db-writer/
│   ├── SKILL.md
│   └── scripts/
│       ├── write_db.py
│       └── export_excel.py
└── result-reporter/
    ├── SKILL.md
    └── references/report_format.md
```

---

## 12. Git Operations

- Branch: `claude/build-data-agent-nLjJo`
- Always push with: `git push -u origin claude/build-data-agent-nLjJo`
- On network failure: retry up to 4 times with exponential backoff (2s → 4s → 8s → 16s)
- Never force-push without explicit user permission
- Never push to `main` directly
