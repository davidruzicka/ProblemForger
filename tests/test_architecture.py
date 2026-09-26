"""Architecture-boundary regression tests."""

from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stderr, redirect_stdout
import importlib
from io import StringIO
import unittest

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

    def test_rejects_unapproved_providers_and_upper_layers(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "bad.py").write_text(
                "import psycopg\n"
                "import openai\n"
                "import sqlite3\n"
                "import _sqlite3\n"
                "from problemforger.config import ProviderConfig\n"
                "from problemforger.application import submit\n"
                "from problemforger.service import start\n"
                "from ..config import ProviderConfig\n"
                "from ..application import submit\n"
                "from ..service import start\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        expected_imports = (
            "psycopg",
            "openai",
            "sqlite3",
            "_sqlite3",
            "problemforger.config",
            "problemforger.application",
            "problemforger.service",
        )
        self.assertEqual(10, len(violations))
        for module in expected_imports:
            with self.subTest(module=module):
                self.assertTrue(any(module in item for item in violations))

    def test_rejects_provider_dependencies_inside_ports(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            ports_root = package_root / "ports"
            core_root.mkdir(parents=True)
            ports_root.mkdir()
            (core_root / "governor.py").write_text(
                "from problemforger.ports import EventStore\n",
                encoding="utf-8",
            )
            (ports_root / "__init__.py").write_text(
                "from psycopg import Connection\n",
                encoding="utf-8",
            )
            (ports_root / "event_store.py").write_text(
                "import json\n"
                "from ..core.events import GraphEvent\n"
                "from .telemetry import TelemetrySink\n"
                "from ..modules.persistence.sqlite import SqliteEventStore\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(2, len(violations))
        self.assertTrue(any("psycopg" in item for item in violations))
        self.assertTrue(
            any(
                "problemforger.modules.persistence.sqlite" in item
                for item in violations
            )
        )

    def test_rejects_ui_framework_stdlib_imports_in_core_and_ports(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            ports_root = package_root / "ports"
            core_root.mkdir(parents=True)
            ports_root.mkdir()
            (core_root / "ui.py").write_text(
                "import tkinter\n",
                encoding="utf-8",
            )
            (ports_root / "ui.py").write_text(
                "from tkinter import ttk\n"
                "import _tkinter\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(3, len(violations))
        for imported_module in ("tkinter", "tkinter.ttk", "_tkinter"):
            with self.subTest(imported_module=imported_module):
                self.assertTrue(
                    any(
                        f"forbidden import '{imported_module}'" in item
                        for item in violations
                    )
                )

    def test_rejects_stdlib_persistence_providers_in_architecture_layers(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            ports_root = package_root / "ports"
            application_root = package_root / "application" / "commands"
            core_root.mkdir(parents=True)
            ports_root.mkdir()
            application_root.mkdir(parents=True)
            (core_root / "store.py").write_text(
                "import dbm\n"
                "from dbm.gnu import open as open_dbm\n",
                encoding="utf-8",
            )
            (ports_root / "store.py").write_text(
                "import shelve\n"
                "import _dbm\n",
                encoding="utf-8",
            )
            (application_root / "store.py").write_text(
                "import _gdbm\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        expected_imports = ("dbm", "dbm.gnu.open", "shelve", "_dbm", "_gdbm")
        self.assertEqual(len(expected_imports), len(violations))
        for imported_module in expected_imports:
            with self.subTest(imported_module=imported_module):
                self.assertTrue(
                    any(
                        f"forbidden import '{imported_module}'" in item
                        for item in violations
                    )
                )

    def test_rejects_unapproved_stdlib_transport_and_ui_modules(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            ports_root = package_root / "ports"
            application_root = package_root / "application" / "commands"
            core_root.mkdir(parents=True)
            ports_root.mkdir()
            application_root.mkdir(parents=True)
            (core_root / "server.py").write_text(
                "import http.server\n"
                "from http import server\n",
                encoding="utf-8",
            )
            (ports_root / "server.py").write_text(
                "import socketserver\n"
                "from wsgiref.simple_server import make_server\n",
                encoding="utf-8",
            )
            (application_root / "terminal_ui.py").write_text(
                "import curses\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        expected_imports = (
            "socketserver",
            "wsgiref.simple_server.make_server",
            "curses",
        )
        self.assertEqual(len(expected_imports) + 2, len(violations))
        self.assertEqual(
            2,
            sum(item.endswith("forbidden import 'http.server'") for item in violations),
        )
        for imported_module in expected_imports:
            with self.subTest(imported_module=imported_module):
                self.assertTrue(
                    any(
                        f"forbidden import '{imported_module}'" in item
                        for item in violations
                    )
                )

    def test_rejects_provider_dependencies_inside_application_use_cases(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            ports_root = package_root / "ports"
            commands_root = package_root / "application" / "commands"
            queries_root = package_root / "application" / "queries"
            core_root.mkdir(parents=True)
            ports_root.mkdir()
            commands_root.mkdir(parents=True)
            queries_root.mkdir()
            (core_root / "governor.py").write_text(
                "from problemforger.ports import EventStore\n",
                encoding="utf-8",
            )
            (commands_root / "submit.py").write_text(
                "import sqlite3\n"
                "import harnessx.agent\n"
                "from problemforger.modules.persistence.sqlite import "
                "SqliteEventStore\n",
                encoding="utf-8",
            )
            (queries_root / "read_graph.py").write_text(
                "import json\n"
                "from problemforger.application.commands.submit import SubmitProposal\n"
                "from problemforger.core.events import GraphEvent\n"
                "from problemforger.ports import EventStore\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(3, len(violations))
        self.assertTrue(any("sqlite3" in item for item in violations))
        self.assertTrue(any("harnessx.agent" in item for item in violations))
        self.assertTrue(
            any(
                "problemforger.modules.persistence.sqlite" in item
                for item in violations
            )
        )

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
                "from __future__ import annotations\n"
                "from collections.abc import Mapping\n"
                "from dataclasses import dataclass\n"
                "from typing import Protocol\n"
                "import json\n"
                "from ..ports import EventStore\n"
                "from .models import Node\n"
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
                "importlib.import_module('problemforger.adapters.harnessx')\n"
                "from importlib import import_module as load\n"
                "load('problemforger.adapters.harnessx')\n"
                "loader = __import__\n"
                "loader('problemforger.modules.persistence.sqlite')\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(4, len(violations))
        self.assertTrue(any("importlib" in item for item in violations))
        self.assertEqual(
            2,
            sum("dynamic import" in item for item in violations),
        )

    def test_allows_unrelated_methods_named_like_import_functions(self):
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "ordinary.py").write_text(
                "class Mapper:\n"
                "    def import_module(self, name): return name\n"
                "    def __import__(self, name): return name\n"
                "mapper = Mapper()\n"
                "mapper.import_module('artifact')\n"
                "mapper.__import__('artifact')\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual([], violations)

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
            (core_root / "also_bad.py").write_text(
                "from ...modules import provider\n"
                "from ... import modules\n",
                encoding="utf-8",
            )

            violations = find_violations(core_root, package_root)

        self.assertEqual(3, len(violations))
        self.assertTrue(
            all("relative import escapes package root" in item for item in violations)
        )

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
        with TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "src" / "problemforger"
            core_root = package_root / "core"
            core_root.mkdir(parents=True)
            (core_root / "valid.py").write_text("import json\n", encoding="utf-8")

            success = StringIO()
            with redirect_stdout(success):
                self.assertEqual(0, main(core_root, package_root))
            self.assertIn("check passed", success.getvalue())

            (core_root / "invalid.py").write_text("import psycopg\n", encoding="utf-8")
            failure = StringIO()
            with redirect_stderr(failure):
                self.assertEqual(1, main(core_root, package_root))
            self.assertIn("forbidden import 'psycopg'", failure.getvalue())


if __name__ == "__main__":
    unittest.main()
