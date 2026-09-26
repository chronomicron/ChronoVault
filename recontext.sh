#!/usr/bin/env bash

# ChronoVault context bootstrap
#
# Provides a new AI development session with a compact description of
# repository state and everything that has changed since the most recent
# reviewed context baseline.
#
# This script is intentionally READ-ONLY. It must not modify the repository.

set -u

echo "============================================================"
echo " ChronoVault Recontextualization"
echo "============================================================"
echo

# Make sure we're inside the repository.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"

if [ -z "${ROOT:-}" ]; then
    echo "ERROR: This script must be run inside the ChronoVault Git repository."
    exit 1
fi

cd "$ROOT"

echo "Repository:"
echo "  $ROOT"
echo

echo "Current branch:"
git branch --show-current
echo

echo "Current HEAD:"
git log -1 --format="  %h  %cd  %s" --date=short
echo

echo "Working tree:"
if [ -z "$(git status --porcelain)" ]; then
    echo "  Clean"
else
    git status --short
fi
echo

# Find the newest annotated context baseline by creation date.
BASELINE="$(
    git tag --list 'context-baseline-*' \
        --sort=-creatordate |
    head -n 1
)"

if [ -z "$BASELINE" ]; then
    echo "No context-baseline-* tag exists."
    echo
    echo "Read AGENTS.md and CHRONOVAULT_HANDOFF.md and perform normal"
    echo "progressive context discovery."
    exit 0
fi

echo "Latest context baseline:"
echo "  $BASELINE"
echo

echo "Baseline commit:"
git log -1 --format="  %h  %cd  %s" --date=short "$BASELINE"
echo

echo "------------------------------------------------------------"
echo " Commits since baseline"
echo "------------------------------------------------------------"

if git diff --quiet "$BASELINE"..HEAD; then
    echo "No committed changes since $BASELINE."
else
    git log --oneline --decorate "$BASELINE"..HEAD
fi

echo

echo "------------------------------------------------------------"
echo " Files changed since baseline"
echo "------------------------------------------------------------"

CHANGED_FILES="$(git diff --name-status "$BASELINE"..HEAD)"

if [ -z "$CHANGED_FILES" ]; then
    echo "No committed file changes since $BASELINE."
else
    echo "$CHANGED_FILES"
fi

echo

echo "------------------------------------------------------------"
echo " Uncommitted changes"
echo "------------------------------------------------------------"

if [ -z "$(git status --porcelain)" ]; then
    echo "None."
else
    git status --short
fi

echo

echo "------------------------------------------------------------"
echo " Context instructions"
echo "------------------------------------------------------------"

cat <<EOF

1. Read AGENTS.md first.
2. Read CHRONOVAULT_HANDOFF.md for persistent contextual knowledge.
3. Treat $BASELINE as the most recent reviewed context checkpoint.
4. Review the commits and changed files listed above.
5. Use AGENTS.md to identify documentation relevant to the current task.
6. Read only the relevant module documentation and implementation.
7. Expand into adjacent modules only when dependencies require it.
8. Consult roadmap.md before changing known problematic or unfinished behavior.
9. Current source code remains authoritative for implemented behavior.
10. Do not modify files merely as part of recontextualization.

============================================================
 Recontextualization report complete
============================================================
EOF
