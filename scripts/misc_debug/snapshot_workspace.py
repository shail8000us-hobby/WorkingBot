#!/usr/bin/env python3
"""
Snapshot the current VS Code workspace:
- TREE.txt: directory tree
- workspace_manifest.json: per-file metadata (path, size, mtime, sha256, preview)
- workspace_manifest.md: human-friendly report you can paste back to me
Run it from VS Code: Run & Debug → "Snapshot: Workspace".
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import pathlib
import sys
from typing import Any, Dict, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Folders/files to ignore (safe defaults)
IGNORE_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "venv", ".venv", ".idea", ".vscode", ".DS_Store", "node_modules"}
IGNORE_FILE_PREFIXES = {".DS_Store"}

# Extensions treated as text for previews
TEXT_EXTS = {".py", ".sh", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".csv", ".tsv", ".env", ".gitignore"}

# Preview limits
MAX_PREVIEW_BYTES = 32_000  # ~32 KB of text preview per file
MAX_FILES_PREVIEW = 500  # cap previews to avoid huge reports


def is_ignored_dir(name: str) -> bool:
    return name in IGNORE_DIRS


def is_text_file(path: pathlib.Path) -> bool:
    if path.suffix.lower() in TEXT_EXTS:
        return True
    # Heuristic for shell scripts without extension
    if path.name.endswith(".zsh") or path.name.endswith(".bash"):
        return True
    return False


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def preview_text(path: pathlib.Path, max_bytes: int = MAX_PREVIEW_BYTES) -> str:
    try:
        raw = path.read_bytes()[:max_bytes]
        # Try utf-8, fall back to latin-1
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = raw.decode("latin-1", errors="replace")
        return text
    except Exception as e:
        return f"<<preview error: {e}>>"


def walk_tree(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for base, dirs, files in os.walk(root):
        # prune ignored directories in-place
        dirs[:] = [d for d in dirs if not is_ignored_dir(d)]
        for f in files:
            if any(f.startswith(pfx) for pfx in IGNORE_FILE_PREFIXES):
                continue
            yield pathlib.Path(base) / f


def make_tree_text(root: pathlib.Path) -> str:
    # Quick, deterministic tree (alphabetical)
    lines = []
    for p in sorted(walk_tree(root)):
        rel = p.relative_to(root)
        lines.append(str(rel))
    return "\n".join(lines) + ("\n" if lines else "")


def summarize_extensions(paths: Iterable[pathlib.Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in paths:
        ext = p.suffix.lower() or "<noext>"
        counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def main() -> int:
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    files = list(walk_tree(ROOT))
    total_files = len(files)
    ext_counts = summarize_extensions(files)

    # Write TREE.txt
    tree_txt = make_tree_text(ROOT)
    (ROOT / "TREE.txt").write_text(tree_txt, encoding="utf-8")

    manifest = {"root": str(ROOT), "timestamp": ts, "total_files": total_files, "extension_counts": ext_counts, "files": []}

    # Build per-file records
    previews_done = 0
    for p in sorted(files):
        try:
            stat = p.stat()
            rec: Dict[str, Any] = {
                "path": str(p.relative_to(ROOT)),
                "size": stat.st_size,
                "mtime": datetime.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                "sha256": sha256_file(p),
            }
            if is_text_file(p) and previews_done < MAX_FILES_PREVIEW:
                rec["preview"] = preview_text(p)
                previews_done += 1
            manifest["files"].append(rec)
        except Exception as e:
            manifest["files"].append({"path": str(p.relative_to(ROOT)), "error": f"{e}"})

    # Write JSON
    (ROOT / "workspace_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Write MD summary
    md = io.StringIO()
    md.write("# Workspace Snapshot\n\n")
    md.write(f"- Root: `{ROOT}`\n")
    md.write(f"- Captured at: `{ts}`\n")
    md.write(f"- Total files (excluding caches/venv): **{total_files}**\n\n")
    md.write("## File types\n\n")
    for ext, n in ext_counts.items():
        md.write(f"- `{ext}`: {n}\n")
    md.write("\n## Tree (flat)\n\n")
    md.write("```\n")
    md.write(tree_txt[:100_000])  # keep it readable
    md.write("```\n")

    md.write("\n## Previews (first ~32KB of selected text files)\n\n")
    shown = 0
    for rec in manifest["files"]:
        if "preview" in rec:
            md.write(f"### {rec['path']}\n\n")
            md.write("```text\n")
            md.write(rec["preview"])
            md.write("\n```\n\n")
            shown += 1
            if shown >= 50:  # cap in MD to keep it pasteable
                md.write("_…truncated; more previews are in `workspace_manifest.json`…_\n")
                break

    (ROOT / "workspace_manifest.md").write_text(md.getvalue(), encoding="utf-8")

    print("✅ Snapshot complete:")
    print(" - TREE.txt")
    print(" - workspace_manifest.json")
    print(" - workspace_manifest.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
