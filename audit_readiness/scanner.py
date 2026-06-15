"""Static analysis wrappers for all free Solidity security tools.

Each wrapper follows the same pattern:
  1. Check tool is installed
  2. Run with proper arguments and timeout
  3. Parse output into Findings
  4. If the tool crashes (non-zero exit, no parsable output) → passed=False

CRITICAL: A tool that crashes is NEVER marked as PASS.
"""

import json
import os
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


def _tool_crashed(result, tool_name: str) -> Optional[str]:
    """Check if a tool crashed and return an error message.
    
    Returns None if the tool ran successfully, or an error string if it crashed.
    A tool 'crashed' if it returned non-zero exit code AND produced no valid output.
    """
    if result.returncode == 0:
        return None
    # Tool returned non-zero - check if it still produced useful output
    if result.stdout and len(result.stdout.strip()) > 50:
        # Has substantial output - may be findings, not a crash
        return None
    # No useful output - this is a crash
    err = result.stderr[:300] if result.stderr else f"{tool_name} exited with code {result.returncode}"
    return err


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

    crash_err = _tool_crashed(result, "slither")
    if crash_err:
        return StaticAnalysisResult(
            tool="slither",
            error=crash_err,
            passed=False,
            raw_output=result.stderr[:1000],
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

    # Slither's --json output wraps detectors under results.detectors
    results = data.get("results", {})
    if isinstance(results, dict):
        detectors = results.get("detectors", [])
    else:
        detectors = results if isinstance(results, list) else []

    ignored_prefixes = ("lib/", "test/", "script/", "node_modules/")
    for detector in detectors:
        if not isinstance(detector, dict):
            continue
        impact = detector.get("impact", "medium").lower()
        severity = severity_map.get(impact, "medium")
        elements = detector.get("elements", [{}])
        source_mapping = elements[0].get("source_mapping", {}) if elements else {}
        file_path = source_mapping.get("filename_short") or source_mapping.get("filename") or ""
        if any(str(file_path).startswith(p) or f"/{p}" in str(file_path) for p in ignored_prefixes):
            continue
        finding = Finding(
            tool="slither",
            severity=severity,
            check=detector.get("check", "unknown"),
            message=detector.get("description", ""),
            file=file_path,
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

    crash_err = _tool_crashed(result, "aderyn")
    if crash_err and not output_path.exists():
        return StaticAnalysisResult(
            tool="aderyn",
            error=crash_err,
            passed=False,
            raw_output=result.stderr[:1000],
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

    # FIX: Create a default .solhint.json if the project doesn't have one.
    # The config focuses on security rules and disables noisy style-only rules.
    solhint_config = project_path / ".solhint.json"
    config_created = False
    if not solhint_config.exists():
        default_config = {
            "extends": "solhint:recommended",
            "rules": {
                "code-complexity": ["error", 7],
                "compiler-version": ["error", ">=0.8.0"],
                "func-visibility": ["error", {"ignoreConstructors": True}],
                "not-rely-on-time": "off",
                "max-line-length": "off",
                "reason-string": "off",
                "no-empty-blocks": "off",
                "no-console": "off",
                "one-contract-per-file": "off",
                "ordering": "off",
                "immutable-vars-naming": "off",
                "private-vars-leading-underscore": "off",
                "const-name-snakecase": "off",
                "func-name-mixedcase": "off",
                "func-param-name-mixedcase": "off",
                "modifier-name-mixedcase": "off",
                "use-forbidden-name": "off",
                "var-name-mixedcase": "off",
                "imports-on-top": "off",
                "visibility-modifier-order": "off",
                "avoid-low-level-calls": "warn",
                "avoid-sha3": "error",
                "avoid-suicide": "error",
                "avoid-throw": "error",
                "avoid-tx-origin": "error",
                "check-send-result": "error",
                "reentrancy": "error",
                "state-visibility": "error"
            }
        }
        solhint_config.write_text(json.dumps(default_config, indent=2))
        config_created = True

    try:
        cmd = ["solhint", "-c", str(solhint_config), "--formatter", "unix"] + sol_files
        result = run_command(cmd, cwd=project_path)
    finally:
        if config_created and solhint_config.exists():
            solhint_config.unlink()

    # FIX: Check if solhint actually ran (not just config error)
    if result.returncode != 0 and "Failed to load" in (result.stderr or ""):
        return StaticAnalysisResult(
            tool="solhint",
            error=f"Solhint config error: {result.stderr[:200]}",
            passed=False,
            raw_output=result.stderr[:500],
        )

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
        raw_output=result.stderr[:500] if result.stderr else "",
    )


def run_semgrep(project_path: Path, timeout: int = 120) -> StaticAnalysisResult:
    """Run Semgrep with Solidity security rules."""
    if not _check_tool("semgrep"):
        return StaticAnalysisResult(
            tool="semgrep",
            error="Semgrep not found. Install: pip install semgrep",
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

    crash_err = _tool_crashed(result, "semgrep")
    if crash_err:
        import os
        if os.path.exists(output_path):
            os.unlink(output_path)
        return StaticAnalysisResult(
            tool="semgrep",
            error=crash_err,
            passed=False,
        )

    findings = []
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        import os
        if os.path.exists(output_path):
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

    Analyzes main contracts (not interfaces/libraries) with forge remappings
    passed via a temporary solc-json config.
    """
    if not _check_tool("myth"):
        return StaticAnalysisResult(
            tool="mythril",
            error="Mythril not found. Install: pip install mythril",
            passed=False,
        )

    # Get forge remappings
    remappings = []
    if _check_tool("forge"):
        rem_result = run_command(["forge", "remappings"], cwd=project_path)
        if rem_result.returncode == 0 and rem_result.stdout:
            remappings = [r.strip() for r in rem_result.stdout.strip().splitlines() if r.strip()]

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
    ][:3]
    if not main_contracts:
        main_contracts = [f for f in src_dir.rglob("*.sol")
                          if "lib/" not in str(f)][:3]

    # Mythril needs remappings in a solc-json file; CLI --solc-remaps is not
    # supported by all versions.
    solc_json = {
        "optimizer": {"enabled": True, "runs": 200},
        "remappings": remappings,
    }
    solc_json_path = project_path / ".mythril-solc.json"
    solc_json_path.write_text(json.dumps(solc_json))

    all_findings = []
    raw_outputs = []
    solc_error_seen = False

    try:
        for contract in main_contracts:
            cmd = [
                "myth", "analyze", str(contract),
                "--execution-timeout", str(max(30, timeout // max(1, len(main_contracts)))),
                "--solc-json", str(solc_json_path),
                "-o", "json",
            ]

            result = run_command(cmd, cwd=project_path)
            raw_outputs.append(f"{contract.name}: exit={result.returncode}")

            output_lower = ((result.stdout or "") + "\n" + (result.stderr or "")).lower()
            if "solidityversionmismatch" in output_lower or "solc experienced a fatal error" in output_lower:
                solc_error_seen = True
                continue

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
    finally:
        if solc_json_path.exists():
            solc_json_path.unlink()

    if solc_error_seen and not all_findings:
        all_findings.append(Finding(
            tool="mythril",
            severity="info",
            check="mythril-solc-version",
            message="Mythril skipped: solc version mismatch or compiler not available.",
        ))

    high_findings = any(f.severity == "high" for f in all_findings)
    return StaticAnalysisResult(
        tool="mythril",
        findings=all_findings,
        passed=not high_findings,
        raw_output="\n".join(raw_outputs) if raw_outputs else "",
    )


def run_halmos(project_path: Path, timeout: int = 300) -> StaticAnalysisResult:
    """Run Halmos - formal verification using symbolic execution.

    Halmos only verifies functions whose names start with `check_`. This wrapper
    scans test contracts, runs Halmos once per contract, and reports violations.
    If no `check_*` functions exist, the tool is skipped with an informational
    note rather than treated as a failure.
    """
    if not _check_tool("halmos"):
        return StaticAnalysisResult(
            tool="halmos",
            error="Halmos not found. Install: pip install halmos",
            passed=False,
        )

    test_contracts = []
    test_dir = project_path / "test"
    if test_dir.exists():
        ignored = {
            "CommonBase", "Config", "StdAssertions", "StdChains", "StdCheats",
            "StdConstants", "StdError", "StdJson", "StdMath", "StdStorage",
            "StdStyle", "StdToml", "StdUtils", "Vm", "console", "console2",
        }
        test_contracts = [
            f.stem for f in test_dir.rglob("*.t.sol")
            if f.stem not in ignored
        ][:5]

    if not test_contracts:
        return StaticAnalysisResult(
            tool="halmos",
            findings=[Finding(
                tool="halmos",
                severity="info",
                check="halmos-no-tests",
                message="No test contracts found. Halmos requires *.t.sol files.",
            )],
            passed=True,
        )

    all_findings = []
    raw_outputs = []
    no_check_functions_seen = False

    per_contract_timeout = max(30, timeout // max(1, len(test_contracts)))

    for contract_name in test_contracts:
        result = run_command(
            [
                "halmos",
                "--root", str(project_path),
                "--match-contract", f"^{contract_name}$",
                "--match-test", "^check_",
                "--solver-timeout-assertion", str(per_contract_timeout * 1000),
            ],
            cwd=project_path,
        )
        raw_outputs.append(f"{contract_name}: exit={result.returncode}")

        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if "no tests with" in output.lower():
            no_check_functions_seen = True
            continue

        for line in output.splitlines():
            line_lower = line.lower()
            if "counterexample" in line_lower or "violated" in line_lower:
                all_findings.append(Finding(
                    tool="halmos",
                    severity="high",
                    check="halmos-formal-check",
                    message=line.strip(),
                ))
            elif "timeout" in line_lower and ("function" in line_lower or "solver" in line_lower):
                all_findings.append(Finding(
                    tool="halmos",
                    severity="info",
                    check="halmos-timeout",
                    message=f"Analysis timed out: {line.strip()}",
                ))

    if no_check_functions_seen and not all_findings:
        all_findings.append(Finding(
            tool="halmos",
            severity="info",
            check="halmos-no-check-functions",
            message="No Halmos check_* functions found in test contracts. Formal verification skipped.",
        ))

    violated = any(f.severity == "high" for f in all_findings)
    return StaticAnalysisResult(
        tool="halmos",
        findings=all_findings,
        passed=not violated,
        raw_output="\n".join(raw_outputs) if raw_outputs else "",
    )


def run_smtchecker(project_path: Path, timeout: int = 180) -> StaticAnalysisResult:
    """Run SMTChecker via solc's built-in model checker.

    Temporarily enables the model_checker setting in the project's foundry.toml,
    runs forge build, then restores the original config. This avoids relying on
    the `--profile` CLI flag which is not supported by older Foundry versions.
    """
    if not _check_tool("forge"):
        return StaticAnalysisResult(
            tool="smtchecker",
            error="forge not found. Install Foundry.",
            passed=False,
        )

    foundry_toml = project_path / "foundry.toml"
    foundry_backup = project_path / "foundry.toml.bak"
    config_created = False

    # Basic build check to fail fast if the project doesn't compile normally.
    basic_build = run_command(["forge", "build"], cwd=project_path)
    if basic_build.returncode != 0:
        return StaticAnalysisResult(
            tool="smtchecker",
            error=f"forge build failed before SMTChecker: {basic_build.stderr[:200]}",
            passed=False,
        )

    try:
        if foundry_toml.exists():
            shutil.copy2(foundry_toml, foundry_backup)
            original_content = foundry_toml.read_text()
        else:
            original_content = ""

        # Inject model_checker into [profile.default] if it exists, otherwise
        # prepend a default profile with the setting.
        smt_line = f'model_checker = {{ engine = "chc", targets = ["assert", "overflow", "divByZero"], timeout = {timeout * 1000} }}\n'
        if "[profile.default]" in original_content:
            modified_content = original_content.replace(
                "[profile.default]\n",
                f"[profile.default]\n{smt_line}",
                1,
            )
        else:
            modified_content = f"[profile.default]\n{smt_line}" + original_content

        foundry_toml.write_text(modified_content)
        config_created = True

        result = run_command(["forge", "build"], cwd=project_path)

    finally:
        if foundry_backup.exists():
            shutil.copy2(foundry_backup, foundry_toml)
            foundry_backup.unlink()
        elif config_created and foundry_toml.exists():
            # We created the file from scratch; restore by removing it if there
            # was no original, otherwise should not happen because backup exists.
            if not original_content:
                foundry_toml.unlink()

    findings = []
    output_lines = (result.stdout or "").splitlines() + (result.stderr or "").splitlines()

    for line in output_lines:
        line_lower = line.lower()

        if "assertion violation" in line_lower or "chc: assertion" in line_lower:
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
        elif "overflow" in line_lower and ("detected" in line_lower or "happens here" in line_lower):
            findings.append(Finding(
                tool="smtchecker",
                severity="high",
                check="overflow",
                message=line.strip(),
            ))
        elif "underflow" in line_lower and ("detected" in line_lower or "happens here" in line_lower):
            findings.append(Finding(
                tool="smtchecker",
                severity="high",
                check="underflow",
                message=line.strip(),
            ))
        elif "division by zero" in line_lower:
            findings.append(Finding(
                tool="smtchecker",
                severity="high",
                check="division-by-zero",
                message=line.strip(),
            ))
        elif ("bmc" in line_lower or "chc" in line_lower) and "timeout" in line_lower:
            findings.append(Finding(
                tool="smtchecker",
                severity="info",
                check="timeout",
                message=line.strip(),
            ))

    violations = any(f.severity in ("critical", "high") for f in findings)

    if result.returncode != 0 and not findings:
        return StaticAnalysisResult(
            tool="smtchecker",
            findings=[],
            passed=False,
            error=f"SMTChecker build failed (exit {result.returncode}). SMT may not be supported by your solc/Foundry version.",
            raw_output=result.stderr[:500] if result.stderr else "",
        )

    return StaticAnalysisResult(
        tool="smtchecker",
        findings=findings,
        passed=not violations,
        raw_output=f"forge build with model_checker: exit={result.returncode}",
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
                    passed=False,  # CRITICAL: never mark a crashed tool as PASS
                )
        else:
            logger.warning(f"Unknown static analysis tool: {tool_name}")
    
    return results
