from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# ---------- utils ----------


def run_pytool(module: str, args: List[str]) -> Tuple[int, str, str]:
    """Run a Python module from the current venv, capture output."""
    proc = subprocess.run(
        [sys.executable, "-m", module, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def run_cmd(argv: List[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def color(txt: str, c: str) -> str:
    if not sys.stdout.isatty():
        return txt
    codes = {"grn": "\033[32m", "red": "\033[31m", "yel": "\033[33m", "cya": "\033[36m", "dim": "\033[2m", "clr": "\033[0m"}
    return f"{codes.get(c, '')}{txt}{codes['clr']}"


def section(title: str) -> None:
    print("\n" + color(f"=== {title} ===", "cya"))


# ---------- checks ----------


def check_ruff() -> bool:
    section("Ruff (imports/errors)")
    try:
        rc, out, err = run_pytool("ruff", ["check", ".", "--select", "I,E,F", "--fix"])
    except Exception as e:
        print(color(f"ruff failed to run: {e}", "red"))
        return False
    if out:
        print(out)
    if err:
        print(err)
    ok = rc == 0
    print(color("Ruff: OK" if ok else "Ruff: issues found", "grn" if ok else "yel"))
    # format (non-fatal)
    _, out2, err2 = run_pytool("ruff", ["format", "."])
    if out2:
        print(out2)
    if err2:
        print(err2)
    return ok


def check_mypy() -> bool:
    section("mypy (types)")
    try:
        rc, out, err = run_pytool("mypy", ["bot"])
    except Exception as e:
        print(color(f"mypy failed to run: {e}", "red"))
        return False
    if out:
        print(out)
    if err:
        print(err)
    ok = rc == 0
    print(color("mypy: OK" if ok else "mypy: type errors", "grn" if ok else "yel"))
    return ok


def check_pytest() -> bool:
    section("pytest (tests)")
    try:
        rc, out, err = run_pytool("pytest", ["-q"])
    except Exception as e:
        print(color(f"pytest failed to run: {e}", "red"))
        return False
    if out:
        print(out)
    if err:
        print(err)
    ok = rc == 0
    print(color("pytest: OK" if ok else "pytest: failures", "grn" if ok else "red"))
    return ok


def snapshot_workspace() -> None:
    section("Workspace snapshot")
    root = Path(".").resolve()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_path = Path("workspace_snapshot.md")
    # Prefer git ls-files for cleaner list; fallback to os.walk
    try:
        rc, out, _ = run_cmd(["git", "ls-files"])
        files = out.splitlines() if rc == 0 else []
    except Exception:
        files = []
    if not files:
        files = []
        for r, _, fs in os.walk("."):
            for f in fs:
                files.append(os.path.join(r, f))
        files.sort()
    with md_path.open("w", encoding="utf-8") as md:
        md.write("# Workspace Snapshot\n\n")
        md.write(f"- Root: `{root}`\n")
        md.write(f"- Captured at: `{ts}`\n\n")
        md.write("## Files\n")
        for p in files[:3000]:
            md.write(f"- {p}\n")
        if len(files) > 3000:
            md.write(f"- ... ({len(files) - 3000} more)\n")
    print(color(f"Snapshot written to {md_path}", "grn"))


def main() -> None:
    print(color(f"Python: {sys.executable}", "dim"))
    print(color(f"Version: {sys.version.split()[0]}", "dim"))
    print(color(f"CWD: {Path.cwd()}", "dim"))

    ok1 = check_ruff()
    ok2 = check_mypy()
    ok3 = check_pytest()
    snapshot_workspace()

    all_ok = ok1 and ok2 and ok3
    print(color("\nHealth: OK" if all_ok else "\nHealth: issues detected", "grn" if all_ok else "yel"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
