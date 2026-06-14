"""Static analysis wrappers for Slither and Aderyn."""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from audit_readiness.utils import run_command, logger


@dataclass
class Finding:
    tool: str
    severity: str  # critical, high, medium, low, info
    check: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None


@dataclass
class StaticAnalysisResult:
    tool: str
    findings: List[Finding] = field(default_factory=list)
    passed: bool = True
    error: Optional[str] = None


def run_slither(project_path: Path) -> StaticAnalysisResult:
    """Run Slither and parse JSON output."""
    if not shutil.which("slither"):
        return StaticAnalysisResult(
            tool="slither",
            error="Slither not found in PATH. Install with: pip install slither-analyzer",
            passed=False,
        )

    result = run_command(
        ["slither", str(project_path), "--json", "-"],
        cwd=project_path,
    )

    if result.returncode != 0 and not result.stdout:
        return StaticAnalysisResult(
            tool="slither",
            error=result.stderr or "Slither failed to run",
            passed=False,
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return StaticAnalysisResult(
            tool="slither",
            error="Failed to parse Slither JSON output",
            passed=False,
        )

    findings = []
    for detector in data.get("results", []):
        if not isinstance(detector, dict):
            continue
        elements = detector.get("elements", [{}])
        source_mapping = elements[0].get("source_mapping", {}) if elements else {}
        finding = Finding(
            tool="slither",
            severity=detector.get("impact", "medium").lower(),
            check=detector.get("check", "unknown"),
            message=detector.get("description", ""),
            file=source_mapping.get("filename"),
            line=source_mapping.get("lines", [None])[0] if source_mapping else None,
        )
        findings.append(finding)

    critical_or_high = any(f.severity in ("critical", "high") for f in findings)
    return StaticAnalysisResult(
        tool="slither",
        findings=findings,
        passed=not critical_or_high,
    )


def run_aderyn(project_path: Path) -> StaticAnalysisResult:
    """Run Aderyn and parse output."""
    if not shutil.which("aderyn"):
        return StaticAnalysisResult(
            tool="aderyn",
            error="Aderyn not found in PATH. Install from https://github.com/Cyfrin/aderyn/releases",
            passed=False,
        )

    output_path = project_path / "aderyn-report.json"
    result = run_command(
        ["aderyn", str(project_path), "-o", str(output_path), "-j"],
        cwd=project_path,
    )

    if not output_path.exists():
        return StaticAnalysisResult(
            tool="aderyn",
            error="Aderyn did not produce output",
            passed=False,
        )

    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return StaticAnalysisResult(
            tool="aderyn",
            error="Failed to parse Aderyn JSON output",
            passed=False,
        )
    finally:
        # Clean up generated report
        if output_path.exists():
            output_path.unlink()

    findings = []
    for issue in data.get("issues", []):
        finding = Finding(
            tool="aderyn",
            severity=issue.get("severity", "medium").lower(),
            check=issue.get("title", "unknown"),
            message=issue.get("description", ""),
        )
        findings.append(finding)

    high = any(f.severity == "high" for f in findings)
    return StaticAnalysisResult(
        tool="aderyn",
        findings=findings,
        passed=not high,
    )


def run_static_analysis(project_path: Path, tools: List[str]) -> Dict[str, StaticAnalysisResult]:
    """Run all configured static analysis tools."""
    results = {}
    for tool in tools:
        if tool == "slither":
            results["slither"] = run_slither(project_path)
        elif tool == "aderyn":
            results["aderyn"] = run_aderyn(project_path)
        else:
            logger.warning(f"Unknown static analysis tool: {tool}")
    return results
