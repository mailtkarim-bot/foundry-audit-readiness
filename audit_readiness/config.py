"""Configuration and threshold management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

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
    tools: List[str] = field(default_factory=lambda: ["slither"])
    ignore_paths: List[str] = field(
        default_factory=lambda: ["lib/", "test/", "script/", "node_modules/"]
    )


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
        return cls(
            coverage=CoverageThresholds(**data.get("coverage", {})),
            invariants=InvariantConfig(**data.get("invariants", {})),
            static_analysis=StaticAnalysisConfig(**data.get("static_analysis", {})),
            natspec=NatSpecConfig(**data.get("natspec", {})),
            gas=GasConfig(**data.get("gas", {})),
        )

    @classmethod
    def from_project(cls, project_path: Path) -> "Config":
        config_path = project_path / "audit-readiness.yaml"
        return cls.from_yaml(config_path)
