"""
STEP 1: file-receiver
Verify the incoming CSV file, extract metadata from filename, and compute integrity hash.
"""

import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("file-receiver")

FILENAME_PATTERN = re.compile(
    r"^(?P<batch_id>[A-Za-z0-9\-]+)_(?P<assay_type>physical|invivo_fluc|invivo_epo|toxicity)_(?P<date>\d{8})\.csv$"
)


def receive_file(file_path: str, tmp_dir: str) -> str:
    """Validate file, extract metadata, write step1 JSON. Returns JSON path."""
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.access(file_path, os.R_OK):
        logger.error("PERMISSION_ERROR: cannot read %s", file_path)
        raise PermissionError(f"PERMISSION_ERROR: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        logger.error("EMPTY_FILE: %s", file_path)
        raise ValueError(f"EMPTY_FILE: {file_path}")

    filename = os.path.basename(file_path)
    m = FILENAME_PATTERN.match(filename)
    if not m:
        logger.error("FILENAME_INVALID: %s", filename)
        raise ValueError(f"FILENAME_INVALID: {filename}")

    batch_id = m.group("batch_id")
    assay_type_hint = m.group("assay_type")
    date_str = m.group("date")

    sha256 = _sha256(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    result = {
        "original_path": os.path.abspath(file_path),
        "batch_id": batch_id,
        "assay_type_hint": assay_type_hint,
        "date_str": date_str,
        "timestamp": timestamp,
        "file_size_bytes": file_size,
        "sha256": sha256,
        "status": "received",
    }

    os.makedirs(tmp_dir, exist_ok=True)
    out_name = f"{batch_id}_{assay_type_hint}_{timestamp}_step1.json"
    out_path = os.path.join(tmp_dir, out_name)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Received: %s → %s", filename, out_path)
    return out_path


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: receive_file.py <csv_path> <tmp_dir>")
        sys.exit(1)
    out = receive_file(sys.argv[1], sys.argv[2])
    print(out)
