"""Parsers for forge coverage, test results, snapshots, and invariants."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from audit_readiness.utils import find_solidity_files, run_command, logger


@dataclass
class CoverageResult:
    line_percent: float = 0.0
    branch_percent: float = 0.0
    function_percent: float = 0.0
    passed: bool = False
    raw_data: Dict = field(default_factory=dict)


@dataclass
class TestResult:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: int = 0


@dataclass
class InvariantResult:
    functions_found: int = 0
    all_passed: bool = True
    runs: int = 0
    passed: bool = False


@dataclass
class GasSnapshot:
    functions: Dict[str, int] = field(default_factory=dict)
    baseline_exists: bool = False
    regressions: List[str] = field(default_factory=list)


def _parse_coverage_cell(cell: str) -> Optional[Tuple[float, int, int]]:
    """Parse a cell like '96.4% (87/87)' into (percent, hit, total)."""
    match = re.match(r"([\d.]+)%\s*\((\d+)/(\d+)\)", cell.strip())
    if not match:
        return None
    return float(match.group(1)), int(match.group(2)), int(match.group(3))


def _parse_coverage_table(
    stdout: str,
    ignore_paths: Optional[List[str]] = None,
) -> CoverageResult:
    """Parse forge coverage terminal table, aggregating non-ignored source files."""
    ignore_paths = ignore_paths or []

    totals = {
        "line": {"hit": 0, "total": 0},
        "statement": {"hit": 0, "total": 0},
        "branch": {"hit": 0, "total": 0},
        "function": {"hit": 0, "total": 0},
    }
    total_row = None
    source_rows_found = False

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        parts = [part.strip() for part in line.split("|")]
        parts = [part for part in parts if part]
        if len(parts) < 5:
            continue

        label = parts[0]
        if label.lower() == "file" or "---" in label:
            continue

        cells = [_parse_coverage_cell(part) for part in parts[1:5]]
        if any(cell is None for cell in cells):
            continue

        if label.lower() == "total":
            total_row = cells
            continue

        if any(ignore in label for ignore in ignore_paths):
            continue

        line_pct, line_hit, line_total = cells[0]
        stmt_pct, stmt_hit, stmt_total = cells[1]
        branch_pct, branch_hit, branch_total = cells[2]
        func_pct, func_hit, func_total = cells[3]

        totals["line"]["hit"] += line_hit
        totals["line"]["total"] += line_total
        totals["statement"]["hit"] += stmt_hit
        totals["statement"]["total"] += stmt_total
        totals["branch"]["hit"] += branch_hit
        totals["branch"]["total"] += branch_total
        totals["function"]["hit"] += func_hit
        totals["function"]["total"] += func_total
        source_rows_found = True

    def calc_pct(hit: int, total: int) -> float:
        return (hit / total * 100) if total > 0 else 0.0

    if source_rows_found:
        return CoverageResult(
            line_percent=calc_pct(totals["line"]["hit"], totals["line"]["total"]),
            branch_percent=calc_pct(totals["branch"]["hit"], totals["branch"]["total"]),
            function_percent=calc_pct(
                totals["function"]["hit"], totals["function"]["total"]
            ),
        )

    if total_row:
        line_pct, line_hit, line_total = total_row[0]
        stmt_pct, stmt_hit, stmt_total = total_row[1]
        branch_pct, branch_hit, branch_total = total_row[2]
        func_pct, func_hit, func_total = total_row[3]
        return CoverageResult(
            line_percent=line_pct,
            branch_percent=branch_pct,
            function_percent=func_pct,
        )

    return CoverageResult()


def parse_forge_coverage(
    project_path: Path,
    ignore_paths: Optional[List[str]] = None,
) -> CoverageResult:
    """Run forge coverage and parse the terminal summary table."""
    result = run_command(
        ["forge", "coverage"],
        cwd=project_path,
    )

    if result.returncode != 0:
        logger.error("forge coverage failed")
        return CoverageResult()

    return _parse_coverage_table(result.stdout, ignore_paths=ignore_paths)


def parse_forge_test(project_path: Path, match_pattern: Optional[str] = None) -> TestResult:
    """Run forge test and parse summary."""
    cmd = ["forge", "test"]
    if match_pattern:
        cmd.extend(["--match-contract", match_pattern])

    result = run_command(cmd, cwd=project_path)

    # Parse final summary line: "Ran 1 test suite in ...: 3 tests passed, 0 failed, 0 skipped"
    summary_match = re.search(
        r"Ran \d+ test suites? in [^:]*:\s*(\d+)\s*tests? passed,\s*(\d+) failed,\s*(\d+) skipped",
        result.stdout,
    )

    if summary_match:
        passed = int(summary_match.group(1))
        failed = int(summary_match.group(2))
        skipped = int(summary_match.group(3))
        total = passed + failed + skipped
        return TestResult(total=total, passed=passed, failed=failed, skipped=skipped)

    return TestResult()


def parse_invariants(
    project_path: Path,
    ignore_paths: Optional[List[str]] = None,
) -> InvariantResult:
    """Detect and run invariant tests."""
    ignore_paths = ignore_paths or ["lib/", "node_modules/"]

    # Search for Solidity files with "Invariant" in the name, excluding ignored dirs
    all_sol_files = find_solidity_files(project_path, ignore_paths)
    invariant_files = [f for f in all_sol_files if "Invariant" in f.name]

    if not invariant_files:
        return InvariantResult(functions_found=0, all_passed=False, passed=False)

    # Run forge test with invariant pattern
    test_result = parse_forge_test(project_path, match_pattern="Invariant")

    # Count invariant functions by grepping for 'function invariant_' in test files
    functions_found = 0
    for f in invariant_files:
        content = f.read_text(encoding="utf-8")
        functions_found += len(re.findall(r"function\s+invariant_\w+", content))

    return InvariantResult(
        functions_found=functions_found,
        all_passed=test_result.failed == 0 and test_result.total > 0,
        runs=10_000,  # Default Foundry fuzz runs
        passed=test_result.failed == 0 and functions_found > 0,
    )


def parse_gas_snapshot(project_path: Path) -> GasSnapshot:
    """Parse .gas-snapshot file if it exists."""
    snapshot_path = project_path / ".gas-snapshot"
    if not snapshot_path.exists():
        return GasSnapshot(baseline_exists=False)

    functions = {}
    for line in snapshot_path.read_text(encoding="utf-8").splitlines():
        # Format: ContractName:testFunction() (gas: 12345)
        match = re.match(r"(\w+):(.+)\s+\(gas:\s*(\d+)\)", line.strip())
        if match:
            func_key = f"{match.group(1)}:{match.group(2)}"
            functions[func_key] = int(match.group(3))

    return GasSnapshot(functions=functions, baseline_exists=True)


def check_compiler_warnings(
    project_path: Path,
    ignore_paths: Optional[List[str]] = None,
) -> tuple[bool, List[str]]:
    """Run forge build and return (no_warnings, list of warning blocks)."""
    ignore_paths = ignore_paths or []
    result = run_command(["forge", "build"], cwd=project_path)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    lines = combined.splitlines()

    warnings: List[str] = []
    current: List[str] = []
    in_warning = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_warning:
                warnings.append("\n".join(current).strip())
                current = []
                in_warning = False
            continue

        if stripped.lower().startswith("warning"):
            if in_warning:
                warnings.append("\n".join(current).strip())
                current = []
            in_warning = True

        if in_warning:
            current.append(line.rstrip())

    if in_warning and current:
        warnings.append("\n".join(current).strip())

    # Filter out warnings located in ignored paths (e.g. test/, script/)
    filtered = []
    for warning in warnings:
        if any(ignore in warning for ignore in ignore_paths):
            continue
        filtered.append(warning)

    return not filtered, filtered
