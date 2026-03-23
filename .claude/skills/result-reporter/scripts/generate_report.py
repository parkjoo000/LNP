"""
STEP 7 – result-reporter: generate_report.py
Produce a Markdown run report and emit the final SSE event payload.
"""

import json
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("result-reporter")

ASSAY_TABLE_MAP = {
    "physical": "AssayResults_Physical",
    "invivo_fluc": "InVivo_FLUC",
    "invivo_epo": "InVivo_EPO",
    "toxicity": "Toxicity",
}


def _load_json(path):
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _fmt_timestamp(ts_str: str) -> str:
    """Convert YYYYMMDD_HHMMSS to YYYY-MM-DD HH:MM:SS."""
    try:
        dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ts_str or "unknown"


def _overall_status(step6: dict, step5: dict) -> str:
    if step6.get("status") == "ok":
        rows = step5.get("rows", [])
        has_warn_or_error = any(
            flag_val not in ("OK", "SKIP: null value")
            for row in rows
            for flag_val in json.loads(row.get("validation_flag", "{}") or "{}").values()
        )
        if has_warn_or_error or step6.get("rows_skipped", 0) > 0:
            return "PARTIAL"
        return "SUCCESS"
    return "FAILED"


def _parse_warnings_section(parse_warnings: list) -> str:
    if not parse_warnings:
        return "No parse warnings. All columns resolved without issues.\n"
    lines = ["| Row | Issue |", "|-----|-------|"]
    for w in parse_warnings:
        lines.append(f"| — | {w} |")
    return "\n".join(lines) + "\n"


def _validation_section(step5: dict) -> str:
    rows = step5.get("rows", [])
    if not rows:
        return "Validation data unavailable.\n"

    lines = []
    for row_idx, row in enumerate(rows):
        flag_str = row.get("validation_flag") or "{}"
        try:
            flags = json.loads(flag_str)
        except (json.JSONDecodeError, TypeError):
            flags = {}
        if not flags:
            continue
        lines.append(f"\n**Row {row_idx + 1}** (batch: {row.get('batch_id', '?')})\n")
        lines.append("| Field | Value | Flag |")
        lines.append("|-------|-------|------|")
        for field, flag in flags.items():
            value = row.get(field, "—")
            lines.append(f"| {field} | {value} | {flag} |")

    if not lines:
        return "All fields within acceptable ranges.\n"
    return "\n".join(lines) + "\n"


def _recommended_actions(step6: dict, overall_status: str, error: str) -> str:
    actions = []
    if "FK_MISSING" in (error or ""):
        batch_id = step6.get("batch_id", "?")
        actions.append(
            f"Register Batch ID `{batch_id}` in the database before re-submitting this file. "
            "Navigate to web interface → Batches → New Batch."
        )
    if "CLASSIFY_FAIL" in (error or ""):
        actions.append(
            "Check that the CSV was exported from a supported instrument or contact the data team."
        )
    if "PARSE_ERROR" in (error or ""):
        actions.append(
            "Inspect the source file for formatting issues (merged cells, missing header, unit rows)."
        )
    if step6.get("study_auto_created"):
        actions.append(
            "An `InVivo_study` record was auto-created with `operator_inferred=1`. "
            "Review and update study metadata via the web interface."
        )
    if overall_status == "PARTIAL":
        actions.append(
            "One or more validation flags were raised. Review the Validation Flags section above."
        )
    return actions


def generate_report(
    step6_json_path: str,
    step3_json_path: str,
    step5_json_path: str,
    logs_dir: str,
) -> dict:
    step6 = _load_json(step6_json_path)
    step3 = _load_json(step3_json_path)
    step5 = _load_json(step5_json_path)

    batch_id = step6.get("batch_id") or step3.get("batch_id") or "unknown"
    assay_type = (
        step6.get("assay_type")
        or step5.get("assay_type")
        or step3.get("assay_type")
        or step3.get("assay_type_confirmed")
        or "unknown"
    )
    timestamp = (
        step6.get("timestamp")
        or step5.get("timestamp")
        or step3.get("timestamp")
        or datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_id = f"{batch_id}_{assay_type}_{timestamp}"
    error = step6.get("error") or step5.get("error") or step3.get("error")
    overall = _overall_status(step6, step5)
    table_name = ASSAY_TABLE_MAP.get(assay_type, assay_type)
    parse_warnings = step3.get("parse_warnings", step6.get("parse_warnings", []))
    rows_inserted = step6.get("rows_inserted", 0)
    rows_skipped = step6.get("rows_skipped", 0)
    rows_attempted = step6.get("rows_attempted", rows_inserted + rows_skipped)
    confidence = step3.get("classification_confidence", step6.get("classification_confidence", "—"))
    matched_pattern = step3.get("matched_pattern", step6.get("matched_pattern", "—"))
    header_row = step3.get("header_row", step6.get("header_row", []))
    assay_type_hint = step3.get("assay_type_hint", "—")
    source_file = os.path.basename(step3.get("original_path", step6.get("original_path", "—")))

    skipped_ids = step6.get("skipped_result_ids", [])
    study_auto_created = step6.get("study_auto_created", False)

    hint_mismatch = assay_type_hint not in ("—", assay_type)

    actions = _recommended_actions(step6, overall, error)

    # ── Build Markdown ────────────────────────────────────────────────────────
    md = []
    md.append("# LNP Data Pipeline — Run Report\n")
    md.append("| Field           | Value |")
    md.append("|-----------------|-------|")
    md.append(f"| Run ID          | {run_id} |")
    md.append(f"| Timestamp       | {_fmt_timestamp(timestamp)} |")
    md.append(f"| Source File     | {source_file} |")
    md.append(f"| Batch ID        | {batch_id} |")
    md.append(f"| Assay Type      | {assay_type} ({confidence}) |")
    md.append(f"| Matched Pattern | {matched_pattern} |")
    md.append(f"| Overall Status  | {overall} |")
    md.append("")
    md.append("---\n")

    md.append("## Classification\n")
    md.append(f"- Assay type: **{assay_type}**")
    md.append(f"- Confidence: {confidence}")
    md.append(f"- Matched instrument pattern: `{matched_pattern}`")
    if header_row:
        md.append(f"- Header columns found: `{header_row}`")
    if hint_mismatch:
        md.append(
            f"\n> **Warning:** Filename hint was `{assay_type_hint}`, but header-based "
            f"classification returned `{assay_type}`. Header result is used as authoritative."
        )
    md.append("")
    md.append("---\n")

    md.append("## Parse Warnings\n")
    md.append(_parse_warnings_section(parse_warnings))
    md.append("---\n")

    md.append("## Validation Flags\n")
    md.append(_validation_section(step5))
    md.append("---\n")

    md.append("## Database Write Summary\n")
    md.append("| Metric          | Count |")
    md.append("|-----------------|-------|")
    md.append(f"| Rows attempted  | {rows_attempted} |")
    md.append(f"| Rows inserted   | {rows_inserted} |")
    md.append(f"| Rows skipped    | {rows_skipped} |")
    md.append("")
    if skipped_ids:
        md.append("Skipped result IDs (UNIQUE conflict — already in database):\n")
        for sid in skipped_ids:
            md.append(f"- `{sid}`")
        md.append("")
    if study_auto_created:
        md.append(
            f"> **Note:** No `InVivo_study` record existed for `batch_id={batch_id}`. "
            "A new study record was automatically created with `operator_inferred=1`. "
            "Review and update the study metadata via the web interface."
        )
        md.append("")
    md.append("---\n")

    md.append(f"## Overall Status: {overall}\n")
    if overall == "SUCCESS":
        md.append(f"Pipeline completed successfully. {rows_inserted} rows written to `{table_name}`.\n")
    elif overall == "PARTIAL":
        md.append(
            f"Pipeline completed with warnings. {rows_inserted} rows written; "
            f"{rows_skipped} skipped. Review validation flags above before accepting these results.\n"
        )
    else:
        failed_step = "unknown"
        if "FK_MISSING" in (error or ""):
            failed_step = "4 (FK validation)"
        elif "CLASSIFY_FAIL" in (error or ""):
            failed_step = "2 (classification)"
        elif "PARSE_ERROR" in (error or ""):
            failed_step = "3 (parsing)"
        md.append(f"Pipeline halted at Step {failed_step}: `{error}`\n")

    if actions:
        md.append("---\n")
        md.append("## Recommended Actions\n")
        for action in actions:
            md.append(f"- [ ] {action}")
        md.append("")

    report_text = "\n".join(md)

    # Write to logs dir
    log_filename = f"run_{run_id}.log"
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, log_filename)
    try:
        with open(log_path, "w") as f:
            f.write(report_text)
        logger.info("Report written to %s", log_path)
    except OSError as exc:
        logger.error("REPORT_WRITE_ERROR: %s", exc)

    # SSE payload
    sse_payload = {
        "event": "pipeline_complete",
        "run_id": run_id,
        "status": overall,
        "log_file": log_filename,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
    }
    return sse_payload


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: generate_report.py <step6_json> <step3_json> <step5_json> <logs_dir>")
        sys.exit(1)
    result = generate_report(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print(json.dumps(result, indent=2))
