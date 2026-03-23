"""
STEP 5 – db-validator: validate_range.py
Apply numeric range rules from config/validation_rules.yaml to each parsed row.
Adds a validation_flag JSON string to each row. Never halts on range violations.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("validate-range")

ASSAY_TABLE_MAP = {
    "physical": "AssayResults_Physical",
    "invivo_fluc": "InVivo_FLUC",
    "invivo_epo": "InVivo_EPO",
    "toxicity": "Toxicity",
}


def _load_rules(rules_path: str) -> dict:
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed; skipping range validation")
        return {}
    try:
        with open(rules_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("RULES_MISSING: %s not found; skipping range check", rules_path)
        return {}
    except Exception as exc:
        logger.warning("RULES_PARSE_ERROR: %s", exc)
        return {}


def _flag_value(value, field_rules: dict) -> str:
    if value is None:
        return "SKIP: null value"

    min_val = field_rules.get("min")
    max_val = field_rules.get("max")
    warn_threshold = field_rules.get("warn_threshold")
    warn_only = field_rules.get("warn_only", False)
    unit = field_rules.get("unit", "")

    out_of_range = False
    if min_val is not None and value < min_val:
        out_of_range = True
    if max_val is not None and value > max_val:
        out_of_range = True

    if out_of_range:
        level = "WARN" if warn_only else "ERROR"
        return f"{level}: {value} out of range [{min_val},{max_val}] {unit}".strip()

    if warn_threshold is not None and value > warn_threshold:
        return f"WARN: {value} {unit} > threshold {warn_threshold}".strip()

    return "OK"


def validate_range(step3_json_path: str, rules_path: str, tmp_dir: str) -> str:
    with open(step3_json_path) as f:
        step3 = json.load(f)

    # Accept both step3 (direct parser output) and step4 (fk-validated) as input
    assay_type = step3.get("assay_type", step3.get("assay_type_confirmed", ""))
    batch_id = step3["batch_id"]
    timestamp = step3["timestamp"]

    rules = _load_rules(rules_path)
    table_name = ASSAY_TABLE_MAP.get(assay_type, "")
    table_rules = rules.get(table_name, {})

    if not table_rules:
        logger.warning("No rules found for table '%s'; all flags will be 'OK'", table_name)

    flagged_rows = []
    for row in step3.get("rows", []):
        flags = {}
        for field, field_rules in table_rules.items():
            value = row.get(field)
            flags[field] = _flag_value(value, field_rules)

        row_copy = dict(row)
        row_copy["validation_flag"] = json.dumps(flags)
        flagged_rows.append(row_copy)

    result = {
        **step3,
        "rows": flagged_rows,
        "status": "range_validated",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_{assay_type}_{timestamp}_step5.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(
        "Range validation done: %d rows, assay=%s", len(flagged_rows), assay_type
    )
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: validate_range.py <step3_or_step4_json> <rules_yaml> <tmp_dir>")
        sys.exit(1)
    print(validate_range(sys.argv[1], sys.argv[2], sys.argv[3]))
