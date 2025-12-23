#!/usr/bin/env python3
"""
make_sync_pack.py
Creates a 'sync_pack/' folder at project root containing:
- SUMMARY.md      → overview + tree + paste instructions
- TREE.txt        → full flat tree of files
- CHUNKS/*.md     → the full text of each source file, split into paste-sized chunks

Paste SUMMARY.md here first, then paste CHUNKS in the order listed.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import pathlib
from typing import Any, Dict, Iterable

# This script lives in scripts/misc_debug/, so root is two levels up
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "sync_pack"
CHUNKS = OUT / "CHUNKS"

# Ignore noisy/cache folders
IGNORE_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "venv", ".venv", ".idea", ".DS_Store", "node_modules"}
IGNORE_FILES_PREFIX = {".DS_Store"}

# Treat these as text files we should include fully
TEXT_EXTS = {".py", ".sh", ".zsh", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".csv", ".tsv", ".env", ".gitignore", ".pyi", ".lock", ".cfg", ".rst"}

# Safety limits
# ~60k chars per Markdown chunk file (chat-friendly)
MAX_CHARS_PER_CHUNK = 60000
MAX_TOTAL_FILES = 10000  # guardrail
MAX_TOTAL_CHUNKS = 500  # guardrail


def is_text_file(p: pathlib.Path) -> bool:
    # by extension first
    if p.suffix.lower() in TEXT_EXTS:
        return True
    # treat shell files without ext
    if p.name.endswith(".bash") or p.name.endswith(".zsh"):
        return True
    return False


def walk_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for base, dirs, files in os.walk(root):
        # prune
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if any(f.startswith(pfx) for pfx in IGNORE_FILES_PREFIX):
                continue
            yield pathlib.Path(base) / f


def rel(p: pathlib.Path) -> str:
    return str(p.relative_to(ROOT))


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text_file(p: pathlib.Path) -> str:
    # Read as text with safe fallback; we only call this for "text" files
    raw = p.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def make_tree_text(paths: list[pathlib.Path]) -> str:
    lines = [rel(p) for p in sorted(paths)]
    return "\n".join(lines) + ("\n" if lines else "")


def ext_counts(paths: list[pathlib.Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in paths:
        e = p.suffix.lower() or "<noext>"
        counts[e] = counts.get(e, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def sanitize_for_filename(s: str) -> str:
    # replace slashes and unpleasant chars
    return s.replace("/", "__").replace("\\", "__").replace(" ", "_")


def chunk_and_write(path: pathlib.Path, text: str, chunks_dir: pathlib.Path) -> list[str]:
    chunk_files: list[str] = []
    total = len(text)
    if total == 0:
        name = sanitize_for_filename(rel(path)) + "__part1.md"
        out = chunks_dir / name
        out.write_text(f"## {rel(path)} (empty file)\n\n", encoding="utf-8")
        return [str(out.relative_to(OUT))]
    parts = (total + MAX_CHARS_PER_CHUNK - 1) // MAX_CHARS_PER_CHUNK
    base = sanitize_for_filename(rel(path))
    for i in range(parts):
        start = i * MAX_CHARS_PER_CHUNK
        end = min(total, (i + 1) * MAX_CHARS_PER_CHUNK)
        name = f"{base}__part{i + 1:02d}.md" if parts > 1 else f"{base}.md"
        out = chunks_dir / name
        out.write_text(f"## {rel(path)} (part {i + 1}/{parts})\n\n```text\n{text[start:end]}\n```\n", encoding="utf-8")
        chunk_files.append(str(out.relative_to(OUT)))
    return chunk_files


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    CHUNKS.mkdir(parents=True, exist_ok=True)

    all_paths = list(walk_files(ROOT))
    # avoid including previous sync_pack
    all_paths = [p for p in all_paths if OUT not in p.parents]
    if len(all_paths) > MAX_TOTAL_FILES:
        print(f"⚠️ Too many files ({len(all_paths)}). Consider pruning or adjusting limits.")
    # write TREE.txt (flat)
    tree_txt = make_tree_text(all_paths)
    (OUT / "TREE.txt").write_text(tree_txt, encoding="utf-8")

    # manifest with metadata
    manifest: Dict[str, Any] = {
        "root": str(ROOT),
        "captured_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "total_files": len(all_paths),
        "extension_counts": ext_counts(all_paths),
        "files": [],
    }

    paste_order: list[str] = []
    total_chunks = 0

    for p in sorted(all_paths):
        rec: Dict[str, Any] = {
            "path": rel(p),
            "size": p.stat().st_size,
            "mtime": datetime.datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
            "sha256": sha256_file(p),
        }
        if is_text_file(p):
            try:
                text = read_text_file(p)
                chunk_files = chunk_and_write(p, text, CHUNKS)
                rec["chunks"] = chunk_files
                paste_order.extend(chunk_files)
                total_chunks += len(chunk_files)
                if total_chunks >= MAX_TOTAL_CHUNKS:
                    rec["truncated"] = True
                    break
            except Exception as e:
                rec["error"] = f"read/chunk error: {e}"
        else:
            rec["skipped"] = "non-text"
        manifest["files"].append(rec)

    (OUT / "INDEX.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # SUMMARY.md with instructions + counts
    md = io.StringIO()
    md.write("# Sync Pack Summary\n\n")
    md.write(f"- Root: `{ROOT}`\n")
    md.write(f"- Captured: `{manifest['captured_at']}`\n")
    md.write(f"- Total files scanned: **{manifest['total_files']}**\n")
    md.write(f"- Total chunk files created: **{total_chunks}**\n\n")

    md.write("## File type counts\n\n")
    for ext, n in manifest["extension_counts"].items():
        md.write(f"- `{ext}`: {n}\n")
    md.write("\n## Flat tree (all files)\n\n```\n")
    md.write(tree_txt[:100_000])
    md.write("\n```\n")

    md.write("\n## Paste Instructions\n")
    md.write("1. Paste this `SUMMARY.md` here first.\n")
    md.write("2. Then paste each of the following chunk files, in order:\n\n")
    for c in paste_order:
        md.write(f"- `CHUNKS/{c.split('CHUNKS/')[1] if 'CHUNKS/' in c else c}`\n")
    md.write("\n_If the list is long, paste them across multiple messages._\n")

    (OUT / "SUMMARY.md").write_text(md.getvalue(), encoding="utf-8")

    print("✅ Sync pack created:")
    print(f" - {OUT / 'SUMMARY.md'}")
    print(f" - {OUT / 'TREE.txt'}")
    print(f" - {OUT / 'INDEX.json'}")
    print(f" - {CHUNKS} (contains the code chunks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
