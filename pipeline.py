"""
LNP Data Pipeline Orchestrator
Coordinates STEPS 1–7 for a single incoming CSV file.
Can be run directly or imported by the watchdog / web app.
"""

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("pipeline")

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / ".claude" / "skills"
TMP_DIR = str(ROOT / "output" / "tmp")
LOGS_DIR = str(ROOT / "output" / "logs")
DB_PATH = str(ROOT / "output" / "lnp_data.db")
RULES_PATH = str(ROOT / "config" / "validation_rules.yaml")
UNCLASSIFIED_DIR = str(ROOT / "input" / "raw" / "unclassified")

# ─── Dynamic imports from skill scripts ──────────────────────────────────────

def _import(rel_path: str):
    import importlib.util
    p = SKILLS / rel_path
    spec = importlib.util.spec_from_file_location(p.stem, str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_parser(assay_type: str):
    mod = _import(f"data-parser/scripts/parse_{assay_type}.py")
    return getattr(mod, f"parse_{assay_type}")


# ─── SSE event emission (no-op when not running under FastAPI) ────────────────

_sse_queue = None  # replaced by web app when imported


def _emit(event: dict):
    if _sse_queue is not None:
        try:
            _sse_queue.put_nowait(event)
        except Exception:
            pass
    logger.info("SSE: %s", event)


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(file_path: str, run_id: str = None) -> dict:
    """
    Execute STEPS 1–7 for the given CSV file.
    Returns the SSE payload dict from result-reporter.
    Raises on fatal errors; emits SSE events on each step transition.
    """
    step3_path = step5_path = step6_path = None

    try:
        # STEP 1 — file-receiver
        _emit({"event": "step_start", "step": 1, "run_id": run_id})
        receive_file = _import("file-receiver/scripts/receive_file.py").receive_file
        step1_path = receive_file(file_path, TMP_DIR)
        _emit({"event": "step_done", "step": 1, "run_id": run_id})

        # STEP 2 — file-classifier
        _emit({"event": "step_start", "step": 2, "run_id": run_id})
        classify_file = _import("file-classifier/scripts/classify_file.py").classify_file
        step2_path = classify_file(step1_path, TMP_DIR, UNCLASSIFIED_DIR)
        _emit({"event": "step_done", "step": 2, "run_id": run_id})

        with open(step2_path) as f:
            step2 = json.load(f)
        assay_type = step2["assay_type_confirmed"]

        # STEP 3 — data-parser
        _emit({"event": "step_start", "step": 3, "run_id": run_id})
        parser = _get_parser(assay_type)
        step3_path = parser(step2_path, TMP_DIR)
        _emit({"event": "step_done", "step": 3, "run_id": run_id})

        # STEP 4 — FK validation
        _emit({"event": "step_start", "step": 4, "run_id": run_id})
        validate_fk = _import("db-validator/scripts/validate_fk.py").validate_fk
        step4_path = validate_fk(step3_path, DB_PATH, TMP_DIR)
        with open(step4_path) as f:
            step4 = json.load(f)
        if not step4.get("fk_valid", False):
            _emit({"event": "pipeline_halted", "step": 4, "error": step4.get("error"), "run_id": run_id})
            raise ValueError(step4.get("error", "FK_MISSING"))
        _emit({"event": "step_done", "step": 4, "run_id": run_id})

        # STEP 5 — range validation (reads step3 rows, uses step4 fk context)
        _emit({"event": "step_start", "step": 5, "run_id": run_id})
        validate_range = _import("db-validator/scripts/validate_range.py").validate_range
        step5_path = validate_range(step4_path, RULES_PATH, TMP_DIR)
        _emit({"event": "step_done", "step": 5, "run_id": run_id})

        # STEP 6 — db-writer
        _emit({"event": "step_start", "step": 6, "run_id": run_id})
        write_db = _import("db-writer/scripts/write_db.py").write_db
        step6_path = write_db(step5_path, DB_PATH, TMP_DIR)
        _emit({"event": "step_done", "step": 6, "run_id": run_id})

    except ValueError as exc:
        error_msg = str(exc)
        logger.error("Pipeline halted: %s", error_msg)
        _emit({"event": "pipeline_halted", "error": error_msg, "run_id": run_id})
        # Still run reporter with whatever we have
        _run_reporter(step6_path, step3_path, step5_path, run_id, fatal_error=error_msg)
        raise

    # STEP 7 — result-reporter
    return _run_reporter(step6_path, step3_path, step5_path, run_id)


def _run_reporter(step6_path, step3_path, step5_path, run_id, fatal_error=None):
    try:
        generate_report = _import("result-reporter/scripts/generate_report.py").generate_report
        payload = generate_report(
            step6_path or "",
            step3_path or "",
            step5_path or "",
            LOGS_DIR,
        )
        _emit({**payload, "run_id": run_id})
        return payload
    except Exception as exc:
        logger.error("Reporter failed: %s", exc)
        return {"event": "pipeline_complete", "status": "FAILED", "run_id": run_id}


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <csv_file_path>")
        sys.exit(1)
    result = run_pipeline(sys.argv[1])
    print(json.dumps(result, indent=2))
