"""
STEP 3 – data-parser: parse_invivo_epo.py
Parses in-vivo EPO ELISA CSV files (SpectraMax, generic ELISA readers).
Outputs normalized row list as step3 JSON.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("parse-invivo-epo")

ENCODINGS = ["utf-8", "cp949", "latin-1"]

COLUMN_MAP = {
    # EPO concentration
    "epo (pg/ml)": "epo_pg_ml",
    "epo (ng/ml)": "_epo_ng_ml",   # will convert to pg/ml
    "epo pg/ml": "epo_pg_ml",
    "epo_pg_ml": "epo_pg_ml",
    "conc (pg/ml)": "epo_pg_ml",
    "concentration (pg/ml)": "epo_pg_ml",
    "pg/ml": "epo_pg_ml",
    "conc. (pg/ml)": "epo_pg_ml",
    "epo": "epo_pg_ml",
    # OD absorbance
    "od 450": "od_450",
    "od450": "od_450",
    "absorbance at 450": "od_450",
    "absorbance": "od_450",
    "a450": "od_450",
    # Sample / Well
    "well": "well_id",
    "well id": "well_id",
    "sample": "sample_id",
    "sample id": "sample_id",
    "sample name": "sample_id",
    # Dilution
    "dilution factor": "dilution_factor",
    "dilution": "dilution_factor",
    # Animal / group
    "animal": "animal_id",
    "animal id": "animal_id",
    "mouse": "animal_id",
    "subject": "animal_id",
    "group": "group_label",
    "treatment": "group_label",
    "treatment group": "group_label",
    # Timepoint
    "timepoint": "timepoint",
    "time point": "timepoint",
    "day": "timepoint",
    # Date / operator / notes
    "date": "_date",
    "time": "_time",
    "operator": "operator",
    "analyst": "operator",
    "notes": "notes",
    "comment": "notes",
    "comments": "notes",
}

PRIMARY_KEYWORDS = {"od 450", "od450", "absorbance", "epo", "pg/ml", "ng/ml", "elisa", "well", "dilution"}


def _find_header_row(lines: list) -> int:
    for i, line in enumerate(lines[:30]):
        cells = [c.strip().lower() for c in line.split(",")]
        if any(kw in cell for cell in cells for kw in PRIMARY_KEYWORDS):
            return i
    return -1


def _to_float(val: str):
    try:
        return float(str(val).strip().replace(",", ""))
    except (ValueError, AttributeError):
        return None


def parse_invivo_epo(step2_json_path: str, tmp_dir: str) -> str:
    with open(step2_json_path) as f:
        step2 = json.load(f)

    file_path = step2["original_path"]
    batch_id = step2["batch_id"]
    timestamp = step2["timestamp"]
    source_file = os.path.basename(file_path)
    parse_warnings = []

    lines = None
    for enc in ENCODINGS:
        try:
            with open(file_path, encoding=enc, errors="strict") as f:
                lines = [line.rstrip("\n") for line in f]
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if lines is None:
        raise ValueError("PARSE_ERROR: cannot decode file")

    header_idx = _find_header_row(lines)
    if header_idx == -1:
        raise ValueError("PARSE_ERROR: cannot locate header row in invivo_epo CSV")

    raw_header = [c.strip() for c in lines[header_idx].split(",")]
    data_lines = lines[header_idx + 1:]

    rows = []
    for row_num, raw_line in enumerate(data_lines):
        if not raw_line.strip():
            continue
        cells = [c.strip() for c in raw_line.split(",")]
        if all(c == "" for c in cells):
            continue
        raw_row = dict(zip(raw_header, cells))
        mapped = {}
        for col_raw, val in raw_row.items():
            key = COLUMN_MAP.get(col_raw.lower().strip())
            if key:
                mapped[key] = val

        # Handle ng/ml → pg/ml conversion
        epo_raw = mapped.get("epo_pg_ml")
        epo_ng = mapped.get("_epo_ng_ml")
        if epo_ng is not None:
            val = _to_float(epo_ng)
            epo_raw = str(val * 1000) if val is not None else None
            mapped["epo_pg_ml"] = epo_raw

        epo_fval = None
        if epo_raw:
            epo_fval = _to_float(epo_raw)
            if epo_fval is None and epo_raw != "":
                parse_warnings.append(
                    f"Row {row_num+1}: non-numeric epo_pg_ml='{epo_raw}'"
                )

        od_raw = mapped.get("od_450")
        od_fval = _to_float(od_raw) if od_raw else None

        dil_raw = mapped.get("dilution_factor")
        dil_fval = _to_float(dil_raw) if dil_raw else None

        measured_at = None
        date_part = mapped.get("_date", "")
        time_part = mapped.get("_time", "")
        if date_part or time_part:
            measured_at = f"{date_part} {time_part}".strip()

        rows.append({
            "batch_id": batch_id,
            "study_id": None,
            "measured_at": measured_at,
            "epo_pg_ml": epo_fval,
            "od_450": od_fval,
            "dilution_factor": dil_fval,
            "well_id": mapped.get("well_id"),
            "sample_id": mapped.get("sample_id"),
            "animal_id": mapped.get("animal_id"),
            "group_label": mapped.get("group_label"),
            "timepoint": mapped.get("timepoint"),
            "source_file": source_file,
            "operator": mapped.get("operator"),
            "notes": mapped.get("notes"),
        })

    if not rows:
        raise ValueError("PARSE_ERROR: no data rows found in invivo_epo CSV")

    result = {
        **step2,
        "assay_type": "invivo_epo",
        "rows": rows,
        "parse_warnings": parse_warnings,
        "status": "parsed",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_invivo_epo_{timestamp}_step3.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Parsed %d EPO rows, %d warnings", len(rows), len(parse_warnings))
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_invivo_epo.py <step2_json> <tmp_dir>")
        sys.exit(1)
    print(parse_invivo_epo(sys.argv[1], sys.argv[2]))
