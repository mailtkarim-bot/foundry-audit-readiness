"""Unit tests for audit_readiness parsers."""

from pathlib import Path

from audit_readiness.parser import (
    parse_forge_coverage,
    parse_forge_test,
    parse_gas_snapshot,
    parse_invariants,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_parse_forge_coverage_returns_valid_percentages():
    result = parse_forge_coverage(FIXTURE)
    assert 0 <= result.line_percent <= 100
    assert 0 <= result.branch_percent <= 100
    assert 0 <= result.function_percent <= 100


def test_parse_forge_test_detects_passing_tests():
    result = parse_forge_test(FIXTURE)
    assert result.total > 0
    assert result.failed == 0


def test_parse_invariants_optional_by_default():
    result = parse_invariants(FIXTURE)
    assert result.functions_found == 0
    assert result.passed is False  # optional, no invariants found


def test_parse_gas_snapshot_no_baseline():
    result = parse_gas_snapshot(FIXTURE)
    assert result.baseline_exists is False
