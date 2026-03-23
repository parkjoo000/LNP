"""
STEP 3 – data-parser: parse_invivo_fluc.py
Parses in vivo bioluminescence (FLUC / IVIS Lumina) CSV files.
study_id is set to null; resolved by db-writer at STEP 6.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("parse-invivo-fluc")

ENCODINGS = ["utf-8", "cp949", "latin-1"]

COLUMN_MAP = {
    # Total flux
    "total flux (p/s)": "fluc_total_flux",
    "total flux": "fluc_total_flux",
    "flux (p/s)": "fluc_total_flux",
    "flux": "fluc_total_flux",
    "bioluminescence (p/s)": "fluc_total_flux",
    "bioluminescence": "fluc_total_flux",
    "radiance (p/s)": "fluc_total_flux",
    "signal (p/s)": "fluc_total_flux",
    # ROI / region label
    "roi": "roi_label",
    "region": "roi_label",
    "group": "group_label",
    "animal id": "animal_id",
    "animal": "animal_id",
    "mouse": "animal_id",
    "subject": "animal_id",
    # Organ / tissue
    "organ": "organ",
    "tissue": "organ",
    # Metadata
    "date": "_date",
    "time": "_time",
    "datetime": "_datetime",
    "timepoint": "timepoint_h",
    "time point (h)": "timepoint_h",
    "timepoint (h)": "timepoint_h",
    "time (h)": "timepoint_h",
    "operator": "operator",
    "analyst": "operator",
    "notes": "notes",
    "comment": "notes",
    "comments": "notes",
}

PRIMARY_KEYWORDS = {"total flux", "flux", "bioluminescence", "radiance", "signal"}


def _find_header_row(lines):
    for i, line in enumerate(lines[:30]):
        cells = [c.strip().lower() for c in line.split(",")]
        if any(kw in cell for cell in cells for kw in PRIMARY_KEYWORDS):
            return i
    return -1


def _to_float(val):
    try:
        return float(val.strip())
    except (ValueError, AttributeError):
        return None


def _parse_datetime(mapped):
    dt_val = mapped.get("_datetime")
    if dt_val:
        return dt_val
    return (f"{mapped.get('_date', '')} {mapped.get('_time', '')}").strip() or None


def parse_invivo_fluc(step2_json_path: str, tmp_dir: str) -> str:
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
        raise ValueError("PARSE_ERROR: cannot locate header row in invivo_fluc CSV")

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

        record = {
            "batch_id": batch_id,
            "study_id": None,  # resolved at STEP 6
            "measured_at": _parse_datetime(mapped),
            "animal_id": mapped.get("animal_id"),
            "organ": mapped.get("organ"),
            "roi_label": mapped.get("roi_label"),
            "group_label": mapped.get("group_label"),
            "timepoint_h": None,
            "fluc_total_flux": None,
            "source_file": source_file,
            "operator": mapped.get("operator"),
            "notes": mapped.get("notes"),
        }

        for field in ("fluc_total_flux", "timepoint_h"):
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
        raise ValueError("PARSE_ERROR: no data rows found in invivo_fluc CSV")

    result = {
        **step2,
        "assay_type": "invivo_fluc",
        "rows": rows,
        "parse_warnings": parse_warnings,
        "status": "parsed",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_invivo_fluc_{timestamp}_step3.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Parsed %d invivo_fluc rows, %d warnings", len(rows), len(parse_warnings))
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_invivo_fluc.py <step2_json> <tmp_dir>")
        sys.exit(1)
    print(parse_invivo_fluc(sys.argv[1], sys.argv[2]))
