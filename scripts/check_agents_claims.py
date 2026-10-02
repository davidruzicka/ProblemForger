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
    import      - does a module path plausibly exist on disk?
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
import functools
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# backticked path with a file extension, or a directory path ending in /; leading ./ and ../ are
# kept so resolve_path can check them, including whether they escape the repository, and a
# dot-prefixed first segment (.github/) is a path like any other
_EXT = r'py|md|mjs|js|json|toml|txt|ya?ml|sh'
_PARENTS = r'(?:\.{1,2}/)*\.?'
# General extensions require a slash; bare domains and version strings are not file claims.
PATH_RE = re.compile(
    rf'`(?P<path>{_PARENTS}[\w][\w ./-]*(?:\.(?:{_EXT})|/)'
    rf'|{_PARENTS}[\w][\w ./-]*/[\w .-]+\.[a-zA-Z][a-zA-Z0-9]*)`'
)
# Markdown destinations identify paths even without an extension; an #anchor is not part of the path,
# and any character in it must be accepted, or a dot in the anchor hides the file claim entirely
# Angle-wrapped destinations must close before the optional title; the brackets are not path data.
_LINK_TARGET = (
    rf'(?P<angle><)?(?P<path>/?{_PARENTS}[\w][\w./-]*)'
    r'(?:#[^)\s<>]*)?(?(angle)>)(?:\s+(?:"[^"\n]*"|\'[^\'\n]*\'))?'
)
LINK_RE = re.compile(rf'\]\({_LINK_TARGET}\)')
REFERENCE_RE = re.compile(rf'^[ \t]{{0,3}}\[[^\]\n]+\]:[ \t]+{_LINK_TARGET}[ \t]*$')
IMPORT_RE = re.compile(
    r'^\s*(?:from\s+(?P<from>[\w.]+)\s+import\s'
    r'|import\s+(?P<mod>[\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*))',
    re.M,
)
# a fence may be indented, e.g. inside a list item
FENCE_RE = re.compile(r'^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$')
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
    lines = text.splitlines()
    open_at = None
    lang = ''
    fence = ''
    for i, line in enumerate(lines, start=1):
        m = FENCE_RE.match(line)
        if not m:
            continue
        marker, info = m.group('fence'), m.group('info').strip()
        if open_at is None:
            if marker[0] == '`' and '`' in info:
                continue
            open_at, fence = i, marker
            lang = info.split()[0] if info else ''
        elif marker[0] == fence[0] and len(marker) >= len(fence) and not info:
            yield lang, open_at, i, '\n'.join(lines[open_at:i - 1])
            open_at = None

    if open_at is not None:
        yield lang, open_at, len(lines) + 1, '\n'.join(lines[open_at:])


def in_fence(line_no, blocks):
    return any(start < line_no < end for _, start, end, _ in blocks)


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
    that module, not to the repo root, so try the document's own directory first.
    """
    repo_abs = repo.resolve()
    bare = raw.lstrip('/')
    candidates = []

    for base, label in ((doc_dir, 'relative to the file'), (repo, 'repo-relative')):
        candidate = (base / bare).resolve()
        try:
            relative = candidate.relative_to(repo_abs)
        except ValueError:
            continue
        candidates.append(str(relative))
        if candidate.exists() and committable(repo_abs, candidate.relative_to(repo_abs)):
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
    if separator and '/' not in head and '/' in tail:
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


def first_party_roots(repo):
    """Top-level names that could be repo packages. Anything else is stdlib/third-party."""
    roots = set()
    for p in repo.iterdir():
        if not p.is_dir() or p.name.startswith('.') or p.name in SKIP_DIR_PARTS:
            continue
        # an ignored directory such as build/ exists only locally and must not shadow a package
        if not committable(repo, Path(p.name)):
            continue
        roots.add(p.name)
        # Packages one level below a top-level directory: <dir>/<package>/__init__.py, and under
        # src/ also PEP 420 namespace packages without __init__.py. Those must contain Python, or
        # an asset folder such as src/http/ would shadow the stdlib or a third-party name.
        for child in p.iterdir():
            if exists_here(repo, child) and child.is_dir() and ((child / '__init__.py').exists()
                                   or (p.name == 'src' and next(child.rglob('*.py'), None))):
                roots.add(child.name)
    return roots


def import_verdict(repo, dotted, roots, doc_dir):
    """None = not a claim about this repo (stdlib/third-party), else (verdict, evidence)."""
    # An instruction file within a regular package supplies the snippet's package context.
    # Keep namespace ancestors; src/ is an import root, as in first_party_roots().
    # Without that context, a relative import cannot be tested as an absolute module path.
    if dotted.startswith('.'):
        directory = doc_dir.resolve()
        if not directory.is_relative_to(repo) or not exists_here(repo, directory / '__init__.py'):
            return 'UNRESOLVED', f'{dotted}: no regular package context for this instruction file'
        package = directory.relative_to(repo).parts
        if package[:1] == ('src',):
            package = package[1:]
        if not package:
            return 'UNRESOLVED', f'{dotted}: no regular package context for this instruction file'
        try:
            dotted = importlib.util.resolve_name(dotted, '.'.join(package))
        except ImportError:
            return 'BREAKS-ON-USE', 'relative import escapes the scoped package'
    top = dotted.split('.')[0]
    if top not in roots:
        return None
    rel = Path(*dotted.split('.'))
    # an ignored directory is not a place modules are imported from in a clean checkout
    bases = [repo, *(p for p in repo.iterdir()
                     if p.is_dir() and p.name not in SKIP_DIR_PARTS and committable(repo, Path(p.name)))]
    for base in bases:
        # a directory without __init__.py still imports as a PEP 420 namespace package
        if exists_here(repo, (base / rel).with_suffix('.py')) or exists_here(repo, base / rel):
            return 'TRUE', f'module path {dotted}'
    # A namespace package can continue in an installed distribution (google.protobuf next to a
    # repo's google.myteam), so a submodule missing here does not prove the import breaks.
    if any(git_ignores(repo, str((base / rel).relative_to(repo)) + suffix)
           for base in bases for suffix in ('.py', '/')):
        return 'UNRESOLVED', f'{dotted} is gitignored: generated at build or run time; absent by design'
    if any(exists_here(repo, base / top) and not exists_here(repo, base / top / '__init__.py')
           for base in bases):
        return 'UNRESOLVED', f'{dotted} not in the repo; namespace package {top} may continue outside it'
    return 'BREAKS-ON-USE', f'module path {dotted}'


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


def collect(doc, repo):
    text = doc.read_text(encoding='utf-8', errors='replace')
    blocks = list(fenced_blocks(text))
    claims = []

    seen = set()

    def add(kind, line, quote, verdict, evidence):
        # The same path often appears twice on one line (backticked and as a link target).
        key = (kind, line, quote.strip()[:200])
        if key in seen:
            return
        seen.add(key)
        claims.append({
            'kind': kind, 'line': line, 'quote': quote.strip()[:200],
            'verdict': verdict, 'evidence': evidence,
        })

    for line_no, line in enumerate(text.splitlines(), start=1):
        # Explicit destinations take precedence when a backticked label names the same path.
        for m in list(LINK_RE.finditer(line)) + list(REFERENCE_RE.finditer(line)) + list(PATH_RE.finditer(line)):
            raw = m.group('path')
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
            add('path', line_no, raw, verdict, detail)

        for m in EXAMPLE_RE.finditer(line):
            found = git_has(repo, m.group('example'))
            if found is None:
                add('example', line_no, m.group('example'), 'UNRESOLVED', 'git log unavailable')
            else:
                add('example', line_no, m.group('example'),
                    'TRUE' if found else 'IMPRECISE',
                    'present in git log' if found else 'no commit with this message in history; fine if illustrative')

        if not in_fence(line_no, blocks):
            if PROCESS_RE.search(line):
                add('process', line_no, line, 'UNRESOLVED', 'corroborate against docs/ or code')
            for m in CONFIG_RE.finditer(line):
                add('config', line_no, m.group(0), 'UNRESOLVED',
                    f'read the config file and compare {m.group("key")}')

    roots = first_party_roots(repo)
    for lang, start, end, body in blocks:
        if lang in PYTHON_LANGS:
            for m in IMPORT_RE.finditer(body):
                if m.group('from'):
                    targets = [(m.group('from'), m.group(0).strip())]
                else:
                    # `import a, b as c` names several modules; each is its own claim
                    names = [part.split()[0] for part in m.group('mod').split(',')]
                    targets = [(name, f'import {name}') for name in names]
                for dotted, quote in targets:
                    verdict = import_verdict(repo, dotted, roots, doc.parent)
                    if verdict is None:
                        continue  # stdlib or third-party: not a claim about this repo
                    add('import', start, quote, *verdict)
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
