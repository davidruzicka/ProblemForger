#!/bin/bash
# Tests for scripts/review_diff.sh. Every check has a scenario that MUST make it fail:
# for a detector the dangerous direction is "passes when it should not", not the reverse.
#
# Run without arguments; builds throwaway repositories under the temp directory and removes them.

set -u

GATE="$(cd "$(dirname "$0")/.." && pwd)/scripts/review_diff.sh"
failures=0

report() {
    if [ "$1" = 'ok' ]; then
        printf '  ok    %s\n' "$2"
    else
        printf '  FAIL  %s\n' "$2"
        failures=$((failures + 1))
    fi
}

expect_exit() {
    local expected="$1" actual="$2" name="$3"
    [ "$expected" = "$actual" ] && report ok "$name" || report fail "$name (expected $expected, got $actual)"
}

# Repository with one method and one call to it through `self` in a subclass, which can only mean
# that method; branch 'baseline' holds the state before the change.
new_repo() {
    local dir
    dir=$(mktemp -d)
    git -C "$dir" init -q .
    git -C "$dir" config user.email test@example.com
    git -C "$dir" config user.name Test
    mkdir -p "$dir/pkg"
    printf 'class Widget:\n    def refreshV2(self):\n        return 1\n' > "$dir/pkg/a.py"
    printf 'class Special(Widget):\n    def use(self): return self.refreshV2()\n' > "$dir/pkg/b.py"
    git -C "$dir" add -A
    git -C "$dir" commit -qm base
    git -C "$dir" branch -q baseline
    echo "$dir"
}

run_gate() {
    local dir="$1"; shift
    (cd "$dir" && "$GATE" "$@" >/dev/null 2>&1)
    echo $?
}

printf 'Checks that must fail:\n'

# An orphaned reference found before commit - exactly how the gate is run.
repo=$(new_repo)
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'orphaned reference in uncommitted change'
git -C "$repo" commit -qam removed
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'orphaned reference after commit'
rm -rf "$repo"

# An async method must survive name extraction. It must exist at baseline already - a method
# added and removed inside the range never appears in the net diff, and that is correct.
repo=$(mktemp -d)
git -C "$repo" init -q .
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
mkdir -p "$repo/pkg"
printf 'class Widget:\n    async def loadAll(self):\n        return 2\n' > "$repo/pkg/a.py"
printf 'class Special(Widget):\n    def use(self): return self.loadAll()\n' > "$repo/pkg/b.py"
git -C "$repo" add -A
git -C "$repo" commit -qm base
git -C "$repo" branch -q baseline
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'orphaned reference to an async method'
rm -rf "$repo"

# A same-named method remains elsewhere - grep cannot tell which class the call means, so the
# check must not switch off (the definition count dropped) but must not fail either: it warns
# and names the remaining definitions.
repo=$(mktemp -d)
git -C "$repo" init -q .
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
mkdir -p "$repo/pkg"
printf 'class Widget:\n    def refreshV2(self):\n        return 1\n' > "$repo/pkg/a.py"
printf 'class Other:\n    def refreshV2(self):\n        return 9\n' > "$repo/pkg/d.py"
printf 'def use(widget):\n    return widget.refreshV2()\n' > "$repo/pkg/b.py"
git -C "$repo" add -A
git -C "$repo" commit -qm base
git -C "$repo" branch -q baseline
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
out=$( (cd "$repo" && "$GATE" --target baseline) 2>&1 )
code=$?
expect_exit 0 "$code" 'same-named method elsewhere does not fail'
case "$out" in
    *'refreshV2'*'pkg/d.py'*'pkg/b.py'*) report ok 'same-named method elsewhere warns with definitions and calls' ;;
    *) report fail "same-named method elsewhere is not reported: $out" ;;
esac
rm -rf "$repo"

# A call on any other receiver may be a library object (sqlite3's `connection.close()`), so with
# the last definition gone it warns; `cls.` is as certain as `self.` and fails.
repo=$(new_repo)
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
printf 'def use(connection):\n    return connection.refreshV2()\n' > "$repo/pkg/b.py"
out=$( (cd "$repo" && "$GATE" --target baseline) 2>&1 )
code=$?
expect_exit 0 "$code" 'call on another receiver does not fail'
case "$out" in
    *'Possible reference to removed method refreshV2'*'pkg/b.py'*) report ok 'call on another receiver warns' ;;
    *) report fail "call on another receiver is not reported: $out" ;;
esac
printf 'class Special(Widget):\n    @classmethod\n    def make(cls): return cls.refreshV2()\n' > "$repo/pkg/b.py"
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'call through cls fails'
rm -rf "$repo"

# A `def name` inside a comment is not a surviving definition.
repo=$(new_repo)
printf '# Call def refreshV2() through use().\n' > "$repo/pkg/c.py"
git -C "$repo" add -A
git -C "$repo" commit -qm comment
git -C "$repo" branch -qf baseline
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'orphaned reference despite def in a comment'
rm -rf "$repo"

# A removed top-level function is not a method: `c.close()` on a library object is unrelated.
repo=$(mktemp -d)
git -C "$repo" init -q .
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
printf 'def close():\n    pass\n' > "$repo/util.py"
printf 'import sqlite3\nc = sqlite3.connect(":memory:")\nc.close()\n' > "$repo/app.py"
git -C "$repo" add -A
git -C "$repo" commit -qm base
git -C "$repo" branch -q baseline
printf '' > "$repo/util.py"
expect_exit 0 "$(run_gate "$repo" --target baseline)" 'removed top-level function is not an orphaned method'
rm -rf "$repo"

# Moving a method to another file is not a removal and must not be reported.
repo=$(new_repo)
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
printf 'class Widget:\n    def refreshV2(self):\n        return 1\n' > "$repo/pkg/moved.py"
git -C "$repo" add -A
expect_exit 0 "$(run_gate "$repo" --target baseline)" 'moved method is not reported'
rm -rf "$repo"

# Before a commit the new file is often not added yet; it must count all the same.
repo=$(new_repo)
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
printf 'class Widget:\n    def refreshV2(self):\n        return 1\n' > "$repo/pkg/moved.py"
expect_exit 0 "$(run_gate "$repo" --target baseline)" 'method moved into an untracked file is not reported'
rm -rf "$repo"

repo=$(new_repo)
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
printf 'def use(widget):\n    return None\n' > "$repo/pkg/b.py"
printf 'class Again(Widget):\n    def use(self): return self.refreshV2()\n' > "$repo/pkg/c.py"
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'orphaned reference from an untracked file'
printf 'Intro.\n<<<<<<< HEAD\n' > "$repo/pkg/notes.md"
expect_exit 1 "$(run_gate "$repo" --check conflict-markers)" 'conflict marker in an untracked file'
rm -rf "$repo"

# Every text file counts, not a list of extensions: requirements.txt and .gitignore conflict too.
repo=$(new_repo)
printf 'coverage\n<<<<<<< HEAD\n' > "$repo/requirements.txt"
git -C "$repo" add -A
expect_exit 1 "$(run_gate "$repo" --check conflict-markers)" 'conflict marker in .txt'
rm -rf "$repo"

repo=$(new_repo)
printf 'Intro.\n<<<<<<< HEAD\nours\n>>>>>>> other\n' > "$repo/pkg/notes.md"
git -C "$repo" add -A
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'conflict marker in .md'
expect_exit 1 "$(run_gate "$repo" --check conflict-markers)" 'conflict marker via --check'
rm -rf "$repo"

# A false path claim in AGENTS.md fails both the full run and the CI check.
repo=$(new_repo)
mkdir -p "$repo/scripts"
cp "$(dirname "$GATE")/check_agents_claims.py" "$repo/scripts/"
printf 'Read `pkg/missing.py` first.\n' > "$repo/AGENTS.md"
git -C "$repo" add -A
expect_exit 1 "$(run_gate "$repo" --target baseline)" 'false path claim in AGENTS.md'
expect_exit 1 "$(run_gate "$repo" --check agents-claims)" 'false path claim via --check'
printf 'Read `pkg/a.py` first.\n' > "$repo/AGENTS.md"
expect_exit 0 "$(run_gate "$repo" --check agents-claims)" 'true path claim via --check'
# A new scoped AGENTS.md is checked before it is added.
printf 'Read `pkg/missing.py` here.\n' > "$repo/pkg/AGENTS.md"
expect_exit 1 "$(run_gate "$repo" --check agents-claims)" 'false claim in an untracked AGENTS.md'
rm -rf "$repo"

# In CI a silent skip is a green job that checked nothing.
repo=$(new_repo)
expect_exit 2 "$(run_gate "$repo" --check agents-claims)" 'missing checker via --check'
mkdir -p "$repo/scripts"
cp "$(dirname "$GATE")/check_agents_claims.py" "$repo/scripts/"
expect_exit 2 "$(run_gate "$repo" --check agents-claims)" 'no tracked AGENTS.md via --check'
rm -rf "$repo"

repo=$(new_repo)
expect_exit 2 "$(run_gate "$repo" --target no-such-branch)" 'unknown target branch'
expect_exit 2 "$(run_gate "$repo" --check nonsense)" 'unknown check name'
expect_exit 2 "$(run_gate "$repo" --taget baseline)" 'typo in a flag'
# A branch given without --target must not be dropped in favor of the default; with a `main`
# branch present the default resolves, so only the argument check can produce exit 2.
git -C "$repo" branch -q main
expect_exit 2 "$(run_gate "$repo" baseline)" 'positional argument is rejected'
rm -rf "$repo"

printf 'Messages that must guide the reader:\n'

# An error without the list of options forces the reader into the source.
repo=$(new_repo)
out=$( (cd "$repo" && "$GATE" --check nonsense) 2>&1 )
case "$out" in
    *conflict-markers*agents-claims*) report ok 'unknown check lists the available ones' ;;
    *) report fail "unknown check does not list the available ones: $out" ;;
esac

out=$( (cd "$repo" && "$GATE" --taget baseline) 2>&1 )
case "$out" in
    *Usage:*) report ok 'unknown flag prints usage' ;;
    *) report fail "unknown flag does not print usage: $out" ;;
esac

out=$( (cd "$repo" && "$GATE" --target baselinee) 2>&1 )
case "$out" in
    *baseline*) report ok 'unknown branch suggests a similar one' ;;
    *) report fail "unknown branch does not suggest a similar one: $out" ;;
esac
rm -rf "$repo"

# Deleting lines another author wrote is a warning, not a failure. Both deleted lines come from
# one commit, which blame --porcelain describes only once; the count must still be per line.
repo=$(new_repo)
git -C "$repo" config user.email me@example.com
printf 'USE = None\n' > "$repo/pkg/b.py"
out=$( (cd "$repo" && "$GATE" --target baseline) 2>&1 )
code=$?
case "$out" in
    *'pkg/b.py (-2 lines written by someone else)'*) report ok 'foreign deletion counts every line' ;;
    *) report fail "foreign deletion is not reported: $out" ;;
esac
expect_exit 0 "$code" 'foreign deletion does not fail'

# A renamed file that loses foreign lines is blamed under its old path. The file is large
# enough that git still detects the rename after one of its lines is deleted.
repo2=$(new_repo)
printf 'A = 1\nB = 2\nC = 3\nD = 4\n' > "$repo2/pkg/consts.py"
git -C "$repo2" add -A
git -C "$repo2" commit -qm consts
git -C "$repo2" branch -qf baseline
git -C "$repo2" config user.email me@example.com
git -C "$repo2" mv pkg/consts.py pkg/renamed.py
printf 'A = 1\nB = 2\nC = 3\n' > "$repo2/pkg/renamed.py"
git -C "$repo2" add -A
out=$( (cd "$repo2" && "$GATE" --target baseline) 2>&1 )
case "$out" in
    *'pkg/renamed.py (-1 lines written by someone else)'*) report ok 'foreign deletion in a renamed file is reported' ;;
    *) report fail "foreign deletion in a renamed file is not reported: $out" ;;
esac
rm -rf "$repo2"

# Without an identity the author of a line cannot be told apart, so no false alarm.
git -C "$repo" config user.email ''
out=$( (cd "$repo" && "$GATE" --target baseline) 2>&1 )
case "$out" in
    *'written by someone else'*) report fail "unset user.email reports foreign deletions: $out" ;;
    *'user.email is not set'*) report ok 'unset user.email skips the foreign-deletion warning' ;;
    *) report fail "unset user.email is not explained: $out" ;;
esac
rm -rf "$repo"

# Your own lines are matched by the literal address, ignoring case: a dot is not a wildcard,
# and the same address typed in another case on another machine is still you.
repo=$(new_repo)
git -C "$repo" config user.email 'aXb@example.com'
printf 'def use(widget):\n    return widget.refreshV2()\n\n\ndef other():\n    return 2\n' > "$repo/pkg/b.py"
git -C "$repo" commit -qam 'add other'
git -C "$repo" branch -qf baseline
printf 'def use(widget):\n    return widget.refreshV2()\n' > "$repo/pkg/b.py"
git -C "$repo" config user.email 'a.b@example.com'
out=$( (cd "$repo" && "$GATE" --target baseline) 2>&1 )
case "$out" in
    *'pkg/b.py (-4 lines written by someone else)'*) report ok 'a dot in your address is not a wildcard' ;;
    *) report fail "a dot in your address matched another author: $out" ;;
esac
git -C "$repo" config user.email 'AXB@EXAMPLE.COM'
out=$( (cd "$repo" && "$GATE" --target baseline) 2>&1 )
case "$out" in
    *'written by someone else'*) report fail "your address in another case counts as foreign: $out" ;;
    *) report ok 'your address in another case is still you' ;;
esac
rm -rf "$repo"

# Option parsing without GNU getopt: both option forms, and a missing value.
repo=$(new_repo)
expect_exit 0 "$(run_gate "$repo" --target=baseline)" '--target=<branch> form'
expect_exit 0 "$(run_gate "$repo" -t baseline)" '-t <branch> form'
expect_exit 2 "$(run_gate "$repo" --target)" 'missing option value'
rm -rf "$repo"

printf 'Checks that must pass:\n'

repo=$(new_repo)
expect_exit 0 "$(run_gate "$repo" --target baseline)" 'clean tree'
expect_exit 0 "$(run_gate "$repo" --check conflict-markers)" 'clean tree via --check'
# A run from a subdirectory must see the whole repository, not just part of it.
printf 'class Widget:\n    pass\n' > "$repo/pkg/a.py"
expect_exit 1 "$(cd "$repo/pkg" && "$GATE" --target baseline >/dev/null 2>&1; echo $?)" 'run from a subdirectory finds the same'
rm -rf "$repo"

printf '\n'
if [ "$failures" -gt 0 ]; then
    printf 'Failed checks: %s\n' "$failures"
    exit 1
fi
printf 'All passed.\n'
