"""Architecture-boundary regression tests."""

from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stderr, redirect_stdout
import importlib
from io import StringIO
import unittest
from unittest.mock import patch

from scripts.check_architecture import find_violations, main


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "problemforger"


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_package_layers_import_without_harness_or_provider_dependencies(self):
        for module in (
            "problemforger",
            "problemforger.core",
            "problemforger.application",
            "problemforger.ports",
            "problemforger.modules",
            "problemforger.config",
            "problemforger.service",
        ):
            with self.subTest(module=module):
                self.assertIsNotNone(importlib.import_module(module))

    def test_repository_core_has_no_forbidden_dependencies(self):
        self.assertEqual(
            [],
            find_violations(PACKAGE_ROOT / "core", PACKAGE_ROOT),
        )

    def test_rejects_provider_and_harness_imports(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "__init__.py").write_text("", encoding="utf-8")
            (core_root / "bad.py").write_text(
                "import problemforger.modules.persistence.sqlite\n"
                "from problemforger.adapters import harnessx\n"
                "from problemforger.modules import *\n"
                "import sqlite3\n"
                "import harnessx.agent\n"
                "import pi\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(6, len(violations))
        self.assertTrue(
            any("problemforger.modules.persistence.sqlite" in item for item in violations)
        )
        self.assertTrue(
            any("problemforger.adapters.harnessx" in item for item in violations)
        )
        self.assertTrue(any("sqlite3" in item for item in violations))
        self.assertTrue(any("harnessx.agent" in item for item in violations))
        self.assertTrue(any("pi" in item for item in violations))
        self.assertTrue(any("problemforger.modules'" in item for item in violations))

    def test_resolves_relative_provider_and_adapter_imports(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "__init__.py").write_text("", encoding="utf-8")
            (core_root / "nested.py").write_text(
                "from ..modules.persistence.sqlite import SqliteEventStore\n"
                "from .. import adapters\n",
                encoding="utf-8",
            )
            (core_root / "allowed.py").write_text(
                "import json\n"
                "from ..ports import EventStore\n"
                "def read(): return json.loads('{}')\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(2, len(violations))
        self.assertTrue(any("problemforger.modules.persistence.sqlite" in item for item in violations))
        self.assertTrue(any("problemforger.adapters" in item for item in violations))

    def test_rejects_dynamic_imports_and_importlib(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "__init__.py").write_text("", encoding="utf-8")
            (core_root / "bad.py").write_text(
                "import importlib\n"
                "__import__('problemforger.modules.persistence.sqlite')\n"
                "importlib.import_module('problemforger.adapters.harnessx')\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(3, len(violations))
        self.assertTrue(any("importlib" in item for item in violations))
        self.assertTrue(any("dynamic import" in item for item in violations))

    def test_reports_invalid_python_instead_of_skipping_it(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "bad.py").write_text("from = invalid\n", encoding="utf-8")

            violations = find_violations(core_root, package_root)

        self.assertEqual(1, len(violations))
        self.assertIn("invalid Python syntax", violations[0])

    def test_rejects_relative_import_that_escapes_package_root(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "bad.py").write_text(
                "from ....modules import provider\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(1, len(violations))
        self.assertIn("relative import escapes package root", violations[0])

    def test_reports_missing_or_empty_core_packages(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            missing = find_violations(package_root / "core", package_root)
            empty_core = package_root / "core"
            empty_core.mkdir(parents=True)
            empty = find_violations(empty_core, package_root)

        self.assertIn("core package directory does not exist", missing[0])
        self.assertIn("no Python files found", empty[0])

    def test_command_reports_success_and_failure(self):
        success = StringIO()
        with patch("scripts.check_architecture.find_violations", return_value=[]):
            with redirect_stdout(success):
                self.assertEqual(0, main())
        self.assertIn("check passed", success.getvalue())

        failure = StringIO()
        with patch(
            "scripts.check_architecture.find_violations",
            return_value=["forbidden import"],
        ):
            with redirect_stderr(failure):
                self.assertEqual(1, main())
        self.assertIn("forbidden import", failure.getvalue())


if __name__ == "__main__":
    unittest.main()
