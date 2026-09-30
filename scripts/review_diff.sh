#!/bin/bash
# Pre-commit review of the change against the target branch.
#
# Catches a class of defects that tests miss because the logic is not wrong; an unsupported
# assumption about how the code is wired is: dropped merged work of others, an orphaned
# reference to a removed method, a conflict marker, a false claim in AGENTS.md.

# `git grep` pathspecs and relative paths are cwd-relative, so a run from a subdirectory
# would check only part of the tree and look identical to a clean run.
cd "$(git rev-parse --show-toplevel)" || exit 2

centered_text() {
    if [ -z "${CI:-}" ]; then
      termwidth="$(tput cols 2>/dev/null || echo 80)";
    else
      termwidth=60;
    fi
    padding="$(printf '%0.1s' ={1..500})"
    printf '\e[1;34m'
    printf '%*.*s %s %*.*s\n' 0 "$(((termwidth - 2 - ${#1}) / 2))" "$padding" "$1" 0 "$(((termwidth - 1 - ${#1}) / 2))" "$padding"
    printf '\e[0m'
}

usage() {
    echo "Usage: scripts/review_diff.sh [--target <branch>] [--check <name>]" >&2
}

exit_code=0

resolve_target() {
    if git rev-parse --verify --quiet "origin/$1" >/dev/null; then
        echo "origin/$1"
    elif git rev-parse --verify --quiet "$1" >/dev/null; then
        echo "$1"
    else
        local similar
        similar=$(git for-each-ref --format='%(refname:short)' 'refs/heads/*' 'refs/remotes/origin/*' \
            | grep -iF "$1" | head -3 | tr '\n' ' ')
        echo "Branch '$1' exists neither locally nor as origin/$1." >&2
        [ -n "$similar" ] && echo "Similar branches: $similar" >&2
        echo "If the branch is new, fetch it first: git fetch origin $1" >&2
        exit 2
    fi
}

show_net_diff() {
    centered_text "Change against $2"
    git diff --stat "$1"
    printf "\nReview the whole change: git diff %s\n" "$1"
}

# All checks below compare the merge base with the working tree, not with HEAD: the gate runs
# before commit, so uncommitted work is exactly what it must see. The merge base (not the target
# tip) keeps commits that landed on the target later from showing up as removed lines.
#
# Rewriting a file (delete some, add some) is the usual shape of dropping merged work, so a
# file that only loses lines is not enough; what decides is WHO wrote the deleted lines,
# so each deleted hunk is blamed at the merge base.
warn_on_foreign_deletions() {
    local base="$1" target="$2" me added deleted file old ranges start count foreign total_foreign=0 report=''
    me=$(git config user.email)
    # Without an identity every deleted line would count as foreign.
    if [ -z "$me" ]; then
        echo "git user.email is not set; skipping the check for deleted lines of other authors."
        return
    fi

    # -z numstat keeps paths unquoted and gives a rename as an empty path followed by the old and
    # new path; the text form's "pkg/{old.py => new.py}" is not a path git diff or blame accept.
    while IFS=$'\t' read -r -d '' added deleted file; do
        if [ -z "$file" ]; then
            IFS= read -r -d '' old
            IFS= read -r -d '' file
        else
            old="$file"
        fi
        [ "$deleted" = '0' ] || [ "$deleted" = '-' ] && continue
        foreign=0
        # Old-side ranges of deleted hunks; -U0 yields hunks without context, so the range is exact.
        # Deleted lines exist only under the old path at the merge base, so blame that one.
        ranges=$(git diff -M -U0 "$base" -- "$old" "$file" | sed -nE 's/^@@ -([0-9]+)(,([0-9]+))? .*/\1 \3/p')
        while read -r start count; do
            [ -z "$start" ] && continue
            count=${count:-1}
            [ "$count" -eq 0 ] && continue
            # --line-porcelain repeats the author for every line; --porcelain gives it once per commit.
            foreign=$((foreign + $(git blame --line-porcelain -L "$start,+$count" "$base" -- "$old" 2>/dev/null \
                | grep -c "^author-mail <\(.*\)>" || true)))
            foreign=$((foreign - $(git blame --line-porcelain -L "$start,+$count" "$base" -- "$old" 2>/dev/null \
                | grep -c "^author-mail <$me>" || true)))
        done <<< "$ranges"

        if [ "$foreign" -gt 0 ]; then
            report="$report  $file (-$foreign lines written by someone else)"$'\n'
            total_foreign=$((total_foreign + foreign))
        fi
    done < <(git diff -z -M --numstat "$base")

    if [ "$total_foreign" -gt 0 ]; then
        centered_text "Deleting lines someone else wrote"
        printf '%s' "$report"
        echo
        echo "Warning, not an error: confirm this is intended and not an overwrite of merged work."
        echo "Who wrote them and why: git log -p $target -- <file>   /   git blame $target -- <file>"
    fi
}

# A removed method that is still called fails only at runtime; static analysis does not
# resolve attribute calls on objects.
check_orphan_references() {
    local removed_names name hits
    # Digits in the name and `async def` must pass, or a truncated name is searched for and
    # the orphan slips through silently.
    removed_names=$(git diff "$1" -- '*.py' \
        | grep -E '^-\s*(async\s+)?def [a-zA-Z_][a-zA-Z0-9_]*' \
        | sed -E 's/^-\s*(async\s+)?def ([a-zA-Z_][a-zA-Z0-9_]*).*/\2/' | sort -u)

    [ -z "$removed_names" ] && return

    local before after definition
    for name in $removed_names; do
        # Only a line that starts with the keyword counts; `def name` in a comment or prose would
        # otherwise pass for a surviving definition and turn a real orphan into a warning.
        definition="^[[:space:]]*(async[[:space:]]+)?def $name\b"
        # A definition existing elsewhere is not enough: common names like `run` or `save`
        # repeat across classes and the check would switch off for them. What decides is
        # whether the definition count dropped against the merge base.
        before=$(git grep -cE "$definition" "$1" -- '*.py' 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
        after=$(git grep -cE "$definition" -- '*.py' 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
        if [ "$after" -ge "$before" ]; then
            continue
        fi
        hits=$(git grep -nE "\.$name\(" -- '*.py')
        [ -z "$hits" ] && continue
        # Grep cannot tell which class a call means. With no definition left the call can only
        # fail at runtime; with same-named definitions left it may be theirs, so only warn.
        if [ "$after" -eq 0 ]; then
            centered_text "Reference to removed method $name"
            echo "Definitions in the repo: $before before the change, none after. Remaining calls:"
            echo "$hits"
            echo
            echo "On a rename, update the calls too."
            exit_code=1
        else
            centered_text "Possible reference to removed method $name"
            echo "Definitions in the repo: $before before the change, $after after. Remaining definitions:"
            git grep -nE "$definition" -- '*.py'
            echo "Remaining calls:"
            echo "$hits"
            echo
            echo "Warning, not an error: confirm each call means one of the remaining definitions."
        fi
    done
}

check_conflict_markers() {
    local hits
    # A bare ======= is deliberately excluded: it is a heading underline in docs and docstrings.
    # One extension list serves both the local run and the CI job that calls --check.
    hits=$(git grep -nE '^(<{7} |>{7} )' -- '*.py' '*.md' '*.mjs' '*.js' '*.json' '*.toml' '*.sh' '*.yml' '*.yaml')
    if [ -n "$hits" ]; then
        centered_text "Conflict markers in tracked files"
        echo "$hits"
        exit_code=1
    fi
}

# Locally, a missing checker or no AGENTS.md is skipped silently: the branch may predate them.
# In CI a silent skip is the worst outcome (a green job that checked nothing), so --check fails.
check_agents_claims() {
    local strict="$1"
    local checker='scripts/check_agents_claims.py'
    if [ ! -f "$checker" ]; then
        [ "$strict" = 'strict' ] && { echo "Missing $checker; cannot run the check." >&2; exit 2; }
        return
    fi

    local docs
    docs=$(git ls-files '*AGENTS.md')
    if [ -z "$docs" ]; then
        [ "$strict" = 'strict' ] && { echo "No tracked AGENTS.md; nothing to check." >&2; exit 2; }
        return
    fi

    centered_text "Claims in AGENTS.md"
    # shellcheck disable=SC2086
    if ! python3 "$checker" $docs --fail-on-breaks; then
        exit_code=1
    fi
}

# Without checking the return value, a typo in a flag would review against the default branch,
# answering a question nobody asked.
OPTIONS=$(getopt -o t:c: --long target:,check: -- "$@") || { usage; exit 2; }
eval set -- "$OPTIONS"

TARGET=''
CHECK=''
while true; do
    case "$1" in
        -t|--target) TARGET="$2"; shift 2 ;;
        -c|--check) CHECK="$2"; shift 2 ;;
        --) break ;;
    esac
done

# A single check on its own; CI calls it so it has no copy of the same logic.
# Whole-tree checks need no target branch.
if [ -n "$CHECK" ]; then
    case "$CHECK" in
        conflict-markers) check_conflict_markers ;;
        agents-claims) check_agents_claims strict ;;
        *)
            echo "Unknown check '$CHECK'. Available: conflict-markers, agents-claims." >&2
            exit 2
            ;;
    esac
    exit $exit_code
fi

[ -z "$TARGET" ] && TARGET="main"
# `exit` inside command substitution ends only the subshell; pass the status on.
TARGET_REF=$(resolve_target "$TARGET") || exit $?
BASE=$(git merge-base "$TARGET_REF" HEAD) || exit 2

show_net_diff "$BASE" "$TARGET_REF"
warn_on_foreign_deletions "$BASE" "$TARGET_REF"
check_orphan_references "$BASE"
check_conflict_markers
check_agents_claims

printf "\n"
exit $exit_code
