"""
STEP 2: file-classifier
Classify assay type from CSV header row against known instrument column patterns.
Header-based classification is authoritative over filename hint.
"""

import csv
import json
import logging
import os
import shutil
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("file-classifier")

# ---------------------------------------------------------------------------
# Pattern definitions (derived from references/column_patterns.md)
# ---------------------------------------------------------------------------

PATTERNS = {
    "physical": [
        {
            "name": "Zetasizer_v3",
            "required": [
                {"z-ave (d.nm)", "z-avg (d.nm)", "z-average (d.nm)"},
                {"pdi", "polydispersity index"},
                {"zeta potential (mv)", "zeta (mv)"},
            ],
        },
        {
            "name": "NanoSight_NS300",
            "required": [
                {"mean", "mean diameter (nm)"},
                {"mode", "mode diameter (nm)", "d10", "d50", "d90", "concentration (particles/ml)"},
            ],
        },
        {
            "name": "ZetaView",
            "required": [
                {"size [nm]", "size (nm)"},
                {"pdi", "polydispersity"},
                {"zeta potential [mv]"},
            ],
        },
        {
            "name": "Generic_physical",
            "required": [
                {"size", "diameter", "pdi", "zeta", "ee%", "encapsulation efficiency", "nm"},
                {"size", "diameter", "pdi", "zeta", "ee%", "encapsulation efficiency", "nm"},
            ],
            "min_match": 2,
            "confidence": "MEDIUM",
        },
    ],
    "invivo_fluc": [
        {
            "name": "LivingImage_4x",
            "required": [
                {"total flux [p/s]", "total flux (p/s)", "total flux"},
                {"average radiance [p/s/cm²/sr]", "avg radiance"},
                {"roi", "region"},
            ],
        },
        {
            "name": "LivingImage_export_csv",
            "required": [
                {"measurement", "value"},
                {"unit"},
                {"image", "acquisition"},
            ],
        },
        {
            "name": "Generic_FLUC",
            "required": [
                {"flux", "bioluminescence", "radiance", "luminescence", "photons"},
            ],
            "confidence": "MEDIUM",
        },
    ],
    "invivo_epo": [
        {
            "name": "SpectraMax_EPO",
            "required": [
                {"well", "well id"},
                {"od 450", "od450", "absorbance at 450"},
                {"sample", "sample id"},
                {"dilution factor", "dilution"},
            ],
        },
        {
            "name": "Generic_ELISA",
            "required": [
                {"od450", "absorbance", "conc", "pg/ml", "ng/ml", "concentration"},
                {"od450", "absorbance", "conc", "pg/ml", "ng/ml", "concentration"},
            ],
            "min_match": 2,
            "confidence": "MEDIUM",
        },
    ],
    "toxicity": [
        {
            "name": "Fuji_DriChem",
            "required": [
                {"alt(gpt)", "alt (u/l)", "alt"},
                {"ast(got)", "ast (u/l)", "ast"},
                {"bun", "bun (mg/dl)"},
            ],
        },
        {
            "name": "Hitachi_7180",
            "required": [
                {"alanine aminotransferase", "alanine aminotransferase"},
                {"aspartate aminotransferase", "aspartate aminotransferase"},
                {"blood urea nitrogen", "urea nitrogen"},
            ],
        },
        {
            "name": "VetScan",
            "required": [
                {"alt/sgpt"},
                {"ast/sgot"},
                {"bun/urea"},
            ],
        },
        {
            "name": "Generic_blood",
            "required": [
                {"alt", "ast", "bun", "creatinine", "crea", "liver", "kidney", "toxicology"},
                {"alt", "ast", "bun", "creatinine", "crea", "liver", "kidney", "toxicology"},
            ],
            "min_match": 2,
            "confidence": "MEDIUM",
        },
    ],
}

ENCODINGS = ["utf-8", "cp949", "latin-1"]


def _read_header(file_path: str) -> list:
    """Try multiple encodings; scan up to 30 lines for header row."""
    for enc in ENCODINGS:
        try:
            with open(file_path, encoding=enc, errors="strict") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= 30:
                        break
                    lines.append(line.rstrip("\n"))
            # Find header: first line with multiple comma-separated tokens
            for line in lines:
                cols = [c.strip() for c in line.split(",")]
                if len(cols) >= 2 and any(c for c in cols):
                    return cols
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError("ENCODING_ERROR: cannot decode file with utf-8, cp949, latin-1")


def _score_pattern(header_lower: set, pattern: dict) -> tuple:
    """
    Returns (matched_required_groups, total_required_groups, instrument_name, base_confidence).
    For patterns with min_match, count individual token hits across the flat union.
    """
    required_groups = pattern["required"]
    forced_confidence = pattern.get("confidence", "HIGH")
    min_match = pattern.get("min_match", None)

    if min_match is not None:
        # Flatten all tokens, count distinct hits
        all_tokens = set()
        for grp in required_groups:
            all_tokens |= grp
        matched = sum(1 for tok in all_tokens if tok in header_lower)
        total = min_match
        return (matched, total, pattern["name"], forced_confidence)

    # Standard group matching: each group contributes 1 if any alias matches
    matched = sum(
        1 for grp in required_groups if grp & header_lower
    )
    return (matched, len(required_groups), pattern["name"], forced_confidence)


def classify_file(step1_json_path: str, tmp_dir: str, unclassified_dir: str) -> str:
    """Classify assay type; returns step2 JSON path or raises on CLASSIFY_FAIL."""
    with open(step1_json_path) as f:
        step1 = json.load(f)

    file_path = step1["original_path"]
    batch_id = step1["batch_id"]
    assay_type_hint = step1["assay_type_hint"]
    timestamp = step1["timestamp"]

    try:
        header_row = _read_header(file_path)
    except ValueError as e:
        _write_error_and_move(step1, str(e), tmp_dir, unclassified_dir)
        raise

    if not header_row or all(c == "" for c in header_row):
        msg = "EMPTY_HEADER"
        logger.error(msg)
        _write_error_and_move(step1, msg, tmp_dir, unclassified_dir)
        raise ValueError(msg)

    header_lower = {c.lower().strip() for c in header_row if c.strip()}

    best_assay = None
    best_instrument = None
    best_confidence = "LOW"
    best_score = (0, 1)

    for assay_type, instruments in PATTERNS.items():
        for instrument in instruments:
            matched, total, name, forced_conf = _score_pattern(header_lower, instrument)
            ratio = matched / total if total else 0

            if ratio >= 1.0:
                conf = "HIGH" if forced_conf == "HIGH" else forced_conf
            elif ratio >= 0.6:
                conf = "MEDIUM"
            else:
                conf = "LOW"

            # Choose best by ratio, then prefer HIGH confidence
            score = (matched / total if total else 0)
            if conf != "LOW":
                prev_ratio = best_score[0] / best_score[1] if best_score[1] else 0
                if score > prev_ratio or (score == prev_ratio and conf == "HIGH" and best_confidence != "HIGH"):
                    best_assay = assay_type
                    best_instrument = name
                    best_confidence = conf
                    best_score = (matched, total)

    if best_confidence == "LOW" or best_assay is None:
        msg = f"CLASSIFY_FAIL: headers={header_row}"
        logger.error(msg)
        _write_error_and_move(step1, msg, tmp_dir, unclassified_dir)
        raise ValueError(msg)

    if best_assay != assay_type_hint:
        logger.warning(
            "HINT_MISMATCH: filename says %s, header says %s", assay_type_hint, best_assay
        )

    result = {
        **step1,
        "assay_type_confirmed": best_assay,
        "classification_confidence": best_confidence,
        "matched_pattern": best_instrument,
        "header_row": header_row,
        "status": "classified",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_{best_assay}_{timestamp}_step2.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Classified as %s (%s) via %s", best_assay, best_confidence, best_instrument)
    return out_path


def _write_error_and_move(step1: dict, error_msg: str, tmp_dir: str, unclassified_dir: str):
    batch_id = step1.get("batch_id", "unknown")
    timestamp = step1.get("timestamp", "00000000_000000")
    hint = step1.get("assay_type_hint", "unknown")
    error_result = {**step1, "status": "classify_failed", "error": error_msg}
    os.makedirs(tmp_dir, exist_ok=True)
    out_path = os.path.join(tmp_dir, f"{batch_id}_{hint}_{timestamp}_step2_error.json")
    with open(out_path, "w") as f:
        json.dump(error_result, f, indent=2)

    src = step1.get("original_path", "")
    if src and os.path.exists(src):
        os.makedirs(unclassified_dir, exist_ok=True)
        dst = os.path.join(unclassified_dir, os.path.basename(src))
        shutil.move(src, dst)
        logger.info("Moved unclassified file to %s", dst)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: classify_file.py <step1_json> <tmp_dir> <unclassified_dir>")
        sys.exit(1)
    out = classify_file(sys.argv[1], sys.argv[2], sys.argv[3])
    print(out)
