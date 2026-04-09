# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LNP (Lipid Nanoparticle) experimental data pipeline: receives CSV files from lab instruments, classifies the assay type, parses/normalizes data, validates against the database and numeric rules, stores results in SQLite, and generates Markdown run reports. A FastAPI web UI provides upload, progress streaming (SSE), data browsing, and Excel export.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run web server (primary entry point)
uvicorn web.app:app --host 0.0.0.0 --port 8000

# Run file watcher (monitors input/raw/ for new CSVs)
python watchdog_runner.py

# Run pipeline manually on a single file
python -c "from pipeline import run_pipeline; run_pipeline('input/raw/BATCH_assay_DATE.csv')"

# Export all data to Excel
python -c "from importlib.util import spec_from_file_location, module_from_spec; s=spec_from_file_location('e','.claude/skills/db-writer/scripts/export_excel.py'); m=module_from_spec(s); s.loader.exec_module(m); m.export_to_excel('output/lnp_data.db','output/exports/export.xlsx')"
```

No test framework is configured. No linter or formatter is configured.

## Architecture

### Pipeline (7-step sequential)

`pipeline.py` orchestrates all processing via dynamic imports (`importlib`). Each step reads the previous step's JSON from `output/tmp/` and writes its own. SSE events are emitted at each transition for the web UI.

| Step | Skill | Script | Halts on error? |
|------|-------|--------|-----------------|
| 1 | file-receiver | `receive_file.py` | Yes |
| 2 | file-classifier | `classify_file.py` | Yes (moves file to `input/raw/unclassified/`) |
| 3 | data-parser | `parse_{assay_type}.py` | Yes |
| 4 | db-validator | `validate_fk.py` | Yes (FK missing) |
| 5 | db-validator | `validate_range.py` | Never (flags only) |
| 6 | db-writer | `write_db.py` | On DB lock after retries |
| 7 | result-reporter | `generate_report.py` | Never |

All skill scripts live under `.claude/skills/{skill-name}/scripts/`.

### Supported Assay Types

- `physical` — Zetasizer, NanoSight, ZetaView (size, PDI, zeta potential, encapsulation)
- `invivo_fluc` — LivingImage bioluminescence (total flux, radiance)
- `invivo_epo` — SpectraMax ELISA (OD450, EPO pg/mL)
- `toxicity` — Fuji/Hitachi/VetScan blood chemistry (ALT, AST, BUN, creatinine)

### CSV Filename Convention

`{batch_id}_{assay_type}_{YYYYMMDD}.csv` — e.g. `LNP-2024-001_physical_20240315.csv`

### Database (SQLite)

Path: `output/lnp_data.db`. Every connection must set `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`.

FK hierarchy (each level must exist before the next):
```
Material → Formulation → Batch → AssayResults_Physical / InVivo_study / Toxicity
                                   InVivo_study → InVivo_FLUC / InVivo_EPO
```

Schema is auto-created by `write_db.py` (`CREATE TABLE IF NOT EXISTS`). No migration tool — schema changes require manual `ALTER TABLE`.

All inserts use `INSERT OR IGNORE` for UNIQUE deduplication. For in-vivo assays, if no `InVivo_study` exists for the batch, one is auto-created with `operator_inferred=1`.

### Web Interface

- `web/app.py` — FastAPI with SSE streaming for pipeline progress
- `web/static/index.html` — Single-page app (Upload, Batches, Logs, Export tabs)
- Key endpoints: `POST /upload`, `GET /progress/{run_id}`, `GET /batches`, `GET /results/{batch_id}`, `POST /export`, `GET /logs`

### Key Design Patterns

- **Column aliasing**: Each parser has a `COLUMN_MAP` dict mapping 20+ instrument-specific column names to normalized DB field names
- **Encoding fallback**: CSV reading tries UTF-8 → cp949 → latin-1
- **Classification confidence**: HIGH (100% match), MEDIUM (60-99%), LOW (<60% = failure)
- **Intermediate JSON**: `output/tmp/{batch_id}_{assay_type}_{timestamp}_step{N}.json` — not auto-cleaned
- **Validation rules**: `config/validation_rules.yaml` — numeric min/max/warn_threshold per field, applied at step 5 only. Missing rules file = fail-open (skip checks)
- **Reference files**: `column_patterns.md` (instrument signatures) and `report_format.md` (log template) guide classifier and reporter skills

## Operational Rules

- **NEVER** overwrite or delete files in `input/raw/` (exception: move to `unclassified/` on classification failure)
- **NEVER** skip the FK check at step 4
- **NEVER** INSERT without UNIQUE conflict check — log when a row is skipped
- **NEVER** push to `main` branch directly
- Range violations at step 5 produce WARN/ERROR flags but never halt the pipeline
- FK violations at step 4 always halt the pipeline immediately
