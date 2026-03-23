"""
LNP Watchdog — monitors input/raw/ for new CSV files and triggers the pipeline.
Requires: watchdog package (pip install watchdog)
Usage: python watchdog_runner.py
"""

import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("watchdog")

ROOT = Path(__file__).resolve().parent
INPUT_RAW = ROOT / "input" / "raw"


def _run():
    try:
        from watchdog.events import FileCreatedEvent, FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        logger.error("watchdog package not installed. Run: pip install watchdog")
        sys.exit(1)

    import pipeline as pl

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if isinstance(event, FileCreatedEvent) and event.src_path.endswith(".csv"):
                logger.info("Detected new file: %s", event.src_path)
                try:
                    pl.run_pipeline(event.src_path)
                except Exception as exc:
                    logger.error("Pipeline error: %s", exc)

    observer = Observer()
    observer.schedule(Handler(), str(INPUT_RAW), recursive=False)
    observer.start()
    logger.info("Watching %s for new CSV files...", INPUT_RAW)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    _run()
