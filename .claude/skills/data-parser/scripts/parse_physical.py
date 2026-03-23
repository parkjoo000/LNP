"""
STEP 3 – data-parser: parse_physical.py
Parses physical characterization CSV files (Zetasizer, NanoSight, ZetaView, generic).
Outputs normalized row list as step3 JSON.
"""

import csv
import json
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("parse-physical")

ENCODINGS = ["utf-8", "cp949", "latin-1"]

# Map lowercase device column names → canonical DB field names
COLUMN_MAP = {
    # Z-average / size
    "z-ave (d.nm)": "z_avg_nm",
    "z-avg (d.nm)": "z_avg_nm",
    "z-average (d.nm)": "z_avg_nm",
    "z-ave": "z_avg_nm",
    "z-average": "z_avg_nm",
    "size (nm)": "z_avg_nm",
    "size [nm]": "z_avg_nm",
    "size": "z_avg_nm",
    "mean": "z_avg_nm",
    "mean diameter (nm)": "z_avg_nm",
    "diameter (nm)": "z_avg_nm",
    "diameter": "z_avg_nm",
    "d.nm": "z_avg_nm",
    # PDI
    "pdi": "pdi",
    "polydispersity index": "pdi",
    "polydispersity": "pdi",
    "pi": "pdi",
    # Zeta potential
    "zeta potential (mv)": "zeta_potential_mv",
    "zeta potential [mv]": "zeta_potential_mv",
    "zeta (mv)": "zeta_potential_mv",
    "zeta": "zeta_potential_mv",
    "zeta-potential (mv)": "zeta_potential_mv",
    # Encapsulation efficiency
    "ee%": "ee_percent",
    "ee (%)": "ee_percent",
    "encapsulation efficiency (%)": "ee_percent",
    "encapsulation efficiency": "ee_percent",
    "encapsulation %": "ee_percent",
    # Concentration
    "concentration (mg/ml)": "concentration_mg_ml",
    "concentration (mg/ml)": "concentration_mg_ml",
    "conc (mg/ml)": "concentration_mg_ml",
    "conc. (mg/ml)": "concentration_mg_ml",
    "concentration_mg_ml": "concentration_mg_ml",
    # Timestamp / operator / notes
    "date": "_date",
    "time": "_time",
    "datetime": "_datetime",
    "measurement date": "_date",
    "operator": "operator",
    "analyst": "operator",
    "notes": "notes",
    "comment": "notes",
    "comments": "notes",
}

PRIMARY_KEYWORDS = {"z-ave", "z-avg", "z-average", "pdi", "zeta", "size", "diameter", "mean"}


def _find_header_row(lines: list) -> int:
    """Return index of header row among first 30 lines, or -1 if not found."""
    for i, line in enumerate(lines[:30]):
        cells = [c.strip().lower() for c in line.split(",")]
        if any(kw in cell for cell in cells for kw in PRIMARY_KEYWORDS):
            return i
    return -1


def _to_float(val: str):
    """Return float or None."""
    try:
        return float(val.strip())
    except (ValueError, AttributeError):
        return None


def _parse_datetime(row_dict: dict) -> str | None:
    dt_val = row_dict.get("_datetime")
    if dt_val:
        return dt_val
    date_val = row_dict.get("_date", "")
    time_val = row_dict.get("_time", "")
    combined = f"{date_val} {time_val}".strip()
    if combined:
        return combined
    return None


def parse_physical(step2_json_path: str, tmp_dir: str) -> str:
    with open(step2_json_path) as f:
        step2 = json.load(f)

    file_path = step2["original_path"]
    batch_id = step2["batch_id"]
    timestamp = step2["timestamp"]
    source_file = os.path.basename(file_path)
    parse_warnings = []

    # Read all lines with encoding fallback
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
        raise ValueError("PARSE_ERROR: cannot locate header row in physical CSV")

    # Parse with csv.DictReader starting from header line
    raw_header = [c.strip() for c in lines[header_idx].split(",")]
    data_lines = lines[header_idx + 1:]

    rows = []
    for row_num, raw_line in enumerate(data_lines):
        if not raw_line.strip():
            continue
        cells = [c.strip() for c in raw_line.split(",")]
        if len(cells) < 2 or all(c == "" for c in cells):
            continue

        raw_row = dict(zip(raw_header, cells))
        mapped = {}
        for col_raw, val in raw_row.items():
            key = COLUMN_MAP.get(col_raw.lower().strip())
            if key:
                mapped[key] = val

        # Build normalized record
        record = {
            "batch_id": batch_id,
            "measured_at": _parse_datetime(mapped),
            "z_avg_nm": None,
            "pdi": None,
            "zeta_potential_mv": None,
            "ee_percent": None,
            "concentration_mg_ml": None,
            "source_file": source_file,
            "operator": mapped.get("operator"),
            "notes": mapped.get("notes"),
        }

        for field in ("z_avg_nm", "pdi", "zeta_potential_mv", "ee_percent", "concentration_mg_ml"):
            raw_val = mapped.get(field)
            if raw_val is not None:
                fval = _to_float(raw_val)
                if fval is None and raw_val != "":
                    parse_warnings.append(
                        f"Row {row_num+1}: non-numeric value '{raw_val}' for '{field}'"
                    )
                record[field] = fval

        rows.append(record)

    if not rows:
        raise ValueError("PARSE_ERROR: no data rows found in physical CSV")

    result = {
        **step2,
        "assay_type": "physical",
        "rows": rows,
        "parse_warnings": parse_warnings,
        "status": "parsed",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_physical_{timestamp}_step3.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Parsed %d physical rows, %d warnings", len(rows), len(parse_warnings))
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_physical.py <step2_json> <tmp_dir>")
        sys.exit(1)
    print(parse_physical(sys.argv[1], sys.argv[2]))
