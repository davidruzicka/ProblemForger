"""Enforce provider-neutral imports in core and ports."""

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
# These standard-library modules still violate provider-neutral boundaries.
FORBIDDEN_STDLIB_IMPORT_PREFIXES = (
    "sqlite3",
    "_sqlite3",
    "importlib",
    "builtins",
)


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


def _is_forbidden(module: str) -> bool:
    """Allow stdlib and core/ports imports; reject providers and upper layers."""
    if not module:
        return False

    if any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_STDLIB_IMPORT_PREFIXES
    ):
        return True

    if module.partition(".")[0] in sys.stdlib_module_names:
        return False

    return not any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in PROVIDER_NEUTRAL_ALLOWED_IMPORT_PREFIXES
    )


def _is_dynamic_import(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "__import__"


def find_violations(core_root: Path, package_root: Path) -> list[str]:
    """Return static import violations in core and provider-neutral ports."""
    if not core_root.is_dir():
        return [f"{core_root}: core package directory does not exist"]

    files = sorted(core_root.rglob("*.py"))
    if not files:
        return [f"{core_root}: no Python files found"]
    ports_root = package_root / "ports"
    if ports_root.is_dir():
        files.extend(sorted(ports_root.rglob("*.py")))

    violations: list[str] = []
    for path in files:
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
                elif _is_forbidden(target):
                    violations.append(f"{path}: forbidden import {target!r}")
            if _is_dynamic_import(node):
                violations.append(
                    f"{path}: dynamic import is forbidden in core and ports"
                )

    return violations


def main(core_root: Path = CORE_ROOT, package_root: Path = PACKAGE_ROOT) -> int:
    violations = find_violations(core_root, package_root)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("Core/ports dependency boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
