"""Unit tests for NatSpec checker."""

from pathlib import Path

from audit_readiness.natspec import check_natspec_completeness

FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"


def test_natspec_all_public_functions_documented():
    result = check_natspec_completeness(
        FIXTURE,
        ignore_paths=["lib/", "test/", "script/"],
        require_public=True,
        require_external=True,
    )
    assert (result.total_public + result.total_external) > 0
    assert result.documented_public == result.total_public
    assert result.documented_external == result.total_external
    assert result.passed is True
