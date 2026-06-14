"""Utility helpers and logging."""

import subprocess
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.logging import RichHandler
import logging

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger("audit_readiness")


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    capture: bool = True,
    check: bool = False,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """Run a shell command with logging."""
    logger.info(f"Running: {' '.join(cmd)}")
    kwargs = {
        "cwd": cwd,
        "capture_output": capture,
        "text": True,
        "check": check,
    }
    if env is not None:
        kwargs["env"] = env
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0 and capture:
        logger.warning(f"Command failed: {result.stderr[:500]}")
    return result


def find_solidity_files(project_path: Path, ignore_paths: List[str]) -> List[Path]:
    """Find all .sol files excluding ignored paths."""
    files = []
    for sol_file in project_path.rglob("*.sol"):
        if not sol_file.is_file():
            continue
        if any(ignore in str(sol_file) for ignore in ignore_paths):
            continue
        files.append(sol_file)
    return sorted(files)


def format_percentage(value: float) -> str:
    return f"{value:.1f}%"
