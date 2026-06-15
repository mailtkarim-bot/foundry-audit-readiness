"""NatSpec completeness checker for Solidity functions.

Uses AST parsing via solc when available, falls back to regex for quick checks.
"""

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional

from audit_readiness.utils import find_solidity_files, logger, run_command


@dataclass
class NatSpecResult:
    total_public: int = 0
    documented_public: int = 0
    total_external: int = 0
    documented_external: int = 0
    missing: List[Tuple[str, str, int]] = field(default_factory=list)
    passed: bool = False
    method: str = "regex"  # "ast" or "regex"


def _documentation_has_natspec(documentation) -> bool:
    """Return True if the AST documentation node contains NatSpec content."""
    if documentation is None:
        return False
    if isinstance(documentation, str):
        return bool(documentation.strip())
    if isinstance(documentation, dict):
        text = documentation.get("text", "")
        return bool(str(text).strip())
    return False


def _detect_solc_version(sol_file: Path) -> Optional[str]:
    """Extract the pragma solidity version from a Solidity file."""
    try:
        content = sol_file.read_text(encoding="utf-8", errors="ignore")
        # Match pragma solidity with exact/pinned version: pragma solidity 0.8.28;
        match = re.search(r"pragma\s+solidity\s+([\d.]+)", content)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _find_matching_solc(sol_file: Path) -> Optional[str]:
    """Find a solc binary matching the file's pragma version.

    Foundry downloads compilers to ~/.local/share/svm/<version>/solc-<version>.
    Falls back to the system `solc` if no matching version is installed.
    """
    version = _detect_solc_version(sol_file)
    if version:
        svm_path = Path.home() / ".local" / "share" / "svm" / version / f"solc-{version}"
        if svm_path.exists() and svm_path.is_file():
            return str(svm_path)
    system_solc = shutil.which("solc")
    return system_solc


def _try_ast_parse(project_path: Path, sol_file: Path) -> Optional[List[Tuple[str, str, bool, int]]]:
    """Try to use solc AST for reliable parsing. Returns None if solc unavailable.

    Uses solc's standard-json interface so Foundry remappings are respected.
    """
    solc_path = _find_matching_solc(sol_file)
    if not solc_path:
        return None

    try:
        remappings = []
        forge = shutil.which("forge")
        if forge:
            rem_result = run_command(["forge", "remappings"], cwd=project_path, capture=True)
            if rem_result.returncode == 0 and rem_result.stdout:
                remappings = [r.strip() for r in rem_result.stdout.strip().splitlines() if r.strip()]

        standard_input = {
            "language": "Solidity",
            "sources": {
                str(sol_file): {"urls": [str(sol_file)]}
            },
            "settings": {
                "remappings": remappings,
                "outputSelection": {"*": {"*": [], "": ["ast"]}},
            },
        }

        result = run_command(
            [solc_path, "--standard-json"],
            cwd=project_path,
            capture=True,
            input=json.dumps(standard_input),
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        errors = [e for e in data.get("errors", []) if e.get("severity") == "error"]
        if errors:
            return None

        source_data = data.get("sources", {}).get(str(sol_file), {})
        ast_data = source_data.get("ast", {})
        if not ast_data:
            return None

        return _extract_functions_from_ast(ast_data)
    except Exception as e:
        logger.debug(f"AST parsing failed for {sol_file}: {e}")
        return None


def _extract_functions_from_ast(ast_data: dict) -> List[Tuple[str, str, bool, int]]:
    """Extract function definitions with NatSpec from AST."""
    functions = []

    def walk_nodes(node):
        if isinstance(node, dict):
            if node.get("nodeType") == "FunctionDefinition":
                visibility = node.get("visibility", "")
                name = node.get("name", "")
                src = node.get("src", "")
                line = 0
                if src:
                    try:
                        # src format: "offset:length:file_id"
                        # line info may be in a separate source map
                        line = int(src.split(":")[0])  # Use offset as fallback
                    except (ValueError, IndexError):
                        pass
                # Try to get actual line number from source locations if available
                if "src" in node and node["src"]:
                    try:
                        parts = node["src"].split(":")
                        if len(parts) >= 3:
                            # The third element is the file ID, not line
                            # Lines require source maps which we may not have
                            pass
                    except:
                        pass
                has_natspec = _documentation_has_natspec(node.get("documentation"))
                if visibility in ("public", "external"):
                    functions.append((name, visibility, has_natspec, line))
            for child in node.values():
                if isinstance(child, (dict, list)):
                    walk_nodes(child)
        elif isinstance(node, list):
            for item in node:
                walk_nodes(item)

    walk_nodes(ast_data)
    return functions


def _find_natspec_blocks(content: str) -> List[Tuple[int, int, str]]:
    """Find NatSpec comment blocks and return (start, end, text) tuples."""
    blocks = []

    # /** ... */ blocks
    for match in re.finditer(r"/\*\*.*?\*/", content, re.DOTALL):
        blocks.append((match.start(), match.end(), match.group(0)))

    # /// line blocks (consecutive lines starting with ///)
    for match in re.finditer(r"(?:^[ \t]*///.*\n?)+", content, re.MULTILINE):
        blocks.append((match.start(), match.end(), match.group(0)))

    blocks.sort()
    return blocks


def _is_documented(blocks: List[Tuple[int, int, str]], func_start: int) -> bool:
    """Return True if a NatSpec block directly precedes the function."""
    if not blocks:
        return False

    # Find the closest block ending before the function starts
    preceding = [b for b in blocks if b[1] <= func_start]
    if not preceding:
        return False

    block = preceding[-1]
    between = content_between = func_start - block[1]
    if between > 250:
        return False

    text = block[2]
    # Empty comment blocks do not count
    cleaned = re.sub(r"/\*\*|\*/|///|\*|/", "", text).strip()
    return bool(cleaned)


def _regex_parse(file_path: Path) -> List[Tuple[str, str, bool, int]]:
    """Fallback regex-based parser."""
    content = file_path.read_text(encoding="utf-8")
    blocks = _find_natspec_blocks(content)

    # Match function declarations spanning multiple lines, ending with { or ; or returns clause
    func_pattern = re.compile(
        r"function\s+(\w+)\s*\([^)]*\)[^{;]*?\b(public|external)\b[^{;]*?(?:\{|;|returns)",
        re.DOTALL,
    )

    results = []
    for match in func_pattern.finditer(content):
        func_name = match.group(1)
        visibility = match.group(2)
        line = content[: match.start()].count("\n") + 1
        has_natspec = _is_documented(blocks, match.start())
        results.append((func_name, visibility, has_natspec, line))

    return results


def check_natspec_completeness(
    project_path: Path,
    ignore_paths: List[str],
    require_public: bool = True,
    require_external: bool = True,
) -> NatSpecResult:
    """Check that all public/external functions have NatSpec documentation."""
    sol_files = find_solidity_files(project_path, ignore_paths)

    total_public = 0
    documented_public = 0
    total_external = 0
    documented_external = 0
    missing = []
    method_used = "regex"

    for sol_file in sol_files:
        # Try AST first, fallback to regex
        ast_result = _try_ast_parse(project_path, sol_file)
        if ast_result is not None:
            functions = ast_result
            method_used = "ast"
        else:
            functions = _regex_parse(sol_file)

        rel_path = sol_file.relative_to(project_path)
        for func_name, visibility, has_natspec, line in functions:
            if visibility == "public":
                total_public += 1
                if has_natspec:
                    documented_public += 1
                else:
                    missing.append((str(rel_path), func_name, line))
            elif visibility == "external":
                total_external += 1
                if has_natspec:
                    documented_external += 1
                else:
                    missing.append((str(rel_path), func_name, line))

    public_ok = not require_public or (total_public == 0 or documented_public == total_public)
    external_ok = not require_external or (total_external == 0 or documented_external == total_external)

    return NatSpecResult(
        total_public=total_public,
        documented_public=documented_public,
        total_external=total_external,
        documented_external=documented_external,
        missing=missing,
        passed=public_ok and external_ok,
        method=method_used,
    )
