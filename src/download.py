"""Download the PaySim data from Kaggle (about 180 MB zipped, 470 MB unzipped).

Needs kaggle.json in C:\\Users\\<you>\\.kaggle\\ (the same key as the credit
project). PaySim is a public dataset, so there are no rules to accept.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def download_dataset(dataset: str, raw_dir: Path, file_name: str) -> Path:
    """Download and unzip the dataset unless the CSV is already there."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / file_name
    if target.exists():
        log.info("%s already present, skipping download.", target.name)
        return target
    if shutil.which("kaggle") is None:
        raise RuntimeError(
            "The 'kaggle' command was not found. Activate the virtual environment "
            "(.venv\\Scripts\\activate) and run: pip install -r requirements.txt"
        )
    log.info("Downloading %s from Kaggle...", dataset)
    result = subprocess.run(
        ["kaggle", "datasets", "download", "-d", dataset, "-p", str(raw_dir), "--unzip"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        hint = "\nHint: 401 means kaggle.json is missing or wrong." if "401" in (result.stderr + result.stdout) else ""
        raise RuntimeError(f"Kaggle download failed:\n{result.stderr or result.stdout}{hint}")
    if not target.exists():
        found = [p.name for p in raw_dir.glob("*.csv")]
        raise FileNotFoundError(f"Expected {file_name} after download, found {found}")
    log.info("Download complete: %s", target)
    return target
