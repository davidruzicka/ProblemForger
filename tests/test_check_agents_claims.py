"""Regression tests for the AGENTS.md claim checker.

A false positive is worse than a missed finding here: a check that fails on correct
documentation gets disabled. Each verdict is therefore tested in both directions.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import subprocess
import unittest
from unittest import mock

from scripts import check_agents_claims
from scripts.check_agents_claims import collect, main


ROOT = Path(__file__).resolve().parents[1]


def run_main(*argv):
    """Run the CLI in-process and return (exit code, stdout, stderr)."""
    out, err = StringIO(), StringIO()
    code = 0
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(list(argv))
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class ClaimCheckerTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        # git must not walk up into a repository that happens to contain the temp directory
        environment = mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.repo.parent)})
        environment.start()
        self.addCleanup(environment.stop)
        (self.repo / "src" / "pkg").mkdir(parents=True)
        (self.repo / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "src" / "pkg" / "store.py").write_text("", encoding="utf-8")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "guide.md").write_text("", encoding="utf-8")
        (self.repo / "node_modules" / "dep").mkdir(parents=True)
        (self.repo / "node_modules" / "dep" / "hidden.md").write_text("", encoding="utf-8")
        check_agents_claims.name_index.cache_clear()
        check_agents_claims.git_paths.cache_clear()

    def verdicts(self, text, doc_dir=None):
        doc = (doc_dir or self.repo) / "AGENTS.md"
        doc.write_text(text, encoding="utf-8")
        return {(claim["kind"], claim["quote"]): claim["verdict"] for claim in collect(doc, self.repo)}

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def test_scoped_ignored_path(self):
        self.git("init", "-q")
        (self.repo / ".gitignore").write_text("src/pkg/generated/\n", encoding="utf-8")
        verdicts = self.verdicts("Read `generated/out.md`.\n", self.repo / "src" / "pkg")
        self.assertEqual("UNRESOLVED", verdicts[("path", "generated/out.md")])

    def test_ignored_generated_package(self):
        self.git("init", "-q")
        (self.repo / ".gitignore").write_text("src/pkg/generated/\n", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom pkg.generated import X\n```\n")
        self.assertEqual("UNRESOLVED", verdicts[("import", "from pkg.generated import")])

    def test_space_containing_code_path(self):
        verdicts = self.verdicts("Read `docs/missing guide.md`.\n")
        self.assertEqual("BREAKS-ON-USE", verdicts.get(("path", "docs/missing guide.md")))
        (self.repo / "docs" / "real guide.md").write_text("", encoding="utf-8")
        verdicts = self.verdicts("Read `docs/real guide.md`.\n")
        self.assertEqual("TRUE", verdicts[("path", "docs/real guide.md")])

    def test_inline_command_is_advisory(self):
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts" / "check.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("Run `python scripts/check.py`.\n")
        self.assertEqual("UNRESOLVED", verdicts[("path", "python scripts/check.py")])

    def test_titled_markdown_path(self):
        verdicts = self.verdicts('Read [guide](docs/missing.md "Guide").\n')
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])

    def test_deployment_context_stops_at_sentence_boundary(self):
        verdicts = self.verdicts("Read `docs/missing.md`. Deploy to production afterwards.\n")
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])

    def test_general_extensions_require_path_shape(self):
        verdicts = self.verdicts(
            "Read `config/missing.ini`, `schema/missing.sql`, `web/missing.html`, "
            "and `types/missing.customextension`. Versions `3.12` and hosts `example.com`, `example.com/v1.2`.\n"
        )
        for path in ("config/missing.ini", "schema/missing.sql", "web/missing.html",
                     "types/missing.customextension"):
            self.assertEqual("BREAKS-ON-USE", verdicts[("path", path)])
        self.assertNotIn(("path", "3.12"), verdicts)
        self.assertNotIn(("path", "example.com"), verdicts)
        self.assertNotIn(("path", "example.com/v1.2"), verdicts)

    def test_python_fence_variants(self):
        for opening, closing in (("````python", "````"), ("~~~python", "~~~"),
                                 ("```python title=Example", "```")):
            with self.subTest(opening=opening):
                verdicts = self.verdicts(f"{opening}\nfrom pkg.missing import X\n{closing}\n")
                self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.missing import")])

    def test_fence_closer_matches_type_length_and_has_no_info(self):
        text = "````python\n```\n~~~~\n````python\nfrom pkg.missing import X\n`````\n"
        blocks = list(check_agents_claims.fenced_blocks(text))
        self.assertEqual(1, len(blocks))
        self.assertEqual(("python", 1, 6), blocks[0][:3])
        self.assertIn("from pkg.missing import X", blocks[0][3])

    def test_backtick_fence_info_cannot_contain_backticks(self):
        self.assertEqual([], list(check_agents_claims.fenced_blocks("```python `example`\n")))

    def test_unclosed_python_fence_extends_to_eof(self):
        verdicts = self.verdicts("~~~python\nfrom pkg.missing import X\n")
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.missing import")])

    def test_suffix_prohibition_is_advisory_and_clause_bounded(self):
        verdicts = self.verdicts(
            "`secrets/key.json` must not be committed.\n"
            "Read `docs/missing.md`. Do not change production files.\n"
            "Read `docs/other.md`; never modify secrets.\n"
        )
        self.assertEqual("NEEDS-AI", verdicts[("path", "secrets/key.json")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/other.md")])
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(1, code)
        self.verdicts("`secrets/key.json` must not be committed.\n")
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_directory_and_long_extension_links(self):
        verdicts = self.verdicts(
            'Read [missing](docs/missing/), [schema](schema/missing.proto#message "Schema"), '
            '[guide](docs/#overview "Guide"), [long](types/missing.customextension), '
            '[web](https://example.com/schema.proto).\n'
        )
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing/")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "schema/missing.proto")])
        self.assertEqual("TRUE", verdicts[("path", "docs/")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "types/missing.customextension")])
        self.assertNotIn(("path", "https://example.com/schema.proto"), verdicts)

    def test_reference_link_definitions_are_checked(self):
        verdicts = self.verdicts(
            '[the guide][guide] and [existing][present].\n'
            '[guide]: docs/missing.md#setup "Guide"\n'
            "[present]: docs/guide.md#setup 'Existing'\n"
            '[external]: https://example.com/missing.md "External"\n'
        )
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])
        self.assertEqual("TRUE", verdicts[("path", "docs/guide.md")])
        self.assertNotIn(("path", "https://example.com/missing.md"), verdicts)
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(1, code)
        self.verdicts('[the guide][guide]\n[guide]: docs/guide.md#setup "Guide"\n')
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_angle_bracket_markdown_destinations(self):
        for text in (
            '[guide](<docs/missing.md>) and [existing](<docs/guide.md#setup> "Guide").\n'
            '[external](<https://example.com/missing.md>).\n',
            '[guide]: <docs/missing.md>\n'
            "[existing]: <docs/guide.md#setup> 'Guide'\n"
            '[external]: <https://example.com/missing.md>\n',
        ):
            with self.subTest(text=text):
                verdicts = self.verdicts(text)
                self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])
                self.assertEqual("TRUE", verdicts[("path", "docs/guide.md")])
                self.assertNotIn(("path", "https://example.com/missing.md"), verdicts)
                code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
                self.assertEqual(1, code)
        self.verdicts('[guide](<docs/guide.md>)\n[guide]: <docs/guide.md>\n')
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_markdown_destination_angle_brackets_must_be_paired(self):
        verdicts = self.verdicts('[guide](<docs/missing.md)\n[guide]: <docs/missing.md\n')
        self.assertNotIn(("path", "docs/missing.md"), verdicts)

    def test_spaced_angle_bracket_markdown_destinations(self):
        (self.repo / "docs" / "real guide (v1).md").write_text("", encoding="utf-8")
        for text in (
            '[missing](<docs/missing guide.md>) '
            '[existing](<docs/real guide (v1).md#setup> "Guide") '
            '[external](<https://example.com/missing.md> "External")\n',
            '[missing]: <docs/missing guide.md> (Missing)\n'
            "[existing]: <docs/real guide (v1).md#setup> 'Existing'\n"
            '[external]: <https://example.com/missing.md> "External"\n',
        ):
            with self.subTest(text=text):
                verdicts = self.verdicts(text)
                self.assertEqual("BREAKS-ON-USE", verdicts.get(("path", "docs/missing guide.md")))
                self.assertEqual("TRUE", verdicts[("path", "docs/real guide (v1).md")])
                self.assertNotIn(("path", "https://example.com/missing.md"), verdicts)

    def test_angle_destination_fragments_allow_spaces_and_parentheses(self):
        for text in (
            "[missing](<docs/missing guide.md#section(with spaces)>)\n",
            "[missing]: <docs/missing guide.md#section(with spaces)>\n",
        ):
            with self.subTest(text=text):
                verdicts = self.verdicts(text)
                self.assertEqual("BREAKS-ON-USE", verdicts.get(("path", "docs/missing guide.md")))

    def test_explicit_spaced_markdown_path_is_not_an_inline_command(self):
        verdicts = self.verdicts("[missing](<missing dir/file.md>)\n")
        self.assertEqual("BREAKS-ON-USE", verdicts.get(("path", "missing dir/file.md")))

    def test_extensionless_markdown_destinations(self):
        (self.repo / "Makefile").write_text("", encoding="utf-8")
        (self.repo / "docs" / "check").write_text("", encoding="utf-8")
        for text in (
            '[build](Makefile) [script](docs/check) [missing](scripts/check) '
            '[parent](../README) [absent](MissingMakefile) '
            '[external](https://example.com/check) [anchor](#setup)\n',
            '[build]: <Makefile>\n[script]: docs/check "Check"\n'
            '[missing]: <scripts/check>\n[parent]: ../README\n[absent]: MissingMakefile\n'
            '[external]: mailto:user@example.com\n[anchor]: #setup\n',
        ):
            with self.subTest(text=text):
                verdicts = self.verdicts(text)
                self.assertEqual("TRUE", verdicts[("path", "Makefile")])
                self.assertEqual("TRUE", verdicts[("path", "docs/check")])
                self.assertEqual("BREAKS-ON-USE", verdicts[("path", "scripts/check")])
                self.assertEqual("BREAKS-ON-USE", verdicts[("path", "../README")])
                self.assertEqual("BREAKS-ON-USE", verdicts[("path", "MissingMakefile")])
                self.assertEqual(5, sum(kind == "path" for kind, _ in verdicts))
                code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
                self.assertEqual(1, code)
        self.verdicts('[build](Makefile)\n[script]: docs/check\n')
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_relative_imports_in_scoped_package(self):
        nested = self.repo / "src" / "pkg" / "nested"
        nested.mkdir()
        (nested / "__init__.py").write_text("", encoding="utf-8")
        (nested / "local.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "```python\nfrom .local import Thing\nfrom ..store import Store\n"
            "from .missing import Thing\nfrom ..missing import Thing\nimport json\n```\n",
            nested,
        )
        self.assertEqual("TRUE", verdicts[("import", "from .local import")])
        self.assertEqual("TRUE", verdicts[("import", "from ..store import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from .missing import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from ..missing import")])
        self.assertNotIn(("import", "import json"), verdicts)
        code, _, _ = run_main(str(nested / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(1, code)
        self.verdicts("```python\nfrom .local import Thing\nfrom ..store import Store\n```\n", nested)
        code, _, _ = run_main(str(nested / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_markdown_destinations_require_an_exact_path(self):
        (self.repo / "docs" / "Makefile").write_text("", encoding="utf-8")
        (self.repo / "tools" / "scripts").mkdir(parents=True)
        (self.repo / "tools" / "scripts" / "check").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            '[build](Makefile) [script](scripts/check)\n'
            '[build]: Makefile\n[script]: scripts/check\n'
        )
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "Makefile")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "scripts/check")])
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(1, code)

    def test_explicit_destinations_override_backticked_link_labels(self):
        for text in ('Read [`missing.md`](missing.md).\n', '[`missing.md`]: missing.md\n'):
            with self.subTest(text=text):
                verdicts = self.verdicts(text)
                self.assertEqual("BREAKS-ON-USE", verdicts[("path", "missing.md")])
                code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
                self.assertEqual(1, code)
        verdicts = self.verdicts('Read `missing.md`.\n')
        self.assertEqual("UNRESOLVED", verdicts[("path", "missing.md")])
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_relative_imports_without_package_context_are_unresolved(self):
        verdicts = self.verdicts("```python\nfrom .missing import Thing\n```\n")
        self.assertEqual("UNRESOLVED", verdicts[("import", "from .missing import")])
        code, _, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)
        (self.repo / "__init__.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom .missing import Thing\n```\n")
        self.assertEqual("UNRESOLVED", verdicts[("import", "from .missing import")])
        namespace = self.repo / "src" / "namespace" / "nested"
        namespace.mkdir(parents=True)
        (namespace / "__init__.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom .missing import Thing\n```\n", namespace)
        self.assertEqual("UNRESOLVED", verdicts[("import", "from .missing import")])
        with TemporaryDirectory() as outside:
            directory = Path(outside)
            (directory / "__init__.py").write_text("", encoding="utf-8")
            verdicts = self.verdicts("```python\nfrom .missing import Thing\n```\n", directory)
            self.assertEqual("UNRESOLVED", verdicts[("import", "from .missing import")])

    def test_relative_imports_cannot_escape_scoped_package(self):
        package = self.repo / "src" / "pkg"
        verdicts = self.verdicts("```python\nfrom . import store\nfrom ..missing import Thing\n```\n", package)
        self.assertEqual("TRUE", verdicts[("import", "from . import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from ..missing import")])
        code, _, _ = run_main(str(package / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(1, code)

    def test_relative_imports_preserve_namespace_ancestors(self):
        package = self.repo / "namespace" / "pkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package.parent / "util.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom ..util import Thing\n```\n", package)
        self.assertEqual("TRUE", verdicts[("import", "from ..util import")])
        code, _, _ = run_main(str(package / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_relative_escape_does_not_override_namespace_extension(self):
        package = self.repo / "namespace" / "pkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom ..missing import Thing\n```\n", package)
        self.assertEqual("UNRESOLVED", verdicts[("import", "from ..missing import")])

    def test_cli_resolves_relative_instruction_file_paths(self):
        self.verdicts("```python\nfrom .missing import Thing\n```\n", self.repo / "src" / "pkg")
        process = subprocess.run(
            [os.sys.executable, str(ROOT / "scripts" / "check_agents_claims.py"),
             "src/pkg/AGENTS.md", "--repo", str(self.repo), "--fail-on-breaks"],
            cwd=self.repo, capture_output=True, text=True,
        )
        self.assertEqual(1, process.returncode)
        self.assertIn("BREAKS-ON-USE", process.stdout)
        self.assertIn("1 claim(s) would break", process.stderr)

    def test_existing_and_missing_paths(self):
        verdicts = self.verdicts(
            "See `docs/guide.md`, `src/pkg/`, and [guide](docs/guide.md#setup).\n"
            "Read `docs/missing.md`, [gone](docs/gone.md#anchor), and [old](docs/old.md#python-3.12).\n"
        )
        self.assertEqual("TRUE", verdicts[("path", "docs/guide.md")])
        self.assertEqual("TRUE", verdicts[("path", "src/pkg/")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/gone.md")])
        # punctuation in the fragment must not hide the file claim
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/old.md")])

    def test_path_relative_to_a_nested_instruction_file(self):
        verdicts = self.verdicts(
            "See `store.py`, `./__init__.py`, `../pkg/store.py`, [guide](../../docs/guide.md#setup), "
            "`../missing.md`, and [gone](../../docs/gone.md).\n",
            doc_dir=self.repo / "src" / "pkg",
        )
        self.assertEqual("TRUE", verdicts[("path", "store.py")])
        self.assertEqual("TRUE", verdicts[("path", "./__init__.py")])
        self.assertEqual("TRUE", verdicts[("path", "../pkg/store.py")])
        self.assertEqual("TRUE", verdicts[("path", "../../docs/guide.md")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "../missing.md")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "../../docs/gone.md")])

    def test_path_escaping_the_repo_is_not_resolved_outside_it(self):
        outside = self.repo.parent / "outside.md"
        outside.write_text("", encoding="utf-8")
        self.addCleanup(outside.unlink)
        verdicts = self.verdicts("See `docs/../../outside.md` and `../outside.md`.\n")
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/../../outside.md")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "../outside.md")])

    def test_bare_file_names_and_shorthand_paths(self):
        verdicts = self.verdicts("Edit `store.py`, `pkg/store.py`, `hidden.md`, and `nowhere.py`.\n")
        self.assertEqual("TRUE", verdicts[("path", "store.py")])
        self.assertEqual("IMPRECISE", verdicts[("path", "pkg/store.py")])
        # node_modules is pruned from the index
        self.assertEqual("UNRESOLVED", verdicts[("path", "hidden.md")])
        self.assertEqual("UNRESOLVED", verdicts[("path", "nowhere.py")])

    def test_missing_path_next_to_a_negation_needs_ai_and_never_fails(self):
        # A negation cannot tell "must stay absent" from "do not proceed until you read it".
        verdicts = self.verdicts(
            "Never commit `secrets/key.json` to the repository.\n"
            "Do not proceed until you have read `docs/required.md`.\n"
            "Do not edit `docs/guide.md` by hand.\n"
        )
        self.assertEqual("NEEDS-AI", verdicts[("path", "secrets/key.json")])
        self.assertEqual("NEEDS-AI", verdicts[("path", "docs/required.md")])
        self.assertEqual("TRUE", verdicts[("path", "docs/guide.md")])

        code, out, _ = run_main(str(self.repo / "AGENTS.md"), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)
        self.assertIn("NEEDS-AI claims: 2", out)

    def test_deployed_path_is_not_a_break(self):
        verdicts = self.verdicts("Logs go to `var/log/app/` (production).\n")
        self.assertEqual("UNRESOLVED", verdicts[("path", "var/log/app/")])

    def test_prohibition_must_stand_next_to_the_path(self):
        verdicts = self.verdicts("Do not guess the layout; read `docs/missing.md` first.\n")
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])

    def test_commit_examples_are_checked_against_history(self):
        self.git("init", "-q")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=T",
                 "commit", "-q", "--allow-empty", "-m", "docs(agents): link invariants to owning ADRs")
        verdicts = self.verdicts(
            "Use `<type>(<scope>): <subject>`, for example `docs(agents): link invariants` "
            "or `fix(persistence): reject stale writes`.\n"
        )
        self.assertEqual("TRUE", verdicts[("example", "docs(agents): link invariants")])
        self.assertEqual("IMPRECISE", verdicts[("example", "fix(persistence): reject stale writes")])
        self.assertNotIn(("example", "<type>(<scope>): <subject>"), verdicts)

    def test_commit_example_without_git_history_is_unresolved(self):
        verdicts = self.verdicts("For example `feat(core): add journal`.\n")
        self.assertEqual("UNRESOLVED", verdicts[("example", "feat(core): add journal")])

    def test_commit_example_when_git_cannot_run_is_unresolved(self):
        with mock.patch.object(check_agents_claims.subprocess, "run", side_effect=OSError):
            verdicts = self.verdicts("For example `feat(core): add journal`.\n")
        self.assertEqual("UNRESOLVED", verdicts[("example", "feat(core): add journal")])

    def test_dot_prefixed_paths_are_claims(self):
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        (self.repo / ".github" / "workflows" / "ci.yml").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "CI lives in `.github/workflows/ci.yml`; also read `.github/workflows/missing.yml` "
            "and [gone](.github/workflows/gone.yml).\n"
        )
        self.assertEqual("TRUE", verdicts[("path", ".github/workflows/ci.yml")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", ".github/workflows/missing.yml")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", ".github/workflows/gone.yml")])

    def test_paths_resolve_against_what_git_would_commit(self):
        """A deleted file differs in CI; an ignored one is generated output, absent by design there."""
        self.git("init", "-q")
        (self.repo / ".gitignore").write_text("build/\n", encoding="utf-8")
        (self.repo / "build").mkdir()
        (self.repo / "build" / "out.md").write_text("", encoding="utf-8")
        (self.repo / "docs" / "old.md").write_text("", encoding="utf-8")
        self.git("add", "docs/old.md")
        (self.repo / "docs" / "old.md").unlink()
        verdicts = self.verdicts(
            "See `build/out.md`, `build/later.md`, `out.md`, `docs/old.md`, and the new `docs/guide.md`.\n"
        )
        # ignored, whether it exists locally or not: the same verdict here and in a clean checkout
        self.assertEqual("UNRESOLVED", verdicts[("path", "build/out.md")])
        self.assertEqual("UNRESOLVED", verdicts[("path", "build/later.md")])
        self.assertEqual("UNRESOLVED", verdicts[("path", "out.md")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/old.md")])
        # untracked but not ignored: it will be committed with the change
        self.assertEqual("TRUE", verdicts[("path", "docs/guide.md")])

    def test_paths_resolve_against_the_disk_when_git_cannot_run(self):
        with mock.patch.object(check_agents_claims.subprocess, "run", side_effect=OSError):
            verdicts = self.verdicts("See `docs/guide.md` and `docs/missing.md`.\n")
        self.assertEqual("TRUE", verdicts[("path", "docs/guide.md")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("path", "docs/missing.md")])

    def test_imports_resolve_against_what_git_would_commit(self):
        self.git("init", "-q")
        (self.repo / ".gitignore").write_text("src/pkg/local.py\nsrc/pkg/_version.py\nbuild/\n", encoding="utf-8")
        (self.repo / "src" / "pkg" / "local.py").write_text("", encoding="utf-8")
        (self.repo / "build").mkdir()
        (self.repo / "build" / "lib.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "```python\n"
            "from pkg.local import X\n"
            "from pkg._version import version\n"
            "from pkg.gone import Z\n"
            "from pkg.store import Y\n"
            "import build\n"
            "```\n"
        )
        # an ignored module is generated (setuptools-scm writes _version.py), present or not
        self.assertEqual("UNRESOLVED", verdicts[("import", "from pkg.local import")])
        self.assertEqual("UNRESOLVED", verdicts[("import", "from pkg._version import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.gone import")])
        self.assertEqual("TRUE", verdicts[("import", "from pkg.store import")])
        # an ignored build/ directory is not a first-party package, so `build` stays third-party
        self.assertNotIn(("import", "import build"), verdicts)

    def test_imports_in_indented_fences_lists_and_python3_blocks(self):
        verdicts = self.verdicts(
            "1. Example:\n"
            "\n"
            "   ```python\n"
            "   from pkg.missing import X\n"
            "   ```\n"
            "```python\n"
            "import json, pkg.gone as gone, pkg.store\n"
            "```\n"
            "```python3\n"
            "import pkg.absent\n"
            "```\n"
        )
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.missing import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "import pkg.gone")])
        self.assertEqual("TRUE", verdicts[("import", "import pkg.store")])
        self.assertNotIn(("import", "import json"), verdicts)
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "import pkg.absent")])

    def test_directory_names_and_shorthand_directories(self):
        (self.repo / "docs" / "adr").mkdir()
        (self.repo / "docs" / "adr" / "0001.md").write_text("", encoding="utf-8")
        (self.repo / "src" / "pkg" / "sub").mkdir()
        verdicts = self.verdicts("Files under `adr/`, `pkg/sub/`, and `nowhere/`.\n")
        # the same treatment as a bare file name or a shorthand file path, never a break
        self.assertEqual("TRUE", verdicts[("path", "adr/")])
        self.assertEqual("IMPRECISE", verdicts[("path", "pkg/sub/")])
        self.assertEqual("UNRESOLVED", verdicts[("path", "nowhere/")])

    def test_src_namespace_packages_are_first_party(self):
        (self.repo / "src" / "acme").mkdir()
        (self.repo / "src" / "acme" / "core.py").write_text("", encoding="utf-8")
        (self.repo / "docs" / "adr").mkdir()
        verdicts = self.verdicts(
            "```python\n"
            "from acme.core import A\n"
            "from acme.missing import Thing\n"
            "from adr.missing import Thing\n"
            "```\n"
        )
        self.assertEqual("TRUE", verdicts[("import", "from acme.core import")])
        # a namespace package may continue in an installed distribution: reported, never a break
        self.assertEqual("UNRESOLVED", verdicts[("import", "from acme.missing import")])
        # only src/ children become import roots without __init__.py; docs/adr does not
        self.assertNotIn(("import", "from adr.missing import"), verdicts)

    def test_namespace_shared_with_an_installed_distribution_is_not_a_break(self):
        (self.repo / "src" / "google" / "myteam").mkdir(parents=True)
        (self.repo / "src" / "google" / "myteam" / "api.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "```python\n"
            "from google.myteam.api import Client\n"
            "from google.protobuf import message\n"
            "```\n"
        )
        self.assertEqual("TRUE", verdicts[("import", "from google.myteam.api import")])
        self.assertEqual("UNRESOLVED", verdicts[("import", "from google.protobuf import")])

    def test_src_directory_without_python_is_not_an_import_root(self):
        (self.repo / "src" / "http").mkdir()
        (self.repo / "src" / "http" / "client.ts").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom http.server import HTTPServer\n```\n")
        self.assertNotIn(("import", "from http.server import"), verdicts)

    def test_regular_packages_one_level_below_any_top_level_directory(self):
        (self.repo / "lib" / "libpkg").mkdir(parents=True)
        (self.repo / "lib" / "libpkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "lib" / "libpkg" / "m.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "```python\n"
            "from libpkg.m import f\n"
            "from libpkg.gone import g\n"
            "```\n"
        )
        self.assertEqual("TRUE", verdicts[("import", "from libpkg.m import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from libpkg.gone import")])

    def test_imports_do_not_search_unrelated_roots_in_src_layout(self):
        (self.repo / "pyproject.toml").write_text(
            '[tool.setuptools]\n'
            'package-dir = {"" = "src"}\n'
            '[tool.setuptools.packages.find]\n'
            'where = ["src"]\n',
            encoding="utf-8",
        )
        test_package = self.repo / "tests" / "pkg"
        test_package.mkdir(parents=True)
        (test_package / "__init__.py").write_text("", encoding="utf-8")
        (test_package / "missing.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "```python\nfrom pkg.store import Store\nfrom pkg.missing import Thing\n```\n"
        )
        self.assertEqual("TRUE", verdicts[("import", "from pkg.store import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.missing import")])

    def test_named_setuptools_package_dir_keeps_package_identity(self):
        (self.repo / "pyproject.toml").write_text(
            '[tool.setuptools]\n'
            'package-dir = {pkg = "lib"}\n'
            'packages = ["pkg"]\n',
            encoding="utf-8",
        )
        package = self.repo / "lib"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "store.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "```python\nfrom pkg.store import Store\nfrom pkg.missing import Thing\n```\n"
        )
        self.assertEqual("TRUE", verdicts[("import", "from pkg.store import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.missing import")])

    def test_ignored_regular_package_marker_keeps_namespace_unresolved(self):
        self.git("init", "-q")
        package = self.repo / "src" / "acme"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "api.py").write_text("", encoding="utf-8")
        (self.repo / ".gitignore").write_text("src/acme/__init__.py\n", encoding="utf-8")
        self.git("add", ".gitignore", "src/acme/api.py")
        self.git("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "fixture")
        check_agents_claims.git_paths.cache_clear()
        verdicts = self.verdicts(
            "```python\nfrom acme.missing import Thing\n```\n"
        )
        self.assertEqual("UNRESOLVED", verdicts[("import", "from acme.missing import")])

    def test_extensionless_file_is_not_an_importable_module(self):
        (self.repo / "src" / "pkg" / "missing").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom pkg.missing import Thing\n```\n")
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.missing import")])

    def test_relative_imports_use_the_enclosing_package_root(self):
        package = self.repo / "lib" / "libpkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "local.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts(
            "```python\nfrom .local import Thing\nfrom .missing import Thing\n```\n",
            package,
        )
        self.assertEqual("TRUE", verdicts[("import", "from .local import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from .missing import")])

    def test_relative_imports_resolve_from_src_namespace_with_only_subpackages(self):
        package = self.repo / "src" / "acme" / "sub"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "local.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom .local import Thing\n```\n", package)
        self.assertEqual("TRUE", verdicts[("import", "from .local import")])

    def test_relative_import_keeps_regular_package_context_with_neighbor_module(self):
        package = self.repo / "lib" / "libpkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "lib" / "utility.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom .missing import Thing\n```\n", package)
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from .missing import")])

    def test_dotted_setuptools_package_dir_preserves_subpackage_mapping(self):
        (self.repo / "pyproject.toml").write_text(
            '[tool.setuptools]\n'
            'package-dir = {"pkg.sub" = "other"}\n'
            'packages = ["pkg", "pkg.sub"]\n',
            encoding="utf-8",
        )
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        mapped = self.repo / "other"
        mapped.mkdir()
        (mapped / "__init__.py").write_text("", encoding="utf-8")
        (mapped / "local.py").write_text("", encoding="utf-8")
        verdicts = self.verdicts("```python\nfrom pkg.sub.local import Thing\n```\n")
        self.assertEqual("TRUE", verdicts[("import", "from pkg.sub.local import")])

    def test_python_imports_in_fenced_blocks(self):
        verdicts = self.verdicts(
            "```python\n"
            "import json\n"
            "from pkg.store import Store\n"
            "from pkg.missing import Thing\n"
            "import docs\n"
            "```\n"
            "```sh\n"
            "run `thing` = `value`\n"
            "```\n"
        )
        self.assertNotIn(("import", "import json"), verdicts)
        self.assertEqual("TRUE", verdicts[("import", "from pkg.store import")])
        self.assertEqual("BREAKS-ON-USE", verdicts[("import", "from pkg.missing import")])
        # a directory without __init__.py imports as a PEP 420 namespace package
        self.assertEqual("TRUE", verdicts[("import", "import docs")])
        self.assertEqual("UNRESOLVED", verdicts[("snippet", "python block, lines 1-6")])
        self.assertEqual("UNRESOLVED", verdicts[("snippet", "sh block, lines 7-9")])
        # config-looking text inside a fence is code, not a claim
        self.assertNotIn(("config", "`thing` = `value`"), verdicts)

    def test_process_and_config_claims_are_enumerated(self):
        verdicts = self.verdicts("Migrations run on every deploy.\nThe `timeout` is `30`.\n")
        self.assertEqual("UNRESOLVED", verdicts[("process", "Migrations run on every deploy.")])
        self.assertEqual("UNRESOLVED", verdicts[("config", "`timeout` is `30`")])

    def test_cli_exit_codes_and_output_modes(self):
        doc = self.repo / "AGENTS.md"
        doc.write_text("Read `docs/missing.md`, `docs/guide.md`, and `nowhere.py`.\n", encoding="utf-8")

        code, out, _ = run_main(str(doc), "--repo", str(self.repo))
        self.assertEqual(0, code)
        self.assertIn("COUNTS: BREAKS-ON-USE=1, TRUE=1, UNRESOLVED=1, total=3", out)

        code, _, err = run_main(str(doc), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(1, code)
        self.assertIn("1 claim(s) would break an agent", err)

        _, out, _ = run_main(str(doc), "--repo", str(self.repo), "--json", "--only", "problems")
        self.assertEqual(["docs/missing.md"], [json.loads(line)["quote"] for line in out.splitlines()])

        _, out, _ = run_main(str(doc), "--repo", str(self.repo), "--json", "--only", "unresolved")
        self.assertEqual(["nowhere.py"], [json.loads(line)["quote"] for line in out.splitlines()])

        # Filtering the display must not hide a break from the exit status.
        code, _, _ = run_main(str(doc), "--repo", str(self.repo), "--only", "unresolved", "--fail-on-breaks")
        self.assertEqual(1, code)

        doc.write_text("Never read `docs/absent.md`.\n", encoding="utf-8")
        _, out, _ = run_main(str(doc), "--repo", str(self.repo), "--json", "--only", "problems")
        self.assertEqual(["NEEDS-AI"], [json.loads(line)["verdict"] for line in out.splitlines()])

        doc.write_text("Read `docs/guide.md`.\n", encoding="utf-8")
        code, _, _ = run_main(str(doc), "--repo", str(self.repo), "--fail-on-breaks")
        self.assertEqual(0, code)

    def test_cli_rejects_missing_inputs(self):
        code, _, _ = run_main("AGENTS.md", "--repo", str(self.repo / "absent"))
        self.assertIn("not a directory", code)
        code, _, _ = run_main(str(self.repo / "absent.md"), "--repo", str(self.repo))
        self.assertIn("not a file", code)

    def test_repository_agents_files_have_no_breaks(self):
        docs = subprocess.run(
            ["git", "ls-files", ":(glob)**/AGENTS.md"], cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
        self.assertTrue(docs)
        code, out, _ = run_main(*(str(ROOT / doc) for doc in docs), "--repo", str(ROOT), "--fail-on-breaks")
        self.assertEqual(0, code, out[-2000:])


if __name__ == "__main__":
    unittest.main()
