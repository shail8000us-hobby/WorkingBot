from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(
    path: os.PathLike[str] | str,
    data: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = True,
    **json_kwargs: Any,
) -> None:
    """
    Atomically write JSON data to the given path.

    Workflow:
        1. Serialize to a temporary file in the same directory.
        2. Flush and fsync to ensure contents hit disk.
        3. Atomically replace the target file.

    Args:
        path: Destination filepath.
        data: JSON-serializable payload.
        indent: Optional indentation for readability (defaults to 2 if provided).
        ensure_ascii: Mirror json.dump behaviour for ASCII escaping (defaults to True).
        json_kwargs: Additional keyword arguments forwarded to json.dump.

    Raises:
        OSError: If filesystem operations fail.
        TypeError: If serialization fails.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd = None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(destination.parent),
            delete=False,
        ) as tmp_file:
            fd = tmp_file.fileno()
            dump_kwargs = dict(json_kwargs)
            if indent is not None:
                dump_kwargs.setdefault("indent", indent)
            if "ensure_ascii" not in dump_kwargs:
                dump_kwargs["ensure_ascii"] = ensure_ascii
            json.dump(data, tmp_file, **dump_kwargs)
            tmp_file.flush()
            os.fsync(fd)
            tmp_path = Path(tmp_file.name)

        os.replace(tmp_path, destination)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
