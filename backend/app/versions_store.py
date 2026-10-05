"""Disk storage for the named versions (section 13: "versions persist after
closing the program").

All versions live in ONE JSON file: {"<name>": <scenario exported in
topology format>, ...}. It is the backend's own storage, not an input file
chosen by the user (section 12 forbids fixed INPUT paths; loading a
scenario still goes through the file explorer and POST /scenario/load).

Default location: backend/data/versions.json. It can be changed with the
SISMOLAB_VERSIONS_FILE environment variable (useful for tests).
"""
import json
import os
from datetime import datetime
from pathlib import Path

_DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "versions.json"


def versions_path() -> Path:
    return Path(os.environ.get("SISMOLAB_VERSIONS_FILE", _DEFAULT_FILE))


def load_versions() -> dict:
    """Read the versions file. Missing file -> no versions.

    If the file is damaged (not valid JSON or not an object), it is renamed
    to versions.json.bad-<timestamp> instead of being overwritten later, so
    nothing is lost, and the program starts with no versions."""
    path = versions_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("the versions file must contain a JSON object")
        return data
    except (OSError, ValueError) as error:
        backup = path.with_name(f"{path.name}.bad-{datetime.now():%Y%m%d-%H%M%S}")
        try:
            path.rename(backup)
        except OSError:
            pass
        print(f"[versions] Could not read {path} ({error}); moved to {backup.name}")
        return {}


def save_versions(versions: dict) -> None:
    """Write all versions. Writes to a temporary file first and then
    replaces the real one, so a crash in the middle never leaves a
    half-written versions.json."""
    path = versions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(versions, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
