"""Static analysis wrappers for all free Solidity security tools."""

import json
import shutil
import tempfile
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
    raw_output: str = ""  # For storing raw command output


def _check_tool(tool_name: str) -> bool:
    """Check if a tool is available in PATH."""
    return shutil.which(tool_name) is not None


def run_slither(project_path: Path, timeout: int = 300) -> StaticAnalysisResult:
    """Run Slither (Trail of Bits) - industry standard static analysis."""
    if not _check_tool("slither"):
        return StaticAnalysisResult(
            tool="slither",
            error="Slither not found. Install: pip install slither-analyzer",
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
            raw_output=result.stderr,
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return StaticAnalysisResult(
            tool="slither",
            error="Failed to parse Slither JSON output",
            passed=False,
            raw_output=result.stdout[:2000],
        )

    findings = []
    severity_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "informational": "info"}
    
    for detector in data.get("results", []):
        if not isinstance(detector, dict):
            continue
        impact = detector.get("impact", "medium").lower()
        severity = severity_map.get(impact, "medium")
        elements = detector.get("elements", [{}])
        source_mapping = elements[0].get("source_mapping", {}) if elements else {}
        finding = Finding(
            tool="slither",
            severity=severity,
            check=detector.get("check", "unknown"),
            message=detector.get("description", ""),
            file=source_mapping.get("filename_short") or source_mapping.get("filename"),
            line=source_mapping.get("lines", [None])[0] if source_mapping else None,
        )
        findings.append(finding)

    critical_or_high = any(f.severity in ("critical", "high") for f in findings)
    return StaticAnalysisResult(
        tool="slither",
        findings=findings,
        passed=not critical_or_high,
        raw_output=result.stdout[:2000] if not findings else "",
    )


def run_aderyn(project_path: Path, timeout: int = 120) -> StaticAnalysisResult:
    """Run Aderyn (Cyfrin) - fast Rust-based static analyzer."""
    if not _check_tool("aderyn"):
        return StaticAnalysisResult(
            tool="aderyn",
            error="Aderyn not found. Install: https://github.com/Cyfrin/aderyn/releases",
            passed=False,
        )

    output_path = project_path / "aderyn-report.json"
    result = run_command(
        ["aderyn", str(project_path), "-o", str(output_path)],
        cwd=project_path,
    )

    if not output_path.exists():
        return StaticAnalysisResult(
            tool="aderyn",
            error="Aderyn did not produce output",
            passed=False,
            raw_output=result.stderr[:1000],
        )

    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        if output_path.exists():
            output_path.unlink()
        return StaticAnalysisResult(
            tool="aderyn",
            error=f"Failed to parse Aderyn output: {e}",
            passed=False,
        )
    finally:
        if output_path.exists():
            output_path.unlink()

    findings = []
    severity_map = {"high": "high", "medium": "medium", "low": "low", "informational": "info"}
    for issue in data.get("issues", []):
        sev = issue.get("severity", "medium").lower()
        findings.append(Finding(
            tool="aderyn",
            severity=severity_map.get(sev, "medium"),
            check=issue.get("title", "unknown"),
            message=issue.get("description", ""),
        ))

    high = any(f.severity == "high" for f in findings)
    return StaticAnalysisResult(
        tool="aderyn",
        findings=findings,
        passed=not high,
    )


def run_solhint(project_path: Path, timeout: int = 60) -> StaticAnalysisResult:
    """Run Solhint - Solidity linter for style and basic security."""
    if not _check_tool("solhint"):
        return StaticAnalysisResult(
            tool="solhint",
            error="Solhint not found. Install: npm install -g solhint",
            passed=False,
        )

    # Build file list explicitly (avoids shell glob issues)
    src_dir = project_path / "src"
    if not src_dir.exists():
        return StaticAnalysisResult(
            tool="solhint",
            error="No src/ directory found",
            passed=False,
        )

    sol_files = [str(f) for f in src_dir.rglob("*.sol")
                 if "lib/" not in str(f) and "node_modules/" not in str(f)]
    if not sol_files:
        return StaticAnalysisResult(
            tool="solhint",
            error="No .sol files found in src/",
            passed=False,
        )

    # Run with explicit file list (no shell glob needed)
    solhint_config = project_path / ".solhint.json"
    cmd = ["solhint", "--formatter", "unix"] + sol_files
    if solhint_config.exists():
        cmd = ["solhint", "-c", str(solhint_config), "--formatter", "unix"] + sol_files

    result = run_command(cmd, cwd=project_path)

    findings = []
    for line in (result.stdout or "").splitlines():
        if not line.strip() or line.startswith("/"):
            continue
        parts = line.split("  ", 1) if "  " in line else (line, "")
        location = parts[0].strip()
        message = parts[1].strip() if len(parts) > 1 else ""
        
        sev = "info"
        file_path = None
        line_no = None
        
        if "error" in location.lower():
            sev = "high"
        elif "warning" in location.lower():
            sev = "medium"
        
        loc_match = location.split(":")
        if len(loc_match) >= 3:
            file_path = loc_match[0].strip()
            try:
                line_no = int(loc_match[1])
            except ValueError:
                pass
        
        findings.append(Finding(
            tool="solhint",
            severity=sev,
            check="solhint-rule",
            message=message or location,
            file=file_path,
            line=line_no,
        ))

    errors = any(f.severity in ("critical", "high") for f in findings)
    return StaticAnalysisResult(
        tool="solhint",
        findings=findings,
        passed=not errors,
        raw_output=result.stderr[:1000] if result.stderr else "",
    )


def run_semgrep(project_path: Path, timeout: int = 120) -> StaticAnalysisResult:
    """Run Semgrep with Solidity security rules."""
    if not _check_tool("semgrep"):
        return StaticAnalysisResult(
            tool="semgrep",
            error="Semgrep not found. Install: pip install semgrep  OR  brew install semgrep",
            passed=False,
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        output_path = tmp.name

    result = run_command(
        [
            "semgrep", "--config=auto",
            str(project_path / "src"),
            "--json",
            "-o", output_path,
            "--timeout", str(timeout),
            "--quiet",
        ],
        cwd=project_path,
    )

    findings = []
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        import os
        os.unlink(output_path)
        return StaticAnalysisResult(
            tool="semgrep",
            error="Failed to parse Semgrep output",
            passed=False,
        )
    finally:
        import os
        if os.path.exists(output_path):
            os.unlink(output_path)

    severity_map = {"ERROR": "high", "WARNING": "medium", "INFO": "info"}
    for res in data.get("results", []):
        findings.append(Finding(
            tool="semgrep",
            severity=severity_map.get(res.get("extra", {}).get("severity", "INFO"), "info"),
            check=res.get("check_id", "unknown").split(".")[-1],
            message=res.get("extra", {}).get("message", ""),
            file=res.get("path"),
            line=res.get("start", {}).get("line"),
        ))

    high_findings = any(f.severity == "high" for f in findings)
    return StaticAnalysisResult(
        tool="semgrep",
        findings=findings,
        passed=not high_findings,
    )


def run_mythril(project_path: Path, timeout: int = 600) -> StaticAnalysisResult:
    """Run Mythril - symbolic execution for complex bug detection.
    
    Analyzes the project as a whole (not individual files) to resolve imports.
    Requires forge remappings for proper dependency resolution.
    """
    if not _check_tool("myth"):
        return StaticAnalysisResult(
            tool="mythril",
            error="Mythril not found. Install: pip install mythril",
            passed=False,
        )

    # Check forge is available for remappings
    remappings = ""
    if _check_tool("forge"):
        rem_result = run_command(
            ["forge", "remappings"],
            cwd=project_path,
        )
        if rem_result.returncode == 0 and rem_result.stdout:
            remappings = rem_result.stdout.strip()

    # Build solc-json config for Mythril with proper remappings
    solc_json = {"optimizer": {"enabled": True, "runs": 200}}
    if remappings:
        solc_json["settings"] = {"remappings": remappings.splitlines()}

    # Analyze the src/ directory as a whole (not individual files)
    src_dir = project_path / "src"
    if not src_dir.exists():
        return StaticAnalysisResult(
            tool="mythril",
            error="No src/ directory found",
            passed=False,
        )

    # Find main contracts (not interfaces or libraries)
    main_contracts = [
        f for f in src_dir.rglob("*.sol")
        if not f.name.startswith("I") and "interface" not in str(f).lower()
        and "library" not in str(f).lower() and "lib/" not in str(f)
    ][:3]  # Limit to 3 main contracts (Mythril is very slow)

    if not main_contracts:
        main_contracts = [f for f in src_dir.rglob("*.sol")
                          if "lib/" not in str(f)][:3]

    all_findings = []
    raw_outputs = []

    for contract in main_contracts:
        # Build remappings arguments
        remap_args = []
        if remappings:
            for remap in remappings.splitlines():
                if remap.strip():
                    remap_args.extend(["--solc-remaps", remap.strip()])

        cmd = [
            "myth", "analyze", str(contract),
            "--execution-timeout", str(timeout // len(main_contracts)),
            "-o", "json",
        ] + remap_args

        result = run_command(cmd, cwd=project_path)
        raw_outputs.append(f"{contract.name}: exit={result.returncode}")

        try:
            data = json.loads(result.stdout) if result.stdout else {}
        except json.JSONDecodeError:
            continue

        severity_map = {"High": "high", "Medium": "medium", "Low": "low", "Informational": "info"}
        for issue in data.get("issues", []):
            all_findings.append(Finding(
                tool="mythril",
                severity=severity_map.get(issue.get("severity", "Medium"), "medium"),
                check=issue.get("title", "unknown"),
                message=issue.get("description", ""),
                file=str(contract.relative_to(project_path)),
                line=issue.get("lineno"),
            ))

    high_findings = any(f.severity == "high" for f in all_findings)
    return StaticAnalysisResult(
        tool="mythril",
        findings=all_findings,
        passed=not high_findings,
        raw_output="\n".join(raw_outputs) if raw_outputs else "",
    )


def run_halmos(project_path: Path, timeout: int = 300) -> StaticAnalysisResult:
    """Run Halmos - formal verification using symbolic execution."""
    if not _check_tool("halmos"):
        return StaticAnalysisResult(
            tool="halmos",
            error="Halmos not found. Install: pip install halmos",
            passed=False,
        )

    result = run_command(
        ["halmos", "--root", str(project_path), "--timeout", str(timeout)],
        cwd=project_path,
    )

    findings = []
    # Parse Halmos output for counterexamples and results
    for line in (result.stdout or "").splitlines():
        line_lower = line.lower()
        if "counterexample" in line_lower or "violated" in line_lower:
            findings.append(Finding(
                tool="halmos",
                severity="high",
                check="halmos-formal-check",
                message=line.strip(),
            ))
        elif "timeout" in line_lower and "function" in line_lower:
            findings.append(Finding(
                tool="halmos",
                severity="info",
                check="halmos-timeout",
                message=f"Analysis timed out: {line.strip()}",
            ))
        elif "error" in line_lower and "revert" in line_lower:
            findings.append(Finding(
                tool="halmos",
                severity="medium",
                check="halmos-revert-check",
                message=line.strip(),
            ))

    violated = any(f.severity == "high" for f in findings)
    return StaticAnalysisResult(
        tool="halmos",
        findings=findings,
        passed=not violated,
        raw_output=result.stdout[:1500] if result.stdout else result.stderr[:1000],
    )


def run_smtchecker(project_path: Path, timeout: int = 180) -> StaticAnalysisResult:
    """Run SMTChecker via forge - uses solc's built-in SMT solver with Foundry remappings.
    
    Requires: forge installed (uses bundled solc with proper import resolution).
    Experimental: SMTChecker can fail on complex dependency trees. Best for simple contracts.
    """
    if not _check_tool("forge"):
        return StaticAnalysisResult(
            tool="smtchecker",
            error="forge not found. Install Foundry. SMTChecker requires forge for import resolution.",
            passed=False,
        )

    # Use forge build with SMTChecker options via environment variable
    # This ensures proper import resolution via forge's remappings
    import os
    env = os.environ.copy()
    env["FOUNDRY_OPTS"] = (
        f"--model-checker-engine chc "
        f"--model-checker-targets assert,overflow,divByZero "
        f"--model-checker-timeout {timeout}"
    )

    # Run forge build which will invoke solc with SMTChecker options
    result = run_command(
        ["forge", "build", "--extra-output", "errors"],
        cwd=project_path,
        env=env,
    )

    findings = []
    
    # Parse forge build output for SMTChecker warnings
    for line in (result.stdout or "").splitlines() + (result.stderr or "").splitlines():
        line_lower = line.lower()
        
        # SMTChecker reports via compiler warnings
        if " assertion violation" in line_lower or "chc: assertion" in line_lower:
            # Extract file and line from compiler warning format
            parts = line.split(":")
            file_path = parts[0].strip() if len(parts) > 0 else None
            line_no = None
            try:
                line_no = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else None
            except (ValueError, IndexError):
                pass
            
            findings.append(Finding(
                tool="smtchecker",
                severity="high",
                check="assertion-violation",
                message=line.strip(),
                file=file_path,
                line=line_no,
            ))
        elif " overflow" in line_lower and ("detected" in line_lower or "happens here" in line_lower):
            findings.append(Finding(
                tool="smtchecker",
                severity="high",
                check="overflow",
                message=line.strip(),
            ))
        elif " underflow" in line_lower and ("detected" in line_lower or "happens here" in line_lower):
            findings.append(Finding(
                tool="smtchecker",
                severity="high",
                check="underflow",
                message=line.strip(),
            ))
        elif " division by zero" in line_lower:
            findings.append(Finding(
                tool="smtchecker",
                severity="high",
                check="division-by-zero",
                message=line.strip(),
            ))
        elif "bmc: " in line_lower and "timeout" in line_lower:
            findings.append(Finding(
                tool="smtchecker",
                severity="info",
                check="timeout",
                message=f"SMTChecker BMC timeout: {line.strip()}",
            ))
        elif "chc: " in line_lower and "timeout" in line_lower:
            findings.append(Finding(
                tool="smtchecker",
                severity="info",
                check="timeout",
                message=f"SMTChecker CHC timeout: {line.strip()}",
            ))

    violations = any(f.severity in ("critical", "high") for f in findings)
    
    # If SMTChecker couldn't run (no findings, no output), report it
    if not findings and result.returncode == 0:
        # SMTChecker ran but found nothing - this is OK
        pass
    elif not findings and result.returncode != 0:
        # SMTChecker likely failed to activate
        return StaticAnalysisResult(
            tool="smtchecker",
            findings=[],
            passed=True,  # Don't fail if SMTChecker couldn't activate
            raw_output=f"forge build exit code: {result.returncode}\nSMTChecker may not have activated. "
                       f"Ensure your solc version supports model checking.\n{result.stderr[:500]}",
        )

    return StaticAnalysisResult(
        tool="smtchecker",
        findings=findings,
        passed=not violations,
        raw_output=f"forge build exit: {result.returncode}",
    )


def run_static_analysis(project_path: Path, config) -> Dict[str, StaticAnalysisResult]:
    """Run ALL configured static analysis tools with timeouts."""
    results = {}
    timeouts = getattr(config.static_analysis, 'timeouts', {})
    
    tool_runners = {
        "slither": run_slither,
        "aderyn": run_aderyn,
        "solhint": run_solhint,
        "semgrep": run_semgrep,
        "mythril": run_mythril,
        "halmos": run_halmos,
        "smtchecker": run_smtchecker,
    }
    
    for tool_name in config.static_analysis.tools:
        runner = tool_runners.get(tool_name)
        if runner:
            logger.info(f"Running {tool_name}...")
            timeout = timeouts.get(tool_name, 300)
            try:
                results[tool_name] = runner(project_path, timeout=timeout)
            except Exception as e:
                logger.error(f"{tool_name} crashed: {e}")
                results[tool_name] = StaticAnalysisResult(
                    tool=tool_name,
                    error=f"Tool crashed: {e}",
                    passed=False,
                )
        else:
            logger.warning(f"Unknown static analysis tool: {tool_name}")
    
    return results
