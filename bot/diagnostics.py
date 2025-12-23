from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Mapping, cast

SNAPSHOT_PATH = Path("bot/run_snapshot.json")

KEY_ENVS = [
    "EXECUTE_ORDERS",
    "DELTA_DRY_ORDERS",
    "I_UNDERSTAND_LIVE",
    "DELTA_BASE_URL",
    "WD_MAX_API_FAIL",
    "WD_MAX_STALE_S",
    "WD_AUTOSAVE_EVERY",
    "SYMBOL",
    "LOT",
    "STEP",
    "BOUNDS_LOW",
    "BOUNDS_HIGH",
]


def _git_info() -> Dict[str, Any]:
    def run(*cmd):
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            return out
        except Exception:
            return None

    if shutil.which("git") is None:
        return {"present": False}
    root = run("git", "rev-parse", "--show-toplevel")
    if not root:
        return {"present": False}
    branch = run("git", "rev-parse", "--abbrev-ref", "HEAD")
    commit = run("git", "rev-parse", "HEAD")
    status = run("git", "status", "--porcelain")
    dirty = bool(status)
    return {"present": True, "root": root, "branch": branch, "commit": commit, "dirty": dirty}


def _env_subset() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k in KEY_ENVS:
        v = os.getenv(k)
        if v is not None:
            out[k] = v
    return out


def _runtime_info() -> Dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "venv": os.getenv("VIRTUAL_ENV"),
        "cwd": str(Path.cwd()),
    }


def _hash_of(obj: Any) -> str:
    b = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(b).hexdigest()


def snapshot(logger=None) -> str:
    """Write a run snapshot JSON and return a short fingerprint string."""
    data = {
        "ts": int(time.time()),
        "env": _env_subset(),
        "runtime": _runtime_info(),
        "git": _git_info(),
    }
    try:
        SNAPSHOT_PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        if logger:
            logger.warning(f"DIAG: failed to write snapshot: {e}")
    fp = _hash_of(data)[:12]
    if logger:
        logger.info(f"DIAG: fingerprint={fp} envs={data['env']}")
        gi = data["git"]
        if cast(Mapping[str, Any], gi).get("present"):
            logger.info(
                f"DIAG: git branch={cast(Mapping[str, Any], gi).get('branch')} commit={cast(Mapping[str, Any], gi).get('commit')}{' (dirty)' if cast(Mapping[str, Any], gi).get('dirty') else ''}"
            )
    else:
        print(f"fingerprint={fp} envs={data['env']}")
    return fp
