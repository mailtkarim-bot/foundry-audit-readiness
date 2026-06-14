# Foundry Audit Readiness

<div align="center">

**One command. Seven security tools. A single professional report.**

[![CI](https://github.com/mailtkarim-bot/foundry-audit-readiness/actions/workflows/audit-readiness.yml/badge.svg)](https://github.com/mailtkarim-bot/foundry-audit-readiness/actions/workflows/audit-readiness.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Foundry](https://img.shields.io/badge/Foundry-compatible-00B4D8?logo=ethereum&logoColor=white)]()
[![Version](https://img.shields.io/badge/version-2.0.0-gold)]()
[![Tools](https://img.shields.io/badge/security%20tools-7-success)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## Overview

`foundry-audit-readiness` is a **multi-tool security orchestrator** for Solidity smart contracts. It runs **7 free, open-source security tools** in a single command and produces a unified, professional audit-readiness report in Markdown or HTML.

### The 7 Tools

| # | Tool | Type | What It Finds | Install |
|---|------|------|--------------|---------|
| 1 | **Slither** | Static Analysis | Reentrancy, unchecked calls, access control | `pip install slither-analyzer` |
| 2 | **Aderyn** | Static Analysis | Rust-based fast detector from Cyfrin | [Prebuilt binary](https://github.com/Cyfrin/aderyn/releases) |
| 3 | **Solhint** | Linter | Style violations & basic security patterns | `npm install -g solhint` |
| 4 | **Semgrep** | Rule Engine | Community security rules for Solidity | `pip install semgrep` |
| 5 | **Mythril** | Symbolic Execution | Complex multi-transaction bugs | `pip install mythril` |
| 6 | **Halmos** | Formal Verification | Mathematical correctness proofs | `pip install halmos` |
| 7 | **SMTChecker** | SMT Verification | Assertion & overflow checks via `solc` | Bundled with Foundry |

**Plus:**
- `forge coverage` — Line, branch & function coverage
- `forge build` — Compiler warnings detection
- `forge snapshot` — Gas regression tracking
- NatSpec completeness validator
- Invariant test detector

---

## Why 7 Tools?

Professional audits cost **$10,000-$50,000**. Auditors reject code that fails basic quality gates. Each tool above catches bugs the others miss:

| Technique | Strengths | Limitations |
|-----------|-----------|-------------|
| **Slither / Aderyn** | Fast, comprehensive pattern matching | Misses state-dependent bugs |
| **Solhint** | Style & best-practice enforcement | Only surface-level checks |
| **Semgrep** | Community rules, CI-friendly | Rule-dependent coverage |
| **Mythril** | Multi-transaction path exploration | Very slow (up to 10 min) |
| **Halmos** | Mathematical soundness proofs | Requires `halmos`-annotated tests |
| **SMTChecker** | Deep assertion verification | Can timeout on complex code |

**Result:** Running all 7 gives you coverage across the entire detection spectrum -- from fast linters to deep formal verification -- without paying a cent.

---

## Quick Start

### Prerequisites

| Dependency | Version | Install |
|------------|---------|---------|
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) |
| Foundry | latest | [getfoundry.sh](https://book.getfoundry.sh/getting-started/installation) |
| Slither | latest | `pip install slither-analyzer` |
| (optional) Aderyn | latest | [GitHub Releases](https://github.com/Cyfrin/aderyn/releases) |
| (optional) Solhint | latest | `npm install -g solhint` |
| (optional) Semgrep | latest | `pip install semgrep` |
| (optional) Mythril | latest | `pip install mythril` |
| (optional) Halmos | latest | `pip install halmos` |

Tools that are not installed are **gracefully skipped** -- the pipeline never breaks.

### Install

```bash
git clone https://github.com/mailtkarim-bot/foundry-audit-readiness.git
cd foundry-audit-readiness
pip install -r requirements.txt
pip install -e .
```

### Run

After installation, the `audit-readiness` command is available globally:

```bash
# Full check with all 7 tools → generates report.md + report.html
audit-readiness --target /path/to/foundry/project --output report

# Fast check (3 tools only)
audit-readiness --target . --tools slither,solhint,semgrep --output report

# Force only HTML
audit-readiness --target . --output report --format html

# Force only Markdown
audit-readiness --target . --output report --format markdown

# CI mode: fail on thresholds
audit-readiness --target . --fail-on-threshold

# Specific checks only
audit-readiness --target . --checks coverage,natspec,static
```

### One-Command Wrappers (Optional)

For even shorter commands, install the bundled shell wrappers:

```bash
./scripts/install.sh
```

Then, in any Foundry project:

```bash
readiness          # fast mode: Slither + Solhint + Semgrep (~2-3 min)
readiness-full     # full mode: all 7 tools (~10-15 min)
```

Both commands accept an optional project path:

```bash
readiness /path/to/foundry/project
readiness-full /path/to/foundry/project
```

---

## Output

By default, the tool generates **both** `report.md` and `report.html` from the same analysis. Use `--format` to override.

### HTML Report (Recommended)

Self-contained dark-themed HTML with:
- **Tool Coverage Summary** -- status of all 7 tools at a glance
- **Detailed Findings** per tool with severity, file, line, message
- **Test Coverage** table with thresholds
- **NatSpec Compliance** with missing documentation list
- **Compiler Warnings** with full context
- **"Save as PDF"** button -- no external dependencies

### Markdown Report

```markdown
# AUDIT READINESS REPORT - my-project
> Foundry Audit Readiness v2.0.0 -- 7 Security Tools

## 1. STATIC ANALYSIS SUITE (7 Tools)

### SLITHER
- Findings: 0 critical | 0 high | 2 medium | 4 low | 0 info
- Status: PASS

### SOLHINT
- Findings: 0 critical | 0 high | 1 medium | 0 low | 0 info
- Status: PASS

### MYTHRIL
- [SKIPPED] myth not found. Install: pip install mythril

### ... (one section per tool)

## 5. TOOL COVERAGE SUMMARY

| # | Tool | Type | Status |
|---|------|------|--------|
| 1 | Slither | Static Analysis | PASS |
| 2 | Aderyn | Static Analysis | N/A |
| 3 | Solhint | Linter | PASS |
| 4 | Semgrep | Rule Engine | N/A |
| 5 | Mythril | Symbolic Execution | N/A |
| 6 | Halmos | Formal Verification | N/A |
| 7 | SMTChecker | SMT Verification | PASS |

## 6. FINAL VERDICT
# STATUS: READY FOR PROFESSIONAL AUDIT
```

---

## Configuration

Create `audit-readiness.yaml` in your project root:

```yaml
# Quality thresholds
coverage:
  line: 95
  branch: 85
  function: 100

# Invariant requirements
invariants:
  min_functions: 0        # 0 = optional (default)
  runs: 10000

# Static analysis tools (subset for CI speed)
static_analysis:
  tools: [slither, solhint, semgrep]   # all 7: [slither, aderyn, solhint, semgrep, mythril, halmos, smtchecker]
  ignore_paths: ["lib/", "test/", "script/", "node_modules/"]
  timeouts:
    slither: 300
    aderyn: 120
    solhint: 60
    semgrep: 120
    mythril: 600
    halmos: 300
    smtchecker: 180

# Documentation
natspec:
  require_public: true
  require_external: true

# Gas tracking
gas:
  compare_with_baseline: true
  max_increase_percent: 5
```

---

## CI/CD Integration

### GitHub Actions (Fast Mode -- 3 tools, ~2 min)

```yaml
name: Audit Readiness

on:
  pull_request:
    branches: [main, develop]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Foundry
        uses: foundry-rs/foundry-toolchain@v1

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install tools
        run: |
          pip install slither-analyzer
          npm install -g solhint
          pip install semgrep

      - name: Run Audit Readiness (fast: 3 tools)
        run: |
          python -m audit_readiness \
            --target . \
            --output audit-report.html \
            --format html \
            --tools slither,solhint,semgrep

      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: audit-readiness-report
          path: audit-report.html

      - name: Check Thresholds
        run: python -m audit_readiness --target . --tools slither,solhint,semgrep --fail-on-threshold
```

### GitHub Actions (Full Mode -- 7 tools, ~15 min)

For deep pre-audit checks before engaging an auditor:

```yaml
      - name: Install all 7 tools
        run: |
          pip install slither-analyzer mythril halmos semgrep
          npm install -g solhint
          # Aderyn: download prebuilt binary
          curl -L https://github.com/Cyfrin/aderyn/releases/latest/download/aderyn-x86_64-unknown-linux-gnu.tar.gz | tar xz
          sudo mv aderyn /usr/local/bin/

      - name: Run Full Audit Suite (7 tools)
        run: |
          python -m audit_readiness \
            --target . \
            --output full-audit-report.html \
            --format html
```

---

## Project Structure

```
foundry-audit-readiness/
├── audit_readiness/
│   ├── __init__.py          # v2.0.0 -- 7 tools
│   ├── __main__.py          # CLI entry point (click)
│   ├── config.py            # Thresholds, YAML, timeouts per tool
│   ├── scanner.py           # 7 tool wrappers (504 lines)
│   ├── parser.py            # Forge coverage / test / gas / invariants
│   ├── natspec.py           # NatSpec completeness checker
│   ├── reporter.py          # Markdown + dark-theme HTML generator
│   └── utils.py             # Logging, subprocess, file discovery
├── tests/
│   ├── test_parser.py
│   ├── test_natspec.py
│   └── fixtures/
│       └── sample_project/  # Mini Foundry project for tests
├── examples/
│   └── dreit_report_sample.md
├── .github/workflows/
│   ├── audit-readiness.yml  # Example CI workflow
│   └── ci.yml               # Self-test workflow
├── requirements.txt
├── README.md
├── LICENSE
└── audit-readiness.yaml     # Example configuration
```

---

## Tool Details

### Slither (Trail of Bits)
The industry-standard static analyzer. Detects 80+ vulnerability patterns including reentrancy, unchecked external calls, and access control issues.

```bash
pip install slither-analyzer
```

### Aderyn (Cyfrin)
Fast Rust-based alternative to Slither. Lighter, quicker scans with different detection heuristics. Good as a second opinion.

```bash
# Download prebuilt binary from GitHub releases
curl -L https://github.com/Cyfrin/aderyn/releases/latest/download/aderyn-$(uname -m)-apple-darwin.tar.gz | tar xz
```

### Solhint
Solidity linter enforcing style guides and basic security patterns. Catches naming conventions, visibility issues, and deprecated syntax.

```bash
npm install -g solhint
```

### Semgrep
Open-source rule engine running community-contributed Solidity security rules. Great for ERC compliance checks and custom rule sets.

```bash
pip install semgrep
```

### Mythril
Symbolic execution engine that explores multi-transaction code paths. Finds deep bugs that static analyzers miss -- but can take 5-10 minutes per contract.

```bash
pip install mythril
```

### Halmos
Formal verification tool that mathematically proves correctness properties. Requires `halmos` annotations in your test files. Most powerful but requires setup.

```bash
pip install halmos
```

### SMTChecker
Built into the Solidity compiler (`solc`). Checks assertions, overflow/underflow, and unreachable code using SMT solvers. No extra install needed if you have Foundry.

---

## Performance

| Mode | Tools | Typical Duration | Use Case |
|------|-------|-----------------|----------|
| **Fast** | Slither + Solhint + Semgrep | 1-3 min | CI on every PR |
| **Standard** | + Aderyn | 2-4 min | Pre-commit check |
| **Deep** | + Mythril + SMTChecker | 8-15 min | Before audit engagement |
| **Full** | + Halmos | 10-20 min | Maximum assurance |

---

## Real-World Validation

Validated against the [Dubai Real Estate Investment Token (DREIT)](https://github.com/mailtkarim-bot/Dubai-Real-Estate-Token-V3):

| Check | Result |
|-------|--------|
| Slither | 0 critical / 0 high / 0 medium / 0 low |
| Coverage | 99.4% line / 92.8% branch / 100% function |
| Invariants | 6/6 passing |
| NatSpec | 100% public + 100% external documented |
| Warnings | None in source contracts |

See [`examples/dreit_report_sample.md`](examples/dreit_report_sample.md) for the full report.

---

## Why No PDF?

We generate **self-contained HTML** with a `window.print()` button. Open in any browser, click "Save as PDF" -- zero external dependencies. No WeasyPrint, no Pango, no Cairo, no 200MB of system libraries that break in CI.

---

## Roadmap

- [x] Slither + Aderyn static analysis
- [x] Solhint linter integration
- [x] Semgrep rule engine
- [x] Mythril symbolic execution
- [x] Halmos formal verification
- [x] SMTChecker via solc
- [x] Configurable timeouts per tool
- [x] Dark-themed HTML report
- [x] Tool coverage summary table
- [x] `--tools` CLI override
- [x] Graceful handling of missing tools
- [ ] SARIF output for GitHub Advanced Security
- [ ] Gas diff visualization
- [ ] VS Code extension
- [ ] Historical report comparison

---

## About

Built by a Solidity developer who realized that 90% of audit prep is repetitive automation. This tool captures that automation -- across **7 free security tools** -- so teams can focus on logic, not boilerplate.

**Positioning:** This is an **audit preparation orchestrator**, not a replacement for professional auditors. It runs the free tools that auditors expect you to have already run. The real value is presenting the results clearly and saying: **"Here's what 7 scanners found -- now the human auditor can focus on what machines can't catch."**

---

## License

MIT -- see [LICENSE](LICENSE)
