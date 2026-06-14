"""Configuration and threshold management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class CoverageThresholds:
    line: int = 90
    branch: int = 85
    function: int = 100


@dataclass
class InvariantConfig:
    min_functions: int = 0  # 0 = optional, not blocking by default
    runs: int = 10_000


@dataclass
class StaticAnalysisConfig:
    # Default: 3 fast, reliable tools. Users can add more via --tools or YAML.
    # Tiers: [slither,solhint,semgrep] = fast (~2min)
    #        +aderyn+mythril = advanced (~8min)
    #        +halmos+smtchecker = deep (~15min)
    tools: List[str] = field(default_factory=lambda: [
        "slither", "solhint", "semgrep"
    ])
    ignore_paths: List[str] = field(
        default_factory=lambda: ["lib/", "test/", "script/", "node_modules/"]
    )
    timeouts: Dict[str, int] = field(default_factory=lambda: {
        "slither": 300,       # 5 min
        "aderyn": 120,        # 2 min
        "solhint": 60,        # 1 min
        "semgrep": 120,       # 2 min
        "mythril": 600,       # 10 min (symbolic execution is slow)
        "halmos": 300,        # 5 min
        "smtchecker": 180,    # 3 min
    })


@dataclass
class NatSpecConfig:
    require_public: bool = True
    require_external: bool = True


@dataclass
class GasConfig:
    compare_with_baseline: bool = True
    max_increase_percent: float = 5.0


@dataclass
class Config:
    coverage: CoverageThresholds = field(default_factory=CoverageThresholds)
    invariants: InvariantConfig = field(default_factory=InvariantConfig)
    static_analysis: StaticAnalysisConfig = field(default_factory=StaticAnalysisConfig)
    natspec: NatSpecConfig = field(default_factory=NatSpecConfig)
    gas: GasConfig = field(default_factory=GasConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        # Parse static_analysis with defaults
        sa_data = data.get("static_analysis", {})
        sa_tools = sa_data.get("tools", StaticAnalysisConfig().tools)
        sa_ignore = sa_data.get("ignore_paths", StaticAnalysisConfig().ignore_paths)
        sa_timeouts = {**StaticAnalysisConfig().timeouts, **sa_data.get("timeouts", {})}
        
        return cls(
            coverage=CoverageThresholds(**data.get("coverage", {})),
            invariants=InvariantConfig(**data.get("invariants", {})),
            static_analysis=StaticAnalysisConfig(
                tools=sa_tools,
                ignore_paths=sa_ignore,
                timeouts=sa_timeouts,
            ),
            natspec=NatSpecConfig(**data.get("natspec", {})),
            gas=GasConfig(**data.get("gas", {})),
        )

    @classmethod
    def from_project(cls, project_path: Path) -> "Config":
        config_path = project_path / "audit-readiness.yaml"
        return cls.from_yaml(config_path)
