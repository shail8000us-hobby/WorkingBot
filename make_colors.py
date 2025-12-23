from pathlib import Path

# Path to new utils/colors.py
path = Path("bot/utils/colors.py")
path.parent.mkdir(parents=True, exist_ok=True)

code = '''"""
Color utilities for terminal logs.
ANSI escape codes wrapped into simple functions.
"""

def _c(code: str, s: str, enable: bool = True) -> str:
    if not enable:
        return s
    return f"\\x1b[{code}m{s}\\x1b[0m"

# Standard colors
def C_GRAY(s, enable=True): return _c("90", s, enable)
def C_GREEN(s, enable=True): return _c("92", s, enable)
def C_RED(s, enable=True): return _c("91", s, enable)
def C_CYAN(s, enable=True): return _c("96", s, enable)
def C_BOLD(s, enable=True): return _c("1", s, enable)
def C_ORANGE(s, enable=True): return _c("33", s, enable)   # ANSI yellow/orange
'''

# Write file
path.write_text(code)
print(f"✓ Created {path}")
