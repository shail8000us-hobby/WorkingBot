#!/usr/bin/env python3
"""
List all files in the workspace with paths relative to the project root.
Ignores venv, cache folders, and hidden git files.
"""

import os
import pathlib

# Project root = one level above 'scripts'
ROOT = pathlib.Path(__file__).resolve().parents[1]

IGNORE_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "venv", ".venv", ".idea", ".vscode", "node_modules"}


def walk(root: pathlib.Path):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            yield pathlib.Path(base) / f


def main():
    print(f"📂 Project root: {ROOT}\n")
    for path in sorted(walk(ROOT)):
        rel = path.relative_to(ROOT)
        print(rel)


if __name__ == "__main__":
    main()
