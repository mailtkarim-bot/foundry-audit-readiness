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


def _try_ast_parse(project_path: Path, sol_file: Path) -> Optional[List[Tuple[str, str, bool, int]]]:
    """Try to use solc AST for reliable parsing. Returns None if solc unavailable."""
    if not shutil.which("solc"):
        return None

    try:
        result = run_command(
            ["solc", "--ast-compact-json", str(sol_file)],
            cwd=project_path,
            capture=True,
        )
        if result.returncode != 0:
            return None

        ast_data = json.loads(result.stdout)
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
                            line = int(src.split(":")[2])
                        except (ValueError, IndexError):
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
    except Exception as e:
        logger.debug(f"AST parsing failed for {sol_file}: {e}")
        return None


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
