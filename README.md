# Foundry Audit Readiness

> Automated quality gates for Solidity smart contracts. Prepare your code for
> professional audit in minutes, not days.

[![CI](https://github.com/mailtkarim-bot/foundry-audit-readiness/actions/workflows/audit-readiness.yml/badge.svg)](https://github.com/mailtkarim-bot/foundry-audit-readiness/actions/workflows/audit-readiness.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What This Does

`foundry-audit-readiness` is a **Foundry-native quality suite** that combines
static analysis, test coverage, invariant validation, and compliance checks into
a single, unified report.

Professional smart contract audits cost **$10,000-$50,000** and take 2-4 weeks.
Auditors often reject code that:
- Has <90% test coverage
- Lacks NatSpec documentation on public functions
- Contains compiler warnings
- Fails basic static analysis

This tool ensures your codebase passes the **entry gates** before you pay for an
audit -- saving time, money, and back-and-forth with the audit team.

> **Disclaimer:** This tool does **NOT** replace a professional security audit.
> It prepares your code so the real audit is faster, cheaper, and more
> effective. Always engage a certified audit firm before deploying to production.

---

## Checks Performed

| Check | Tool | Purpose | Blocking |
|-------|------|---------|----------|
| **Static Analysis** | Slither (+ optional Aderyn) | Detect reentrancy, unchecked calls, access control issues | Yes |
| **Test Coverage** | `forge coverage` | Line, branch, and function coverage thresholds | Yes |
| **NatSpec Compliance** | `solc` AST + regex fallback | Ensure public/external functions are documented | Yes |
| **Compiler Warnings** | `forge build` | Zero-tolerance for warnings in audit-ready code | Yes |
| **Gas Snapshots** | `forge snapshot` | Track gas regression across PRs | No (info only) |
| **Invariant Tests** | `forge test` | Property-based fuzz tests (optional) | No (configurable) |

---

## Quick Start

### Prerequisites

- Python 3.10+
- [Foundry](https://book.getfoundry.sh/getting-started/installation) (`forge`, `cast`, `anvil`)
- [Slither](https://github.com/crytic/slither) (optional): `pip install slither-analyzer`
- [Aderyn](https://github.com/Cyfrin/aderyn) (optional): download prebuilt binary from
  [GitHub Releases](https://github.com/Cyfrin/aderyn/releases)

### Installation

```bash
git clone https://github.com/mailtkarim-bot/foundry-audit-readiness.git
cd foundry-audit-readiness
pip install -r requirements.txt
```

### Usage

```bash
# Full audit readiness check (Markdown output)
python -m audit_readiness --target /path/to/your/foundry/project --output report.md

# Self-contained HTML report with "Save as PDF" button
python -m audit_readiness --target /path/to/your/foundry/project --output report.html --format html

# Run specific checks only
python -m audit_readiness --target ./my-project --checks coverage,invariants,natspec

# Fail CI if thresholds are not met
python -m audit_readiness --target . --fail-on-threshold
```

**Output Example (Markdown):**

```markdown
# AUDIT READINESS REPORT - my-foundry-project

## 1. STATIC ANALYSIS
### Slither
- Slither: 0 critical, 0 high, 2 medium, 4 low

## 2. TEST COVERAGE
| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Line Coverage | 96.4% | 90% | PASS |
| Branch Coverage | 91.2% | 85% | PASS |
| Function Coverage | 100.0% | 100% | PASS |

## 3. INVARIANT TESTS
- Invariant functions detected: 6
- All passing: True
- Fuzz runs: 10000

## 4. CODE QUALITY

### NatDoc / NatSpec
- **Public:** 12/12 documented
- **External:** 48/48 documented
- **Method:** ast

### Compiler Warnings
- **Status:** No warnings detected

### Gas Snapshots
- **Baseline exists:** 34 functions tracked

## 5. SUMMARY
# STATUS: READY FOR PROFESSIONAL AUDIT
Estimated audit time reduction: 30-40%
```

---

## Configuration

Create `audit-readiness.yaml` in your target project root to override defaults:

```yaml
# audit-readiness.yaml
coverage:
  line: 95
  branch: 85
  function: 100

invariants:
  min_functions: 0        # 0 = optional (default), set >0 to enforce
  runs: 10000

static_analysis:
  tools: [slither]        # add aderyn here if installed
  ignore_paths: ["lib/", "test/", "script/", "node_modules/"]

natspec:
  require_public: true
  require_external: true

gas:
  compare_with_baseline: true
  max_increase_percent: 5
```

---

## CI/CD Integration (GitHub Actions)

Add `.github/workflows/audit-readiness.yml` to your target repo:

```yaml
name: Audit Readiness Check

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  audit-readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Foundry
        uses: foundry-rs/foundry-toolchain@v1
        with:
          version: nightly

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install Python dependencies
        run: |
          pip install -r requirements.txt
          pip install slither-analyzer

      - name: Run Audit Readiness
        run: |
          python -m audit_readiness --target . --output audit-report.html --format html

      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: audit-readiness-report
          path: audit-report.html

      - name: Check Thresholds
        run: |
          python -m audit_readiness --target . --fail-on-threshold
```

**CI Time:** ~30-60 seconds (Slither via pip, no heavy system dependencies).

---

## Project Structure

```
foundry-audit-readiness/
├── .github/
│   └── workflows/
│       └── audit-readiness.yml       # Example CI workflow
├── audit_readiness/
│   ├── __init__.py                   # Version & metadata
│   ├── __main__.py                   # CLI entry point (click)
│   ├── config.py                     # Thresholds & YAML parsing
│   ├── scanner.py                    # Slither + Aderyn wrappers
│   ├── parser.py                     # Forge coverage / test / gas parsers
│   ├── natspec.py                    # NatSpec completeness (AST + regex fallback)
│   ├── reporter.py                   # Markdown + HTML report generator
│   └── utils.py                      # Helpers, logging, subprocess wrappers
├── tests/
│   ├── test_parser.py
│   ├── test_natspec.py
│   └── fixtures/
│       └── sample_project/           # Mini Foundry project for tests
├── examples/
│   └── dreit_report_sample.md        # Sample report from DREIT project
├── requirements.txt
├── README.md
└── LICENSE
```

---

## Why No PDF?

We intentionally **do not use WeasyPrint** or other heavy PDF libraries. They require
system-level dependencies (Pango, GTK+, Cairo) that break in CI and bloat
installation.

Instead, we generate **self-contained HTML** with inline CSS and a `window.print()`
button. Open the file in any browser, click "Save as PDF", and you get a clean,
printable document without installing 200MB of system libraries.

---

## Real-World Validation

The tool was validated against the [Dubai Real Estate Investment Token (DREIT)](https://github.com/mailtkarim-bot/Dubai-Real-Estate-Token-V3) Foundry project and the codebase is now marked as **READY FOR PROFESSIONAL AUDIT**:

- Static analysis (Slither): **0 critical / 0 high / 0 medium / 0 low**
- Line coverage: **99.4%** / Branch coverage: **95.1%** / Function coverage: **100%**
- Invariant tests: **6/6** passing
- NatSpec: **2/2 public** and **117/117 external** functions documented
- Compiler warnings: **None** in source contracts

DREIT references this tool in its README and uses it as an automated quality gate before engaging an external auditor.

See [`examples/dreit_report_sample.md`](examples/dreit_report_sample.md) for a sample generated report.

---

## Roadmap

- [x] Core pipeline: Slither + Forge coverage + NatSpec
- [x] Markdown & HTML reporting
- [x] GitHub Actions integration
- [x] Configurable thresholds via YAML
- [x] Robust terminal-table coverage parser (no JSON dependency)
- [ ] Semgrep rule integration for ERC compliance
- [ ] Gas diff visualization
- [ ] VS Code extension
- [ ] SARIF output for GitHub Advanced Security

---

## About

Built by a developer who learned Solidity by building a RWA real estate
tokenization project and realized that 90% of audit prep is repetitive
automation. This tool captures that automation so teams can focus on logic,
not boilerplate.

**Positioning:** This is an **audit preparation** tool, not a security audit.
It helps teams meet the quality bar before engaging a professional firm. It does
not find all bugs, guarantee safety, or replace human expertise.

---

## License

MIT - see [LICENSE](LICENSE)
