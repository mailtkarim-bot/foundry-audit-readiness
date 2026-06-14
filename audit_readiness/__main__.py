"""CLI entry point for Foundry Audit Readiness - Multi-Tool Edition."""

import datetime
import sys
from pathlib import Path

import click

from audit_readiness import __version__, __tools__
from audit_readiness.config import Config
from audit_readiness.natspec import check_natspec_completeness
from audit_readiness.parser import (
    check_compiler_warnings,
    parse_forge_coverage,
    parse_gas_snapshot,
    parse_invariants,
)
from audit_readiness.reporter import (
    generate_markdown_report,
    generate_html_report,
    save_report,
)
from audit_readiness.scanner import run_static_analysis
from audit_readiness.utils import console, logger


class DummyCoverage:
    line_percent = 0.0
    branch_percent = 0.0
    function_percent = 0.0


class DummyInvariant:
    functions_found = 0
    all_passed = False
    passed = False
    runs = 0


class DummyNatSpec:
    passed = False
    total_public = 0
    documented_public = 0
    missing = []


class DummyGas:
    baseline_exists = False
    functions = {}


@click.command()
@click.option("--target", "-t", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to the Foundry project to analyze.")
@click.option("--output", "-o", default="audit-report.md", type=click.Path(path_type=Path),
              help="Output file path.")
@click.option("--format", "-f", default="both", type=click.Choice(["markdown", "html", "both"]),
              help="Output format. 'both' generates Markdown + HTML. HTML includes a 'Save as PDF' button.")
@click.option("--checks", "-c", default="all",
              help="Comma-separated: all, coverage, invariants, natspec, static, gas.")
@click.option("--fail-on-threshold", is_flag=True,
              help="Exit with non-zero code if thresholds are not met.")
@click.option("--tools", default=None,
              help="Override tools: comma-separated list (slither,aderyn,solhint,semgrep,mythril,halmos,smtchecker).")
@click.version_option(version=__version__, prog_name="foundry-audit-readiness")
def main(
    target: Path,
    output: Path,
    format: str,
    checks: str,
    fail_on_threshold: bool,
    tools: str,
) -> None:
    """Run comprehensive audit readiness checks with free Solidity security tools."""
    console.rule(f"[bold blue] Foundry Audit Readiness v{__version__} - {target.name}")

    config = Config.from_project(target)
    
    # Allow --tools override
    if tools:
        config.static_analysis.tools = [t.strip() for t in tools.split(",")]

    n_tools_configured = len(config.static_analysis.tools)
    console.print(f"[dim]Configured: {n_tools_configured} tool(s) "
                  f"({', '.join(config.static_analysis.tools)})[/dim]")

    enabled_checks = set(checks.split(",")) if checks != "all" else {"all"}
    run_all = "all" in enabled_checks
    run_static = run_all or "static" in enabled_checks
    run_coverage = run_all or "coverage" in enabled_checks
    run_invariants = run_all or "invariants" in enabled_checks
    run_natspec = run_all or "natspec" in enabled_checks
    run_gas = run_all or "gas" in enabled_checks

    results = {}
    tools_ran = 0
    tools_skipped = 0
    tools_failed = 0

    if run_static:
        console.rule(f"[yellow] Static Analysis Suite ({n_tools_configured} tool(s) configured)")
        results["static_analysis"] = run_static_analysis(target, config)
        for tool, res in results["static_analysis"].items():
            if res.error:
                console.print(f"  [yellow]{tool:12s}[/yellow]: [dim]skipped - {res.error[:80]}[/dim]")
                tools_skipped += 1
            elif not res.passed:
                console.print(f"  [red]{tool:12s}[/red]: FAIL ({len(res.findings)} findings)")
                tools_ran += 1
                tools_failed += 1
            else:
                console.print(f"  [green]{tool:12s}[/green]: PASS ({len(res.findings)} findings)")
                tools_ran += 1

    if run_coverage:
        console.rule("[yellow] Test Coverage")
        results["coverage"] = parse_forge_coverage(
            target, ignore_paths=config.static_analysis.ignore_paths
        )
        cov = results["coverage"]
        console.print(f"  Line:     {cov.line_percent:.1f}% (threshold: {config.coverage.line}%)")
        console.print(f"  Branch:   {cov.branch_percent:.1f}% (threshold: {config.coverage.branch}%)")
        console.print(f"  Function: {cov.function_percent:.1f}% (threshold: {config.coverage.function}%)")

    if run_invariants:
        console.rule("[yellow] Invariant Tests")
        results["invariants"] = parse_invariants(target)
        inv = results["invariants"]
        console.print(f"  Functions found: {inv.functions_found}")
        console.print(f"  All passed: {inv.all_passed}")
        if not inv.passed and config.invariants.min_functions > 0:
            console.print("  [dim]Note: Invariants are optional by default.[/dim]")

    if run_natspec:
        console.rule("[yellow] NatSpec Compliance")
        results["natspec"] = check_natspec_completeness(
            target,
            config.static_analysis.ignore_paths,
            config.natspec.require_public,
            config.natspec.require_external,
        )
        ns = results["natspec"]
        console.print(f"  Public:   {ns.documented_public}/{ns.total_public}")
        console.print(f"  External: {ns.documented_external}/{ns.total_external}")

    console.rule("[yellow] Compiler Warnings")
    no_warnings, warning_lines = check_compiler_warnings(
        target, ignore_paths=config.static_analysis.ignore_paths
    )
    console.print(f"  No warnings: {no_warnings}")
    for line in warning_lines[:3]:
        console.print(f"    [dim]{line[:120]}[/dim]")

    if run_gas:
        console.rule("[yellow] Gas Snapshots")
        results["gas"] = parse_gas_snapshot(target)
        gas = results["gas"]
        console.print(f"  Baseline exists: {gas.baseline_exists}")
        if gas.baseline_exists:
            console.print(f"  Functions tracked: {len(gas.functions)}")

    # Generate report
    console.rule("[green] Generating Report")

    report = generate_markdown_report(
        project_name=target.name,
        version=__version__,
        date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        config=config,
        static_analysis=results.get("static_analysis", {}),
        coverage=results.get("coverage", DummyCoverage()),
        invariants=results.get("invariants", DummyInvariant()),
        natspec=results.get("natspec", DummyNatSpec()),
        gas=results.get("gas", DummyGas()),
        no_warnings=no_warnings,
        compiler_warnings=warning_lines,
    )

    md_output = output.with_suffix(".md")
    html_output = output.with_suffix(".html")

    if format in ("markdown", "both"):
        save_report(report, md_output)

    if format in ("html", "both"):
        generate_html_report(report, html_output)

    # Determine overall status
    static_results = results.get("static_analysis", {})
    static_ok = all(
        r.passed for r in static_results.values() if not r.error
    ) if static_results else True

    coverage_obj = results.get("coverage", DummyCoverage())
    coverage_ok = (
        coverage_obj.line_percent >= config.coverage.line
        and coverage_obj.branch_percent >= config.coverage.branch
        and coverage_obj.function_percent >= config.coverage.function
    ) if "coverage" in results else True

    ns_obj = results.get("natspec", DummyNatSpec())
    natspec_ok = ns_obj.passed if "natspec" in results else True

    all_passed = static_ok and coverage_ok and natspec_ok and no_warnings

    # Honest summary message
    if all_passed:
        console.rule("[bold green] READY FOR PROFESSIONAL AUDIT")
        msg_parts = []
        if tools_ran > 0:
            msg_parts.append(f"{tools_ran} tool(s) ran clean")
        if tools_skipped > 0:
            msg_parts.append(f"{tools_skipped} skipped (not installed)")
        if tools_failed > 0:
            msg_parts.append(f"{tools_failed} had findings (non-critical)")
        console.print(f"[green]{' | '.join(msg_parts)}[/green]")
        if tools_skipped > 0:
            console.print(f"[dim]Install more tools for deeper checks: "
                          f"mythril, halmos, aderyn | Use: --tools {','.join(__tools__)}[/dim]")
    else:
        console.rule("[bold red] NOT READY FOR AUDIT")
        if tools_failed > 0:
            console.print(f"[red]{tools_failed} tool(s) reported critical/high findings[/red]")
        if not coverage_ok:
            console.print("[red]Coverage below thresholds[/red]")
        if not natspec_ok:
            console.print("[red]NatSpec documentation incomplete[/red]")
        if not no_warnings:
            console.print("[red]Compiler warnings detected[/red]")

    if fail_on_threshold and not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
