"""Enforce dependency boundaries for core, ports, and application use cases."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "problemforger"
CORE_ROOT = PACKAGE_ROOT / "core"
PROVIDER_NEUTRAL_ALLOWED_IMPORT_PREFIXES = (
    "problemforger.core",
    "problemforger.ports",
)
APPLICATION_USE_CASE_ALLOWED_IMPORT_PREFIXES = (
    "problemforger.application",
    *PROVIDER_NEUTRAL_ALLOWED_IMPORT_PREFIXES,
)
# Keep architectural layers on a reviewed, provider-neutral stdlib surface.
PROVIDER_NEUTRAL_ALLOWED_STDLIB_MODULES = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "copy",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "heapq",
        "itertools",
        "json",
        "math",
        "numbers",
        "operator",
        "re",
        "statistics",
        "string",
        "typing",
        "uuid",
    }
)
CORE_PORTS_ALLOWED_STDLIB_MODULES = PROVIDER_NEUTRAL_ALLOWED_STDLIB_MODULES
APPLICATION_USE_CASE_ALLOWED_STDLIB_MODULES = PROVIDER_NEUTRAL_ALLOWED_STDLIB_MODULES


def _package_name(path: Path, package_root: Path) -> str:
    parts = path.relative_to(package_root.parent).with_suffix("").parts
    return ".".join(parts[:-1])


def _resolve_import(module: str | None, level: int, package: str) -> str | None:
    if level == 0:
        return module or ""

    parts = package.split(".") if package else []
    keep = len(parts) - level + 1
    if keep <= 0:
        return None
    return ".".join([*parts[:keep], *([module] if module else [])])


def _import_targets(node: ast.AST, package: str) -> list[str | None]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []

    base = _resolve_import(node.module, node.level, package)
    if base is None:
        return [None]
    if not base:
        return []
    if any(alias.name == "*" for alias in node.names):
        return [base]
    return [f"{base}.{alias.name}" for alias in node.names]


def _is_forbidden(
    module: str,
    allowed_import_prefixes: tuple[str, ...],
    allowed_stdlib_modules: frozenset[str],
) -> bool:
    """Allow reviewed stdlib roots and layer imports; reject other dependencies."""
    if not module:
        return False

    top_level_module = module.partition(".")[0]
    if top_level_module in sys.stdlib_module_names:
        return top_level_module not in allowed_stdlib_modules

    return not any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in allowed_import_prefixes
    )


def _is_dynamic_import(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "__import__"


def find_violations(core_root: Path, package_root: Path) -> list[str]:
    """Return import violations in core, ports, and application use cases."""
    if not core_root.is_dir():
        return [f"{core_root}: core package directory does not exist"]

    core_files = sorted(core_root.rglob("*.py"))
    if not core_files:
        return [f"{core_root}: no Python files found"]

    files: list[tuple[Path, tuple[str, ...], frozenset[str]]] = [
        (
            path,
            PROVIDER_NEUTRAL_ALLOWED_IMPORT_PREFIXES,
            CORE_PORTS_ALLOWED_STDLIB_MODULES,
        )
        for path in core_files
    ]
    ports_root = package_root / "ports"
    if ports_root.is_dir():
        files.extend(
            (
                path,
                PROVIDER_NEUTRAL_ALLOWED_IMPORT_PREFIXES,
                CORE_PORTS_ALLOWED_STDLIB_MODULES,
            )
            for path in sorted(ports_root.rglob("*.py"))
        )
    application_root = package_root / "application"
    if application_root.is_dir():
        files.extend(
            (
                path,
                APPLICATION_USE_CASE_ALLOWED_IMPORT_PREFIXES,
                APPLICATION_USE_CASE_ALLOWED_STDLIB_MODULES,
            )
            for path in sorted(application_root.rglob("*.py"))
        )

    violations: list[str] = []
    for path, allowed_import_prefixes, allowed_stdlib_modules in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            violations.append(
                f"{path}: invalid Python syntax at line {error.lineno}: {error.msg}"
            )
            continue

        package = _package_name(path, package_root)
        for node in ast.walk(tree):
            for target in _import_targets(node, package):
                if target is None:
                    violations.append(f"{path}: relative import escapes package root")
                elif _is_forbidden(
                    target,
                    allowed_import_prefixes,
                    allowed_stdlib_modules,
                ):
                    violations.append(f"{path}: forbidden import {target!r}")
            if _is_dynamic_import(node):
                violations.append(
                    f"{path}: dynamic import is forbidden in provider-neutral layers"
                )

    return violations


def main(core_root: Path = CORE_ROOT, package_root: Path = PACKAGE_ROOT) -> int:
    violations = find_violations(core_root, package_root)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("Provider-neutral dependency boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
