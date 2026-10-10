#!/usr/bin/env python3
"""
Enumerate checkable claims in an agent instruction file and resolve the mechanical ones.

Usage:
    python3 scripts/check_agents_claims.py AGENTS.md
    python3 scripts/check_agents_claims.py AGENTS.md --repo /path/to/repo
    python3 scripts/check_agents_claims.py AGENTS.md --json          # NDJSON, one object per claim
    python3 scripts/check_agents_claims.py AGENTS.md --only unresolved

What it resolves by itself (deterministic, no judgement):
    path        - does the referenced file/directory exist?
    import      - does a first-party module path in a parseable Python block plausibly exist on
                  disk? Member names in `from ... import ...` statements are unresolved.
    example     - does a quoted Conventional Commits example exist in git history?

What it only enumerates, for the model to adjudicate:
    path        - NEEDS-AI when a missing path stands next to a negation
    snippet     - fenced code block: identifiers must resolve against real code
    config      - a claimed config value: read the config file and compare
    process     - "on every deploy...", "someone has to..." : corroborate elsewhere

Exit code is 0 by default; with --fail-on-breaks it is 1 when some claim is BREAKS-ON-USE.
IMPRECISE, NEEDS-AI, and UNRESOLVED never fail the run - an unresolved claim is data, not an error.
"""

import argparse
import ast
import functools
import importlib.util
import json
import os
import re
import string
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path
from urllib.parse import unquote

# backticked path with a file extension, or a directory path ending in /; leading ./ and ../ are
# kept so resolve_path can check them, including whether they escape the repository, and a
# dot-prefixed first segment (.github/) is a path like any other
_EXT = r'py|md|mjs|js|json|toml|txt|ya?ml|sh'
_PARENTS = r'(?:\.{1,2}/)*\.?'
MARKDOWN_ESCAPE_RE = re.compile(r'\\([%s])' % re.escape(string.punctuation))
# General extensions require a slash; bare domains and version strings are not file claims.
PATH_RE = re.compile(
    rf'`(?P<path>{_PARENTS}[\w][\w ./-]*(?:\.(?:{_EXT})|/)'
    rf'|{_PARENTS}[\w][\w ./-]*/[\w .-]+\.[a-zA-Z][a-zA-Z0-9]*)`'
)
# Markdown destinations identify paths even without an extension; an #anchor is not part of the path,
# and any character in it must be accepted, or a dot in the anchor hides the file claim entirely
# Angle-wrapped destinations must close before the optional title; the brackets are not path data.
_LINK_TARGET = (
    rf'(?P<angle><)?(?![A-Za-z][A-Za-z0-9+.-]*:)(?P<path>/?{_PARENTS}(?:[\w%]|\\[^\n])(?(angle)(?:\\[^\n]|[^<>?#\n])*|(?:\\[^\n]|[\w./()%-])*))'
    r'(?:\?(?(angle)[^<>#\n]*|[^)\s<>#]*))?'
    r'(?:#(?(angle)[^<>\n]*|[^)\s<>]*))?(?(angle)>)(?:\s+(?:"[^"\n]*"|\'[^\'\n]*\'|\([^\n)]*\)))?'
)
LINK_RE = re.compile(rf'\]\({_LINK_TARGET}\)')
REFERENCE_RE = re.compile(rf'^[ \t]{{0,3}}\[[^\]\n]+\]:[ \t]+{_LINK_TARGET}[ \t]*$')
# Only simple list containers are tracked; uncontained four-space indentation is a literal code
# block, not a fence. Deeper CommonMark constructs stay outside this basic scanner.
LIST_ITEM_RE = re.compile(r'^(?P<indent> {0,3})(?P<marker>[-+*]|[0-9]{1,9}[.)])(?P<gap> {1,4})\S')
FENCE_RE = re.compile(r'^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$')
BLOCKQUOTE_PREFIX_RE = re.compile(r'^(?: {0,3}>[ \t]?)+')
PYTHON_LANGS = {'python', 'py', 'python3'}
# claims that name a config knob and a value
CONFIG_RE = re.compile(r'`(?P<key>[\w-]+)`\s*(?:=|is|:)\s*`?(?P<value>[\w.-]+)`?')
# backticked Conventional Commits example; `<type>(<scope>): ...` templates do not match
_TYPES = r'feat|fix|docs|test|refactor|ci|chore|perf'
EXAMPLE_RE = re.compile(rf'`(?P<example>(?:{_TYPES})(?:\([\w./-]+\))?!?: [^`]+)`')
PROCESS_RE = re.compile(
    r'\b(?:on every deploy|automatically registered|registered automatically|is sufficient'
    r'|happens automatically)\b',
    re.I,
)
# a negation next to a missing path may mean "must stay absent" ("never commit .env") or may not
# ("do not proceed until you read x"); only a model can tell, so such claims are NEEDS-AI
PROHIBITION_RE = re.compile(r'\b(?:never|not |non-|don\'t|do not|avoid|must not|no )', re.I)
# How many characters around a path still count as the same clause.
CLAUSE_REACH = 60
# a path described as living on a deploy target, not in this working copy
ELSEWHERE_RE = re.compile(r'\b(?:production|on the server|deploy(?:ed|ment)?\b)', re.I)

SKIP_DIR_PARTS = {'node_modules', '__pycache__', '.git'}


def fenced_blocks(text):
    """Yield (lang, start_line, end_line, body) for each fenced code block."""
    raw_lines = text.splitlines()
    quote_prefixes = [BLOCKQUOTE_PREFIX_RE.match(line) for line in raw_lines]
    lines = [line[match.end():] if match else line
             for line, match in zip(raw_lines, quote_prefixes)]
    open_at = None
    lang = ''
    fence = ''
    container_indent = None
    blockquoted = False
    for i, raw_line in enumerate(raw_lines, start=1):
        quoted = quote_prefixes[i - 1] is not None
        if open_at is None:
            line = lines[i - 1] if quoted else raw_line
        elif blockquoted:
            if not quoted:
                continue
            line = lines[i - 1]
        else:
            line = raw_line
        m = FENCE_RE.match(line)
        if not m:
            continue
        marker, info = m.group('fence'), m.group('info').strip()
        indent = len(m.group('indent').expandtabs(4))
        if open_at is None:
            if marker[0] == chr(96) and chr(96) in info:
                continue
            container_indent = fence_container_indent(lines, i - 1, indent)
            if container_indent is None:
                continue
            open_at, fence = i, marker
            lang = info.split()[0] if info else ''
            blockquoted = quoted
        elif (marker[0] == fence[0] and len(marker) >= len(fence) and not info
              and container_indent <= indent <= container_indent + 3):
            body_lines = lines if blockquoted else raw_lines
            yield lang, open_at, i, '\n'.join(body_lines[open_at:i - 1])
            open_at = None
            container_indent = None
            blockquoted = False

    if open_at is not None:
        body_lines = lines if blockquoted else raw_lines
        yield lang, open_at, len(raw_lines) + 1, '\n'.join(body_lines[open_at:])
def fence_container_indent(lines, line_index, indent):
    """Return 0 for shallow fences or the content column of a nearby simple list item."""
    if indent <= 3:
        return 0
    for line in reversed(lines[:line_index]):
        if not line.strip():
            continue
        match = LIST_ITEM_RE.match(line)
        if match:
            base = (len(match.group('indent')) + len(match.group('marker'))
                    + len(match.group('gap')))
            return base if base <= indent <= base + 3 else None
        if not line.startswith((' ', '\t')):
            return None
    return None


def in_fence(line_no, blocks):
    # The opening info string and closing delimiter are part of the fenced block too.
    return any(start <= line_no <= end for _, start, end, _ in blocks)


def indented_code_lines(lines):
    """Return lines in basic indented code blocks, respecting simple list containers."""
    code_lines = set()
    list_items = []
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        item = LIST_ITEM_RE.match(line)
        if item:
            marker_indent = len(item.group('indent').expandtabs(4))
            while list_items and list_items[-1][0] >= marker_indent:
                list_items.pop()
            content_indent = (marker_indent + len(item.group('marker'))
                              + len(item.group('gap')))
            list_items.append((marker_indent, content_indent))
            continue

        leading = line[:len(line) - len(line.lstrip(' \t'))]
        indent = len(leading.expandtabs(4))
        while list_items and indent < list_items[-1][1]:
            list_items.pop()
        if list_items:
            if indent >= list_items[-1][1] + 4:
                code_lines.add(line_no)
        elif indent >= 4:
            code_lines.add(line_no)
    return code_lines


def inline_code_span_end(line, start, body_end):
    """Return the end of a same-line code span, or None when the delimiter is unmatched."""
    tick = chr(96)
    if start >= body_end or line[start] != tick:
        return None
    backslashes = 0
    cursor = start - 1
    while cursor >= 0 and line[cursor] == '\\':
        backslashes += 1
        cursor -= 1
    if backslashes % 2:
        return None

    opener_end = start + 1
    while opener_end < body_end and line[opener_end] == tick:
        opener_end += 1
    delimiter_size = opener_end - start
    cursor = opener_end
    while cursor < body_end:
        closing = line.find(tick, cursor, body_end)
        if closing < 0:
            return None
        closing_end = closing + 1
        while closing_end < body_end and line[closing_end] == tick:
            closing_end += 1
        if closing_end - closing == delimiter_size:
            return closing_end
        cursor = closing_end
    return None


def mask_markdown_comments(text):
    """Mask HTML comments while preserving Markdown code and source line positions."""
    source_lines = text.splitlines(keepends=True)
    indented_code = indented_code_lines(source_lines)
    tick = chr(96)
    masked = text
    while True:
        blocks = list(fenced_blocks(masked))
        fenced_lines = {
            line_no
            for _, start, end, _ in blocks
            for line_no in range(start, end + 1)
        }
        lines = []
        in_comment = False
        for line_no, line in enumerate(source_lines, start=1):
            if not in_comment and (line_no in fenced_lines or line_no in indented_code):
                lines.append(line)
                continue
            body_end = len(line.rstrip("\r\n"))
            chars = list(line)
            cursor = 0
            while cursor < body_end:
                if in_comment:
                    close = line.find("-->", cursor, body_end)
                    stop = body_end if close < 0 else close + 3
                    chars[cursor:stop] = " " * (stop - cursor)
                    if close < 0:
                        cursor = body_end
                    else:
                        in_comment = False
                        cursor = stop
                else:
                    opening = line.find("<!--", cursor, body_end)
                    inline_start = line.find(tick, cursor, body_end)
                    inline_end = None
                    while inline_start >= 0:
                        inline_end = inline_code_span_end(line, inline_start, body_end)
                        if inline_end is not None:
                            break
                        run_end = inline_start + 1
                        while run_end < body_end and line[run_end] == tick:
                            run_end += 1
                        inline_start = line.find(tick, run_end, body_end)

                    if inline_end is not None and (opening < 0 or inline_start < opening):
                        cursor = inline_end
                    elif opening < 0:
                        break
                    else:
                        close = line.find("-->", opening + 4, body_end)
                        stop = body_end if close < 0 else close + 3
                        chars[opening:stop] = " " * (stop - opening)
                        if close < 0:
                            in_comment = True
                            cursor = body_end
                        else:
                            cursor = stop
            lines.append("".join(chars))
        updated = "".join(lines)
        if updated == masked:
            return updated
        masked = updated


@functools.lru_cache(maxsize=None)
def name_index(repo):
    """
    File name -> paths, built in one walk.

    Ignored directories are pruned during the descent; filtering after a per-claim `rglob` walked
    into node_modules for every lookup, so runtime grew with dependencies, not with claims.
    """
    index = {}
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_PARTS and not d.startswith('.')]
        # Directories too, so `adr/` resolves like a bare file name does.
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            if committable(repo, path.relative_to(repo)):
                index.setdefault(name, []).append(path)
    return index


@functools.lru_cache(maxsize=None)
def git_paths(repo):
    """
    Paths git would commit from this working tree (tracked, or untracked and not ignored) and their
    parent directories, relative to `repo`; None outside a git work tree.

    CI checks a clean checkout, so a file that exists only locally (ignored build output) must not
    resolve here, or the local gate passes and CI fails on the same text.
    """
    try:
        out = subprocess.run(
            ['git', '-C', str(repo), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            capture_output=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    paths = set()
    for name in out.stdout.decode('utf-8', 'replace').split('\0'):
        if name:
            paths.add(Path(name))
            paths.update(Path(name).parents)
    return frozenset(paths)


def committable(repo, rel):
    """Would git commit the existing path `rel` (relative to `repo`)? Always True outside git."""
    paths = git_paths(repo)
    return paths is None or rel in paths


def exists_here(repo, path):
    """Does `path` (under `repo`) exist in what git would commit, as a clean checkout would see it?"""
    return path.exists() and committable(repo, path.relative_to(repo))


def resolve_path(repo, doc_dir, raw, explicit=False):
    """
    Returns (verdict, evidence). Paths in a module-scoped instruction file are usually relative to
    that module, not to the repo root. A leading slash marks a repo-root path; other forms try the
    document's own directory first.
    """
    if explicit:
        raw = unquote(MARKDOWN_ESCAPE_RE.sub(r'\1', raw))
    repo_abs = repo.resolve()
    root_relative = raw.startswith('/')
    bare = raw.lstrip('/')
    candidates = []

    bases = ((repo, 'repo-relative'),) if root_relative else (
        (doc_dir, 'relative to the file'), (repo, 'repo-relative')
    )
    directory_target = raw.endswith('/')
    for base, label in bases:
        candidate = (base / bare).resolve()
        try:
            relative = candidate.relative_to(repo_abs)
        except ValueError:
            continue
        candidates.append(str(relative))
        if (candidate.exists() and (not directory_target or candidate.is_dir())
                and committable(repo_abs, candidate.relative_to(repo_abs))):
            return 'TRUE', f'{candidate.relative_to(repo_abs)} ({label})'

    # A bare backticked name may describe a kind of file; a Markdown destination names a target.
    # A trailing slash only marks a directory; it is not a directory part.
    bare = bare.rstrip('/')
    if not explicit and '/' not in bare:
        hits = name_index(repo).get(bare, [])[:3]
        if hits:
            return 'TRUE', f'{len(hits)}+ files named {bare}, e.g. {hits[0].relative_to(repo_abs)}'
        return 'UNRESOLVED', f'no file named {bare} found; may be illustrative'

    # Shorthand path: the doc names a real file but omits leading directories. Worth reporting,
    # because an agent cannot open it as written, but the fix is a longer path, not new code.
    if not explicit:
        tail = Path(bare).name
        for hit in name_index(repo).get(tail, []):
            if str(hit).endswith('/' + bare):
                return 'IMPRECISE', f'shorthand for {hit.relative_to(repo_abs)}'

    if any(git_ignores(repo, candidate) for candidate in candidates):
        return 'UNRESOLVED', 'gitignored: generated at build or run time; absent by design'
    # A spaced span with a bare first word followed by a path may be an inline command.
    # Keep it advisory rather than guessing shell syntax or installed executables.
    head, separator, tail = raw.partition(' ')
    if not explicit and separator and '/' not in head and '/' in tail:
        return 'UNRESOLVED', 'may be an inline command rather than a literal path'
    return 'BREAKS-ON-USE', 'missing under both the file directory and the repo root'


def git_ignores(repo, bare):
    """
    True when the repo's .gitignore covers a path that is missing from what git would commit: build
    output, a generated `_version.py`. A clean checkout lacks it too, so it is absent by design.
    A `dist/` pattern matches directories only and git cannot tell that a missing path is one, so
    the path is retried with a slash. Git missing, not a repository (exit 128) or too slow: False,
    which keeps BREAKS-ON-USE.
    """
    for candidate in (bare,) if bare.endswith('/') else (bare, bare + '/'):
        try:
            out = subprocess.run(
                ['git', '-C', str(repo), 'check-ignore', '-q', '--no-index', '--', candidate],
                capture_output=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        if out.returncode == 0:
            return True
        if out.returncode != 1:
            return False
    return False


def configured_package_roots(repo):
    """Map setuptools import names to their actual package directories."""
    repo = repo.resolve()
    pyproject = repo / 'pyproject.toml'
    if not exists_here(repo, pyproject):
        return None
    try:
        with pyproject.open('rb') as stream:
            config = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    tools = config.get('tool')
    setuptools = tools.get('setuptools') if isinstance(tools, dict) else None
    if not isinstance(setuptools, dict):
        return None

    roots = {}
    declared = False

    def add(name, path, context=False):
        path = path.resolve()
        if not path.is_relative_to(repo):
            return
        candidates = roots.setdefault(name, [])
        for index, (candidate, is_context) in enumerate(candidates):
            if candidate == path:
                candidates[index] = (path, is_context or context)
                break
        else:
            candidates.append((path, context))

    def directories(base):
        try:
            return [child for child in base.iterdir()
                    if child.is_dir() and not child.name.startswith('.')
                    and child.name not in SKIP_DIR_PARTS
                    and exists_here(repo, child)]
        except OSError:
            return []

    def has_python(path):
        return any(child.is_file() and exists_here(repo, child)
                   for child in path.rglob('*.py'))

    def add_from_base(base, context=False):
        base = base.resolve()
        if not base.is_relative_to(repo):
            return
        for child in directories(base):
            initializer = child / '__init__.py'
            regular = exists_here(repo, initializer) and initializer.is_file()
            if base == repo or regular or has_python(child):
                add(child.name, child, context or regular)

    package_dir = setuptools.get('package-dir', {})
    if isinstance(package_dir, dict):
        for package, directory in package_dir.items():
            if not isinstance(package, str) or not isinstance(directory, str):
                continue
            declared = True
            mapped = (repo / directory).resolve()
            if package:
                add(package, mapped, context=True)
            else:
                add_from_base(mapped, context=True)

    py_modules = setuptools.get('py-modules')
    if isinstance(py_modules, list) and py_modules:
        module_base = repo
        if isinstance(package_dir, dict) and isinstance(package_dir.get(''), str):
            module_base = (repo / package_dir['']).resolve()
        declared = True
        for name in py_modules:
            if not isinstance(name, str) or not name or not all(
                    part.isidentifier() for part in name.split('.')):
                continue
            module = module_base.joinpath(*name.split('.')).with_suffix('.py').resolve()
            if (module.is_relative_to(module_base) and exists_here(repo, module)
                    and module.is_file()):
                add(name, module)

    packages = setuptools.get('packages', {})
    finder = packages.get('find', {}) if isinstance(packages, dict) else {}
    if isinstance(finder, dict) and 'where' in finder:
        declared = True
        where = finder['where']
        if isinstance(where, str):
            where = [where]
        if isinstance(where, list):
            for directory in where:
                if isinstance(directory, str):
                    add_from_base((repo / directory).resolve(), context=True)
    elif isinstance(finder, dict) and finder:
        declared = True
        add_from_base(repo)

    return roots if declared else None


def first_party_roots(repo):
    """Map first-party import names to their actual package directories and context roots."""
    repo = repo.resolve()
    roots = {}

    def add(name, package, context=False):
        package = package.resolve()
        packages = roots.setdefault(name, [])
        for index, (candidate, is_context) in enumerate(packages):
            if candidate == package:
                packages[index] = (package, is_context or context)
                break
        else:
            packages.append((package, context))

    def directories(base):
        try:
            children = base.iterdir()
            return [child for child in children
                    if child.is_dir() and not child.name.startswith('.')
                    and child.name not in SKIP_DIR_PARTS
                    and exists_here(repo, child)]
        except OSError:
            return []

    def has_direct_module(path):
        return any(child.is_file() and exists_here(repo, child)
                   for child in path.glob('*.py'))

    def has_python(path):
        return any(child.is_file() and exists_here(repo, child)
                   for child in path.rglob('*.py'))

    def add_top_level_modules():
        try:
            children = list(repo.iterdir())
        except OSError:
            return
        for child in children:
            if child.is_file() and child.suffix == '.py' and exists_here(repo, child):
                add(child.stem, child)

    configured = configured_package_roots(repo)
    if configured is not None:
        roots.update(configured)
        # The repository root is a real import base for tools such as `scripts`; it must not
        # override a same-named package found under an explicitly configured source root.
        for child in directories(repo):
            if child.name != 'src' and child.name not in roots:
                initializer = child / '__init__.py'
                context = ((exists_here(repo, initializer) and initializer.is_file())
                           or has_python(child))
                add(child.name, child, context)
        add_top_level_modules()
        return roots

    top_level = directories(repo)
    # Prefer conventional src/ packages when a fixture has no packaging metadata. Keep each name
    # tied to its actual package directory so an unrelated tests/pkg cannot satisfy the import.
    package_bases = [child for child in top_level if child.name == 'src']
    package_bases.extend(child for child in top_level if child.name != 'src')
    for base in package_bases:
        for child in directories(base):
            initializer = child / '__init__.py'
            if exists_here(repo, initializer) and initializer.is_file():
                add(child.name, child, context=True)
            elif base.name == 'src' and any(
                    descendant.is_file() and exists_here(repo, descendant)
                    for descendant in child.rglob('*.py')):
                add(child.name, child, context=True)
    for child in top_level:
        if child.name != 'src' and child.name not in roots:
            initializer = child / '__init__.py'
            context = ((exists_here(repo, initializer) and initializer.is_file())
                       or has_python(child))
            add(child.name, child, context)
    add_top_level_modules()
    return roots


def absolute_import_verdict(repo, dotted, roots):
    """Resolve an absolute import. None means it is outside the discovered first-party roots."""
    names = [name for name in roots if dotted == name or dotted.startswith(name + '.')]
    if not names:
        return None
    prefix = max(names, key=lambda name: len(name.split('.')))
    remainder = dotted.split('.')[len(prefix.split('.')):]
    tail = Path(*remainder)
    locations = roots[prefix]

    for package_root, _ in locations:
        if package_root.is_file():
            if not remainder and exists_here(repo, package_root):
                return 'TRUE', f'module path {dotted}'
            continue
        module = (package_root / tail).with_suffix('.py')
        package = package_root / tail
        if ((exists_here(repo, module) and module.is_file())
                or (exists_here(repo, package) and package.is_dir())):
            return 'TRUE', f'module path {dotted}'

    if any(git_ignores(repo, str((package_root / tail).relative_to(repo)) + suffix)
           for package_root, _ in locations if package_root.is_dir()
           for suffix in ('.py', '/')):
        return 'UNRESOLVED', f'{dotted} is gitignored: generated at build or run time; absent by design'
    existing_roots = [package_root for package_root, _ in locations
                      if exists_here(repo, package_root) and package_root.is_dir()]
    if existing_roots and all(
            not (exists_here(repo, package_root / '__init__.py')
                 and (package_root / '__init__.py').is_file())
            for package_root in existing_roots):
        return 'UNRESOLVED', f'{dotted} not in the repo; namespace package {prefix} may continue outside it'
    return 'BREAKS-ON-USE', f'module path {dotted}'


def import_verdict(repo, dotted, roots, doc_dir):
    """None = not a claim about this repo (stdlib/third-party), else (verdict, evidence)."""
    repo = repo.resolve()
    if not dotted.startswith('.'):
        return absolute_import_verdict(repo, dotted, roots)

    # Relative imports need a package context. Resolve against each configured or regular package
    # root containing this instruction file; multiple valid names can exist in source layouts.
    directory = doc_dir.resolve()
    initializer = directory / '__init__.py'
    if not directory.is_relative_to(repo) or not exists_here(repo, initializer) or not initializer.is_file():
        return 'UNRESOLVED', f'{dotted}: no regular package context for this instruction file'

    contexts = []
    for name, locations in roots.items():
        for package_root, is_context in locations:
            if is_context and directory.is_relative_to(package_root):
                package = '.'.join((name, *directory.relative_to(package_root).parts))
                contexts.append(package)
    if not contexts:
        return 'UNRESOLVED', f'{dotted}: no import root for this instruction file'

    results = []
    escaped = False
    for package in contexts:
        try:
            absolute = importlib.util.resolve_name(dotted, package)
        except ImportError:
            escaped = True
            continue
        verdict = absolute_import_verdict(repo, absolute, roots)
        results.append(verdict or ('UNRESOLVED', f'{absolute}: no matching first-party import root'))

    for verdict in ('TRUE', 'BREAKS-ON-USE', 'UNRESOLVED'):
        for result in results:
            if result[0] == verdict:
                return result
    if escaped:
        return 'BREAKS-ON-USE', 'relative import escapes the scoped package'
    return 'UNRESOLVED', f'{dotted}: no reliable package context'


def git_has(repo, needle):
    """Search the whole history for a commit message, not a bounded slice."""
    try:
        out = subprocess.run(
            ['git', '-C', str(repo), 'log', '--all', '--fixed-strings', f'--grep={needle.strip()}',
             '--pretty=%h', '-1'],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return bool(out.stdout.strip())


def balanced_parentheses(value):
    """Whether unwrapped Markdown destination parentheses are properly paired."""
    depth = 0
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def collect(doc, repo):
    source = doc.read_text(encoding='utf-8', errors='replace')
    text = mask_markdown_comments(source)
    blocks = list(fenced_blocks(text))
    claims = []

    seen = set()

    def add(kind, line, quote, verdict, evidence, identity=None):
        key = (kind, line, quote.strip()[:200], identity)
        if key in seen:
            return
        seen.add(key)
        claims.append({
            'kind': kind, 'line': line, 'quote': quote.strip()[:200],
            'verdict': verdict, 'evidence': evidence,
        })

    lines = text.splitlines()
    indented_code = indented_code_lines(lines)
    for line_no, line in enumerate(lines, start=1):
        # Explicit destinations take precedence when a backticked label names the same path.
        fenced = in_fence(line_no, blocks)
        literal = fenced or line_no in indented_code
        links = list(LINK_RE.finditer(line)) if not literal else []
        references = list(REFERENCE_RE.finditer(line)) if not literal else []
        matches = links + references
        if not literal:
            for path_match in PATH_RE.finditer(line):
                start, end = path_match.span()
                raw = path_match.group('path')
                # A backticked label inside an explicit link is illustrative text. If it names
                # the exact destination, keep the destination's stronger path verdict only.
                linked_label = any(
                    raw == link.group('path')
                    and (label_start := line.rfind('[', 0, link.start())) >= 0
                    and label_start < start < end <= link.start()
                    for link in links
                )
                reference_label = any(
                    raw == reference.group('path')
                    and (label_start := line.find('[', reference.start(), reference.end())) >= 0
                    and (label_end := line.find(']:', label_start, reference.end())) >= 0
                    and label_start < start < end <= label_end
                    for reference in references
                )
                if not linked_label and not reference_label:
                    matches.append(path_match)
        for m in matches:
            raw = m.group('path')
            # The link regex can include parentheses in an unwrapped destination. Keep only
            # balanced pairs there; angle-wrapped destinations have their own delimiter.
            if m.re is not PATH_RE and not m.group('angle') and not balanced_parentheses(raw):
                continue
            # The prohibition must stand next to the path, not anywhere on the line: instruction
            # text is full of "not" and "never", and a line-wide match exempted links the agent is
            # told to follow. Negations may precede or follow the path; both sides stop at a
            # clause boundary. Environment markers also apply only within that clause.
            prefix = line[max(0, m.start() - CLAUSE_REACH):m.start()]
            clause = re.split(r'[;.]\s|\s--\s', prefix)[-1]
            suffix = re.split(r'[;.!?](?:\s|$)|\s--\s', line[m.end():m.end() + CLAUSE_REACH])[0]
            verdict, detail = resolve_path(repo, doc.parent, raw, explicit=m.re is not PATH_RE)
            if verdict != 'TRUE':
                if PROHIBITION_RE.search(clause) or PROHIBITION_RE.search(suffix):
                    verdict, detail = 'NEEDS-AI', 'missing, next to a negation: decide whether the absence is intended'
                elif ELSEWHERE_RE.search(clause) or ELSEWHERE_RE.search(suffix):
                    verdict, detail = 'UNRESOLVED', 'absent here; the text places it on a deploy target'
            # The same path can have different meanings in separate clauses on this line.
            add('path', line_no, raw, verdict, detail, identity=m.start('path'))

        if not literal:
            for m in EXAMPLE_RE.finditer(line):
                found = git_has(repo, m.group('example'))
                if found is None:
                    add('example', line_no, m.group('example'), 'UNRESOLVED', 'git log unavailable')
                else:
                    add('example', line_no, m.group('example'),
                        'TRUE' if found else 'IMPRECISE',
                        'present in git log' if found else 'no commit with this message in history; fine if illustrative')

        if not literal:
            if PROCESS_RE.search(line):
                add('process', line_no, line, 'UNRESOLVED', 'corroborate against docs/ or code')
            for m in CONFIG_RE.finditer(line):
                add('config', line_no, m.group(0), 'UNRESOLVED',
                    f'read the config file and compare {m.group("key")}')

    roots = first_party_roots(repo)
    for lang, start, end, body in blocks:
        if lang.lower() in PYTHON_LANGS:
            try:
                tree = ast.parse(textwrap.dedent(body))
            except (SyntaxError, ValueError):
                tree = None  # the snippet claim below keeps unparsable examples visible
            if tree is not None:
                import_nodes = sorted(
                    (node for node in ast.walk(tree)
                     if isinstance(node, (ast.Import, ast.ImportFrom))),
                    key=lambda node: (node.lineno, node.col_offset),
                )
                for node in import_nodes:
                    claim_line = start + node.lineno
                    if isinstance(node, ast.ImportFrom):
                        dotted = '.' * node.level + (node.module or '')
                        quote = f'from {dotted} import'
                        names = [alias.name for alias in node.names]
                        identity = tuple((alias.name, alias.asname) for alias in node.names)
                        targets = [(dotted, quote, identity)]
                    else:
                        names = None
                        targets = [(alias.name, f'import {alias.name}', None)
                                   for alias in node.names]
                    for dotted, quote, identity in targets:
                        verdict = import_verdict(repo, dotted, roots, doc.parent)
                        if verdict is None:
                            continue  # stdlib or third-party: not a claim about this repo
                        add('import', claim_line, quote, *verdict, identity=identity)
                        if (isinstance(node, ast.ImportFrom) and verdict[0] == 'TRUE'
                                and names):
                            add(
                                'import-member', claim_line, quote, 'UNRESOLVED',
                                f'{dotted} exists; imported member names are not statically checked: '
                                f'{", ".join(names)}',
                                identity=identity,
                            )
        add('snippet', start, f'{lang or "text"} block, lines {start}-{end}', 'UNRESOLVED',
            'resolve every identifier against real code; check it runs on paste')

    return claims


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('doc', nargs='+', help='instruction file(s) to audit')
    ap.add_argument('--repo', default='.', help='repo root the claims are about (default: cwd)')
    ap.add_argument('--json', action='store_true', help='NDJSON output')
    ap.add_argument('--only', choices=['unresolved', 'problems'], help='filter output')
    ap.add_argument('--fail-on-breaks', action='store_true',
                    help='exit 1 if any claim is BREAKS-ON-USE (for CI). IMPRECISE, NEEDS-AI, and UNRESOLVED never fail.')
    args = ap.parse_args(argv)

    # Absolute from here on: a relative root yields relative walk hits, which then blow up
    # in relative_to() against an absolute root.
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.exit(f'not a directory: {repo}')
    docs = [Path(d) for d in args.doc]
    for doc in docs:
        if not doc.is_file():
            sys.exit(f'not a file: {doc}')

    claims = []
    for doc in docs:
        for claim in collect(doc, repo):
            claim['doc'] = str(doc)
            claims.append(claim)

    # Counted before --only filters the display, so the exit status always sees every break.
    breaks = sum(c['verdict'] == 'BREAKS-ON-USE' for c in claims)
    needs_ai = sum(c['verdict'] == 'NEEDS-AI' for c in claims)

    if args.only == 'unresolved':
        claims = [c for c in claims if c['verdict'] == 'UNRESOLVED']
    elif args.only == 'problems':
        claims = [c for c in claims if c['verdict'] in ('BREAKS-ON-USE', 'IMPRECISE', 'NEEDS-AI')]

    if args.json:
        for c in claims:
            print(json.dumps(c, ensure_ascii=False))
    else:
        for c in claims:
            print(f"{c['verdict']:<14} {c['kind']:<8} {c['doc']}:{c['line']:<5} {c['quote']}")
            if c['verdict'] != 'TRUE':
                print(f"{'':14} {'':8} └─ {c['evidence']}")

        counts = {}
        for c in claims:
            counts[c['verdict']] = counts.get(c['verdict'], 0) + 1
        print('\nCOUNTS: ' + ', '.join(f'{k}={v}' for k, v in sorted(counts.items())) + f', total={len(claims)}')
        print('UNRESOLVED claims need a human or a model to adjudicate — they are not passes.')
        if needs_ai:
            print(f'NEEDS-AI claims: {needs_ai}. A missing path stands next to a negation; have a model or a '
                  'reviewer decide whether each absence is intended or the instruction is broken.')

    if args.fail_on_breaks:
        if breaks:
            print(f'\n{breaks} claim(s) would break an agent that follows them. Fix the code or the text.',
                  file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
