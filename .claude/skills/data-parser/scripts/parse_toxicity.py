"""
STEP 3 – data-parser: parse_toxicity.py
Parses blood chemistry / toxicology CSV files (ALT, AST, BUN, creatinine, etc.)
from Fuji DriChem, Hitachi 7180, VetScan, or generic exporters.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("parse-toxicity")

ENCODINGS = ["utf-8", "cp949", "latin-1"]

COLUMN_MAP = {
    # ALT
    "alt": "alt_u_l",
    "alt (u/l)": "alt_u_l",
    "alt(gpt)": "alt_u_l",
    "alt/sgpt": "alt_u_l",
    "alanine aminotransferase": "alt_u_l",
    "alanine aminotransferase (u/l)": "alt_u_l",
    "sgpt": "alt_u_l",
    "gpt": "alt_u_l",
    # AST
    "ast": "ast_u_l",
    "ast (u/l)": "ast_u_l",
    "ast(got)": "ast_u_l",
    "ast/sgot": "ast_u_l",
    "aspartate aminotransferase": "ast_u_l",
    "aspartate aminotransferase (u/l)": "ast_u_l",
    "sgot": "ast_u_l",
    "got": "ast_u_l",
    # BUN
    "bun": "bun_mg_dl",
    "bun (mg/dl)": "bun_mg_dl",
    "bun/urea": "bun_mg_dl",
    "blood urea nitrogen": "bun_mg_dl",
    "blood urea nitrogen (mg/dl)": "bun_mg_dl",
    "urea nitrogen": "bun_mg_dl",
    "urea (mg/dl)": "bun_mg_dl",
    # Creatinine
    "creatinine": "creatinine_mg_dl",
    "crea": "creatinine_mg_dl",
    "creatinine (mg/dl)": "creatinine_mg_dl",
    "crea (mg/dl)": "creatinine_mg_dl",
    # Animal / sample
    "animal id": "animal_id",
    "animal": "animal_id",
    "mouse": "animal_id",
    "subject": "animal_id",
    "sample": "animal_id",
    "sample id": "animal_id",
    "id": "animal_id",
    "group": "group_label",
    # Metadata
    "date": "_date",
    "time": "_time",
    "datetime": "_datetime",
    "timepoint": "timepoint_h",
    "time point (h)": "timepoint_h",
    "timepoint (h)": "timepoint_h",
    "operator": "operator",
    "analyst": "operator",
    "notes": "notes",
    "comment": "notes",
    "comments": "notes",
}

PRIMARY_KEYWORDS = {"alt", "ast", "bun", "alanine", "aspartate", "creatinine", "aminotransferase"}


def _find_header_row(lines):
    for i, line in enumerate(lines[:30]):
        cells = [c.strip().lower() for c in line.split(",")]
        if any(kw in cell for cell in cells for kw in PRIMARY_KEYWORDS):
            return i
    return -1


def _to_float(val):
    try:
        return float(str(val).strip())
    except (ValueError, AttributeError):
        return None


def _parse_datetime(mapped):
    dt_val = mapped.get("_datetime")
    if dt_val:
        return dt_val
    return (f"{mapped.get('_date', '')} {mapped.get('_time', '')}").strip() or None


def parse_toxicity(step2_json_path: str, tmp_dir: str) -> str:
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
        raise ValueError("PARSE_ERROR: cannot locate header row in toxicity CSV")

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
            "measured_at": _parse_datetime(mapped),
            "animal_id": mapped.get("animal_id"),
            "group_label": mapped.get("group_label"),
            "timepoint_h": None,
            "alt_u_l": None,
            "ast_u_l": None,
            "bun_mg_dl": None,
            "creatinine_mg_dl": None,
            "source_file": source_file,
            "operator": mapped.get("operator"),
            "notes": mapped.get("notes"),
        }

        for field in ("alt_u_l", "ast_u_l", "bun_mg_dl", "creatinine_mg_dl", "timepoint_h"):
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
        raise ValueError("PARSE_ERROR: no data rows found in toxicity CSV")

    result = {
        **step2,
        "assay_type": "toxicity",
        "rows": rows,
        "parse_warnings": parse_warnings,
        "status": "parsed",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_toxicity_{timestamp}_step3.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Parsed %d toxicity rows, %d warnings", len(rows), len(parse_warnings))
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_toxicity.py <step2_json> <tmp_dir>")
        sys.exit(1)
    print(parse_toxicity(sys.argv[1], sys.argv[2]))
