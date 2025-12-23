# GridBot Bug Finder - Automated Static Analysis

Comprehensive bug detection system for the GridBot trading bot project. Automatically scans Python code for syntax errors, logic issues, security vulnerabilities, and type mismatches.

## Features

- **🔍 Multi-Tool Analysis**: Combines flake8, pylint, mypy, and bandit
- **🎯 Smart Detection**: Finds bugs before runtime
- **🔴 Severity Classification**: Critical, Error, Warning, Info levels
- **📊 Detailed Reports**: Terminal output + text/JSON reports
- **⚡ Fast Mode**: Quick scan option for rapid checks
- **🔒 Security Scanning**: Detects hardcoded secrets, unsafe code patterns

## Installation

```bash
# Install dependencies
pip3 install -r bug_finder_requirements.txt
```

## Usage

### Basic Scan (Full Analysis)
```bash
python3 run_bug_finder.py
```

### Quick Scan (Fast - Flake8 + Pylint only)
```bash
python3 run_bug_finder.py --quick
```

### Export JSON Report (for CI/CD)
```bash
python3 run_bug_finder.py --export-json
```

## What It Checks

### 1. Flake8 - Syntax & Style
- ✅ Syntax errors (E999)
- ✅ Undefined variables (F821)
- ✅ Unused imports (F401)
- ✅ Code style issues (PEP 8)

### 2. Pylint - Logic & Quality
- ✅ Unused variables
- ✅ Unreachable code
- ✅ Logic errors
- ✅ Code complexity
- ✅ Naming conventions

### 3. Mypy - Type Safety
- ✅ Type mismatches
- ✅ Missing type hints
- ✅ Invalid function calls
- ✅ Attribute errors

### 4. Bandit - Security
- ✅ Hardcoded passwords/secrets
- ✅ SQL injection risks
- ✅ Unsafe eval() usage
- ✅ Insecure random usage
- ✅ Path traversal vulnerabilities

## Output Example

```
🔍 GridBot Bug Finder - Automated Static Analysis
================================================================================
📁 Project Root: /Users/user/Projects/WorkingBot
🔧 Mode: Full Scan
⏰ Started: 2025-11-02 18:00:00
================================================================================

📂 bot: 45 Python files
📂 webui/backend: 23 Python files
📂 scripts: 12 Python files

🔎 Running Flake8 (Syntax & Style)...
  ✓ Found 8 issues
🔎 Running Pylint (Logic & Quality)...
  ✓ Found 15 issues
🔎 Running Mypy (Type Checker)...
  ✓ Found 3 issues
🔎 Running Bandit (Security Analyzer)...
  ✓ Found 2 security issues

================================================================================
📊 ANALYSIS RESULTS
================================================================================

🔴 CRITICAL ISSUES (Security/Safety)
--------------------------------------------------------------------------------
  [BANDIT] bot/config/secrets.py:12
    → B105 Possible hardcoded password: 'API_KEY'

❌ ERRORS (Runtime/Logic)
--------------------------------------------------------------------------------
  [FLAKE8] bot/strategy/gridbot.py:124
    → F821 undefined name 'missing_variable'
  [PYLINT] webui/backend/routes/config.py:89
    → E0602 Undefined variable 'old_value'

🟡 WARNINGS
--------------------------------------------------------------------------------
  [PYLINT] webui/backend/routes/config.py:203
    → W0612 Unused variable 'temp_data'
  [MYPY] bot/strategy/modules/order_manager.py:45
    → Argument 1 has incompatible type "str"; expected "int"

================================================================================
📈 SUMMARY
================================================================================
📁 Total Files Scanned: 80
🔴 Critical Issues: 2
❌ Errors: 12
🟡 Warnings: 25
ℹ️  Info: 8

🚨 Scan Complete — 2 CRITICAL issues found!
================================================================================

📄 Full report written to: /Users/user/Projects/WorkingBot/bug_report.txt
```

## Reports Generated

### bug_report.txt
Detailed text report with all findings, organized by tool and severity.

### bug_report.json (with --export-json)
Machine-readable JSON format for CI/CD integration:
```json
{
  "summary": {
    "total_files": 80,
    "errors": 12,
    "warnings": 25,
    "critical": 2,
    "info": 8,
    "timestamp": "2025-11-02T18:00:00"
  },
  "results": {
    "flake8": [...],
    "pylint": [...],
    "mypy": [...],
    "bandit": [...]
  }
}
```

## Git Pre-Commit Integration

Enable automatic checks before each commit:

```bash
# Install pre-commit
pip3 install pre-commit

# Set up hooks
pre-commit install

# Now bug finder runs automatically on git commit
```

## Performance

- **Quick Mode**: ~10-30 seconds (flake8 + pylint only)
- **Full Mode**: ~30-90 seconds (all 4 tools)
- **Files Scanned**: All .py files in bot/, webui/backend/, scripts/, dashboard/

## Exit Codes

- `0`: No critical issues (warnings are OK)
- `1`: Critical security or runtime issues found

## Integration with CI/CD

```yaml
# GitHub Actions example
- name: Run Bug Finder
  run: |
    pip3 install -r bug_finder_requirements.txt
    python3 run_bug_finder.py --export-json
    
- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: bug-report
    path: bug_report.json
```

## Customization

Edit `run_bug_finder.py` to:
- Add/remove scan directories (SCAN_DIRS)
- Modify tool configurations
- Adjust severity thresholds
- Change ignore patterns

## Troubleshooting

### Tool Not Found
```bash
# Install missing tool
pip3 install flake8 pylint mypy bandit termcolor
```

### False Positives
Edit the tool configurations in `run_bug_finder.py`:
- Flake8: `--ignore` parameter
- Pylint: `--disable` parameter
- Bandit: `--skip` parameter

### Too Many Warnings
Use `--quick` mode to focus on critical issues only.

## License

Part of the GridBot trading bot project.
