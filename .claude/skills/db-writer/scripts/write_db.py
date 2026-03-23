"""
STEP 6 – db-writer: write_db.py
Insert validated rows into SQLite. Initialises schema on first run.
Uses INSERT OR IGNORE with UNIQUE conflict detection.
"""

import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("db-writer")

DB_RETRY_ATTEMPTS = 3
DB_RETRY_DELAY = 0.5  # seconds

# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS Material (
    material_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    smiles        TEXT,
    mol_weight    REAL,
    supplier      TEXT,
    lot_number    TEXT,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS Formulation (
    formulation_id      TEXT PRIMARY KEY,
    ionizable_lipid_id  TEXT REFERENCES Material(material_id),
    helper_lipid_id     TEXT REFERENCES Material(material_id),
    sterol_id           TEXT REFERENCES Material(material_id),
    peg_lipid_id        TEXT REFERENCES Material(material_id),
    molar_ratio         TEXT,
    n_p_ratio           REAL,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS FormulationComponent (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    formulation_id  TEXT NOT NULL REFERENCES Formulation(formulation_id),
    material_id     TEXT NOT NULL REFERENCES Material(material_id),
    role            TEXT,
    mole_fraction   REAL
);

CREATE TABLE IF NOT EXISTS Batch (
    batch_id        TEXT PRIMARY KEY,
    formulation_id  TEXT REFERENCES Formulation(formulation_id),
    preparation_date TEXT,
    operator        TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS AssayResults_Physical (
    result_id             TEXT PRIMARY KEY,
    batch_id              TEXT NOT NULL REFERENCES Batch(batch_id),
    measured_at           TEXT,
    z_avg_nm              REAL,
    pdi                   REAL,
    zeta_potential_mv     REAL,
    ee_percent            REAL,
    concentration_mg_ml   REAL,
    source_file           TEXT,
    operator              TEXT,
    notes                 TEXT,
    validation_flag       TEXT
);

CREATE TABLE IF NOT EXISTS InVivo_study (
    study_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id          TEXT NOT NULL REFERENCES Batch(batch_id),
    study_date        TEXT,
    model             TEXT,
    route             TEXT,
    dose_ug           REAL,
    operator          TEXT,
    operator_inferred INTEGER DEFAULT 0,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS InVivo_FLUC (
    result_id       TEXT PRIMARY KEY,
    batch_id        TEXT NOT NULL REFERENCES Batch(batch_id),
    study_id        INTEGER REFERENCES InVivo_study(study_id),
    measured_at     TEXT,
    animal_id       TEXT,
    organ           TEXT,
    roi_label       TEXT,
    group_label     TEXT,
    timepoint_h     REAL,
    fluc_total_flux REAL,
    source_file     TEXT,
    operator        TEXT,
    notes           TEXT,
    validation_flag TEXT
);

CREATE TABLE IF NOT EXISTS InVivo_EPO (
    result_id       TEXT PRIMARY KEY,
    batch_id        TEXT NOT NULL REFERENCES Batch(batch_id),
    study_id        INTEGER REFERENCES InVivo_study(study_id),
    measured_at     TEXT,
    animal_id       TEXT,
    group_label     TEXT,
    well            TEXT,
    sample_id       TEXT,
    dilution_factor REAL,
    od_450          REAL,
    epo_pg_ml       REAL,
    timepoint_h     REAL,
    source_file     TEXT,
    operator        TEXT,
    notes           TEXT,
    validation_flag TEXT
);

CREATE TABLE IF NOT EXISTS Toxicity (
    result_id           TEXT PRIMARY KEY,
    batch_id            TEXT NOT NULL REFERENCES Batch(batch_id),
    measured_at         TEXT,
    animal_id           TEXT,
    group_label         TEXT,
    timepoint_h         REAL,
    alt_u_l             REAL,
    ast_u_l             REAL,
    bun_mg_dl           REAL,
    creatinine_mg_dl    REAL,
    source_file         TEXT,
    operator            TEXT,
    notes               TEXT,
    validation_flag     TEXT
);
"""


def init_schema(db_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = _open_db(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("Schema initialised at %s", db_path)
    finally:
        conn.close()


def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _retry_connect(db_path: str) -> sqlite3.Connection:
    for attempt in range(DB_RETRY_ATTEMPTS):
        try:
            return _open_db(db_path)
        except sqlite3.OperationalError as exc:
            if attempt < DB_RETRY_ATTEMPTS - 1:
                time.sleep(DB_RETRY_DELAY * (attempt + 1))
            else:
                raise RuntimeError(f"DB_LOCKED after {DB_RETRY_ATTEMPTS} attempts: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# Insertion helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_result_id(batch_id: str, assay_type: str, row_idx: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{batch_id}_{assay_type}_{ts}_{row_idx:04d}"


def _resolve_study_id(conn: sqlite3.Connection, batch_id: str) -> int:
    row = conn.execute(
        "SELECT study_id FROM InVivo_study WHERE batch_id = ? ORDER BY rowid DESC LIMIT 1",
        (batch_id,),
    ).fetchone()
    if row:
        return row[0]
    conn.execute(
        "INSERT INTO InVivo_study (batch_id, operator_inferred) VALUES (?, 1)",
        (batch_id,),
    )
    conn.commit()
    study_id = conn.execute(
        "SELECT study_id FROM InVivo_study WHERE batch_id = ? ORDER BY rowid DESC LIMIT 1",
        (batch_id,),
    ).fetchone()[0]
    logger.warning("STUDY_AUTO_CREATED: study_id=%s for batch %s", study_id, batch_id)
    return study_id


def _insert_physical(conn, rows, batch_id, assay_type):
    inserted, skipped, skipped_ids = 0, 0, []
    for i, row in enumerate(rows):
        rid = _make_result_id(batch_id, assay_type, i)
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO AssayResults_Physical
                   (result_id, batch_id, measured_at, z_avg_nm, pdi, zeta_potential_mv,
                    ee_percent, concentration_mg_ml, source_file, operator, notes, validation_flag)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, row.get("batch_id"), row.get("measured_at"),
                 row.get("z_avg_nm"), row.get("pdi"), row.get("zeta_potential_mv"),
                 row.get("ee_percent"), row.get("concentration_mg_ml"),
                 row.get("source_file"), row.get("operator"), row.get("notes"),
                 row.get("validation_flag")),
            )
            if cur.rowcount == 0:
                logger.info("UNIQUE_SKIP: %s", rid)
                skipped += 1
                skipped_ids.append(rid)
            else:
                inserted += 1
        except sqlite3.IntegrityError as exc:
            logger.error("FK_CONSTRAINT: %s — %s", rid, exc)
            raise
    return inserted, skipped, skipped_ids


def _insert_invivo_fluc(conn, rows, batch_id, assay_type):
    inserted, skipped, skipped_ids = 0, 0, []
    study_id_cache = {}
    for i, row in enumerate(rows):
        bid = row.get("batch_id", batch_id)
        if bid not in study_id_cache:
            study_id_cache[bid] = _resolve_study_id(conn, bid)
        study_id = row.get("study_id") or study_id_cache[bid]

        rid = _make_result_id(batch_id, assay_type, i)
        cur = conn.execute(
            """INSERT OR IGNORE INTO InVivo_FLUC
               (result_id, batch_id, study_id, measured_at, animal_id, organ, roi_label,
                group_label, timepoint_h, fluc_total_flux, source_file, operator, notes, validation_flag)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, bid, study_id, row.get("measured_at"), row.get("animal_id"),
             row.get("organ"), row.get("roi_label"), row.get("group_label"),
             row.get("timepoint_h"), row.get("fluc_total_flux"),
             row.get("source_file"), row.get("operator"), row.get("notes"),
             row.get("validation_flag")),
        )
        if cur.rowcount == 0:
            logger.info("UNIQUE_SKIP: %s", rid)
            skipped += 1
            skipped_ids.append(rid)
        else:
            inserted += 1
    return inserted, skipped, skipped_ids


def _insert_invivo_epo(conn, rows, batch_id, assay_type):
    inserted, skipped, skipped_ids = 0, 0, []
    study_id_cache = {}
    for i, row in enumerate(rows):
        bid = row.get("batch_id", batch_id)
        if bid not in study_id_cache:
            study_id_cache[bid] = _resolve_study_id(conn, bid)
        study_id = row.get("study_id") or study_id_cache[bid]

        rid = _make_result_id(batch_id, assay_type, i)
        cur = conn.execute(
            """INSERT OR IGNORE INTO InVivo_EPO
               (result_id, batch_id, study_id, measured_at, animal_id, group_label,
                well, sample_id, dilution_factor, od_450, epo_pg_ml, timepoint_h,
                source_file, operator, notes, validation_flag)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, bid, study_id, row.get("measured_at"), row.get("animal_id"),
             row.get("group_label"), row.get("well"), row.get("sample_id"),
             row.get("dilution_factor"), row.get("od_450"), row.get("epo_pg_ml"),
             row.get("timepoint_h"), row.get("source_file"), row.get("operator"),
             row.get("notes"), row.get("validation_flag")),
        )
        if cur.rowcount == 0:
            logger.info("UNIQUE_SKIP: %s", rid)
            skipped += 1
            skipped_ids.append(rid)
        else:
            inserted += 1
    return inserted, skipped, skipped_ids


def _insert_toxicity(conn, rows, batch_id, assay_type):
    inserted, skipped, skipped_ids = 0, 0, []
    for i, row in enumerate(rows):
        rid = _make_result_id(batch_id, assay_type, i)
        cur = conn.execute(
            """INSERT OR IGNORE INTO Toxicity
               (result_id, batch_id, measured_at, animal_id, group_label, timepoint_h,
                alt_u_l, ast_u_l, bun_mg_dl, creatinine_mg_dl,
                source_file, operator, notes, validation_flag)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, row.get("batch_id"), row.get("measured_at"), row.get("animal_id"),
             row.get("group_label"), row.get("timepoint_h"),
             row.get("alt_u_l"), row.get("ast_u_l"), row.get("bun_mg_dl"),
             row.get("creatinine_mg_dl"), row.get("source_file"),
             row.get("operator"), row.get("notes"), row.get("validation_flag")),
        )
        if cur.rowcount == 0:
            logger.info("UNIQUE_SKIP: %s", rid)
            skipped += 1
            skipped_ids.append(rid)
        else:
            inserted += 1
    return inserted, skipped, skipped_ids


INSERT_DISPATCH = {
    "physical": _insert_physical,
    "invivo_fluc": _insert_invivo_fluc,
    "invivo_epo": _insert_invivo_epo,
    "toxicity": _insert_toxicity,
}

# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def write_db(step5_json_path: str, db_path: str, tmp_dir: str) -> str:
    with open(step5_json_path) as f:
        step5 = json.load(f)

    assay_type = step5.get("assay_type", step5.get("assay_type_confirmed", ""))
    batch_id = step5["batch_id"]
    timestamp = step5["timestamp"]
    rows = step5.get("rows", [])

    init_schema(db_path)

    inserter = INSERT_DISPATCH.get(assay_type)
    if inserter is None:
        raise ValueError(f"PARSE_ERROR: unknown assay_type '{assay_type}'")

    conn = _retry_connect(db_path)
    try:
        inserted, skipped, skipped_ids = inserter(conn, rows, batch_id, assay_type)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    result = {
        **{k: step5[k] for k in ("batch_id", "assay_type", "timestamp",
                                   "original_path", "sha256",
                                   "assay_type_confirmed", "classification_confidence",
                                   "matched_pattern", "header_row",
                                   "study_id", "study_auto_created",
                                   "parse_warnings") if k in step5},
        "assay_type": assay_type,
        "batch_id": batch_id,
        "timestamp": timestamp,
        "rows_attempted": len(rows),
        "rows_inserted": inserted,
        "rows_skipped": skipped,
        "skipped_result_ids": skipped_ids,
        "status": "ok",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_{assay_type}_{timestamp}_step6.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(
        "DB write complete: inserted=%d skipped=%d assay=%s batch=%s",
        inserted, skipped, assay_type, batch_id,
    )
    return out_path


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "init":
        db_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "lnp_data.db")
        init_schema(db_path)
        print(f"Schema initialised: {db_path}")
        sys.exit(0)
    if len(sys.argv) < 4:
        print("Usage: write_db.py <step5_json> <db_path> <tmp_dir>")
        print("       write_db.py init")
        sys.exit(1)
    print(write_db(sys.argv[1], sys.argv[2], sys.argv[3]))
