"""
STEP 3 – data-parser: parse_invivo_fluc.py
Parses in-vivo bioluminescence (FLUC) CSV files from IVIS/LivingImage instruments.
Outputs normalized row list as step3 JSON.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("parse-invivo-fluc")

ENCODINGS = ["utf-8", "cp949", "latin-1"]

COLUMN_MAP = {
    # Total flux (primary measurement)
    "total flux [p/s]": "fluc_total_flux",
    "total flux (p/s)": "fluc_total_flux",
    "total flux": "fluc_total_flux",
    "flux": "fluc_total_flux",
    "photons/second": "fluc_total_flux",
    "photons/sec": "fluc_total_flux",
    # Radiance
    "average radiance [p/s/cm²/sr]": "avg_radiance",
    "average radiance (p/s/cm²/sr)": "avg_radiance",
    "avg radiance": "avg_radiance",
    "radiance": "avg_radiance",
    # Region of interest
    "roi": "roi_label",
    "region": "roi_label",
    "region of interest": "roi_label",
    "label": "roi_label",
    # Animal / subject
    "animal": "animal_id",
    "animal id": "animal_id",
    "mouse": "animal_id",
    "subject": "animal_id",
    # Group / treatment
    "group": "group_label",
    "treatment": "group_label",
    "treatment group": "group_label",
    # Time / image info
    "date": "_date",
    "time": "_time",
    "image": "image_label",
    "acquisition": "image_label",
    "timepoint": "timepoint",
    "time point": "timepoint",
    "day": "timepoint",
    # Operator/notes
    "operator": "operator",
    "analyst": "operator",
    "notes": "notes",
    "comment": "notes",
    "comments": "notes",
    # measurement/value pair (LivingImage export format)
    "measurement": "_measurement_name",
    "value": "_measurement_value",
    "unit": "_measurement_unit",
}

PRIMARY_KEYWORDS = {"flux", "radiance", "bioluminescence", "luminescence", "photons", "roi", "measurement"}


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

    # Detect LivingImage key-value export format
    is_kv_format = any(
        c.lower().strip() in ("measurement", "value") for c in raw_header
    )

    rows = []
    if is_kv_format:
        # Accumulate key-value pairs into a single record
        kv = {}
        for raw_line in data_lines:
            if not raw_line.strip():
                continue
            cells = [c.strip() for c in raw_line.split(",")]
            row_dict = dict(zip(raw_header, cells))
            name = row_dict.get("Measurement") or row_dict.get("measurement") or ""
            val = row_dict.get("Value") or row_dict.get("value") or ""
            unit = row_dict.get("Unit") or row_dict.get("unit") or ""
            if name.lower() in ("total flux", "total flux [p/s]", "total flux (p/s)"):
                kv["fluc_total_flux"] = _to_float(val)
            elif "radiance" in name.lower():
                kv["avg_radiance"] = _to_float(val)
        if kv:
            rows.append({
                "batch_id": batch_id,
                "study_id": None,
                "measured_at": None,
                "fluc_total_flux": kv.get("fluc_total_flux"),
                "avg_radiance": kv.get("avg_radiance"),
                "roi_label": None,
                "animal_id": None,
                "group_label": None,
                "timepoint": None,
                "image_label": None,
                "source_file": source_file,
                "operator": None,
                "notes": None,
            })
    else:
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

            fluc_val = mapped.get("fluc_total_flux")
            if fluc_val is not None:
                fval = _to_float(fluc_val)
                if fval is None and fluc_val != "":
                    parse_warnings.append(
                        f"Row {row_num+1}: non-numeric fluc_total_flux='{fluc_val}'"
                    )
            else:
                fval = None

            rad_val = mapped.get("avg_radiance")
            rad_fval = _to_float(rad_val) if rad_val else None

            measured_at = None
            date_part = mapped.get("_date", "")
            time_part = mapped.get("_time", "")
            if date_part or time_part:
                measured_at = f"{date_part} {time_part}".strip()

            rows.append({
                "batch_id": batch_id,
                "study_id": None,
                "measured_at": measured_at,
                "fluc_total_flux": fval,
                "avg_radiance": rad_fval,
                "roi_label": mapped.get("roi_label"),
                "animal_id": mapped.get("animal_id"),
                "group_label": mapped.get("group_label"),
                "timepoint": mapped.get("timepoint"),
                "image_label": mapped.get("image_label"),
                "source_file": source_file,
                "operator": mapped.get("operator"),
                "notes": mapped.get("notes"),
            })

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

    logger.info("Parsed %d FLUC rows, %d warnings", len(rows), len(parse_warnings))
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_invivo_fluc.py <step2_json> <tmp_dir>")
        sys.exit(1)
    print(parse_invivo_fluc(sys.argv[1], sys.argv[2]))
