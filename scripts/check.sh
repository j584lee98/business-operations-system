#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"

if [[ -x .venv/Scripts/python.exe ]]; then
    python=".venv/Scripts/python.exe"
elif [[ -x .venv/bin/python ]]; then
    python=".venv/bin/python"
else
    printf '%s\n' "Project virtual environment not found. Run the setup commands in README.md first." >&2
    exit 1
fi

printf '\n%s\n' '==> Linting with Ruff'
"$python" -m ruff check src tests

printf '\n%s\n' '==> Running unit and integration tests'
"$python" -m pytest

printf '\n%s\n' '==> Checking unstaged changes for whitespace errors'
git --no-pager diff --check

printf '\n%s\n' '==> Checking staged changes for whitespace errors'
git --no-pager diff --cached --check

printf '\n%s\n' 'All checks passed.'
