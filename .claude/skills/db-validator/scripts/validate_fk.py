"""
STEP 4 – db-validator: validate_fk.py
Check that batch_id exists in the Batch table.
For invivo_fluc / invivo_epo: also ensure InVivo_study exists, auto-creating if needed.
"""

import json
import logging
import os
import sqlite3
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("validate-fk")


def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema(db_path: str):
    """Bootstrap minimal schema so we can query even on a fresh DB."""
    # Defer to write_db.py for full schema; here we just need the tables to exist.
    import importlib.util, pathlib
    write_db_path = pathlib.Path(__file__).resolve().parent.parent.parent / "db-writer" / "scripts" / "write_db.py"
    if write_db_path.exists():
        spec = importlib.util.spec_from_file_location("write_db", str(write_db_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.init_schema(db_path)
    else:
        logger.warning("write_db.py not found; cannot init schema")


def validate_fk(step3_json_path: str, db_path: str, tmp_dir: str) -> str:
    with open(step3_json_path) as f:
        step3 = json.load(f)

    batch_id = step3["batch_id"]
    assay_type = step3.get("assay_type", step3.get("assay_type_confirmed", ""))
    timestamp = step3["timestamp"]

    # Ensure DB exists
    if not os.path.exists(db_path):
        logger.warning("DB not found at %s — initialising schema", db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _ensure_schema(db_path)

    study_id = None
    study_auto_created = False

    try:
        conn = _open_db(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM Batch WHERE batch_id = ? LIMIT 1", (batch_id,)
            ).fetchone()

            if row is None:
                error_msg = f"FK_MISSING: batch_id {batch_id} not found in Batch table"
                logger.error(error_msg)
                result = {
                    "fk_valid": False,
                    "batch_id": batch_id,
                    "assay_type": assay_type,
                    "error": error_msg,
                    **{k: step3[k] for k in ("timestamp", "sha256", "original_path", "source_file" if "source_file" in step3 else "original_path") if k in step3},
                }
                # keep pass-through keys needed by downstream even on failure
                result = {**step3, "fk_valid": False, "error": error_msg, "status": "fk_failed"}
                os.makedirs(tmp_dir, exist_ok=True)
                out_name = f"{batch_id}_{assay_type}_{timestamp}_step4.json"
                out_path = os.path.join(tmp_dir, out_name)
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2)
                raise ValueError(error_msg)

            logger.info("FK check passed: batch_id=%s", batch_id)

            # For in vivo assays: ensure InVivo_study exists
            if assay_type in ("invivo_fluc", "invivo_epo"):
                study_row = conn.execute(
                    "SELECT study_id FROM InVivo_study WHERE batch_id = ? ORDER BY rowid DESC LIMIT 1",
                    (batch_id,),
                ).fetchone()

                if study_row is None:
                    # Auto-create study record
                    conn.execute(
                        "INSERT INTO InVivo_study (batch_id, operator_inferred) VALUES (?, 1)",
                        (batch_id,),
                    )
                    conn.commit()
                    study_id = conn.execute(
                        "SELECT study_id FROM InVivo_study WHERE batch_id = ? ORDER BY rowid DESC LIMIT 1",
                        (batch_id,),
                    ).fetchone()[0]
                    study_auto_created = True
                    logger.warning(
                        "STUDY_AUTO_CREATED: created InVivo_study %s for batch %s",
                        study_id, batch_id,
                    )
                else:
                    study_id = study_row[0]
                    logger.info("InVivo_study found: study_id=%s", study_id)

        finally:
            conn.close()

    except sqlite3.OperationalError as exc:
        raise RuntimeError(f"DB_ERROR: {exc}") from exc

    result = {
        **step3,
        "fk_valid": True,
        "study_id": study_id,
        "study_auto_created": study_auto_created,
        "error": None,
        "status": "fk_valid",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_{assay_type}_{timestamp}_step4.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: validate_fk.py <step3_json> <db_path> <tmp_dir>")
        sys.exit(1)
    print(validate_fk(sys.argv[1], sys.argv[2], sys.argv[3]))
