# Business Operations System

An early foundation for an AI operations manager. The first workflow will help
an owner respond to a customer asking about an overdue order.

## Current scope

This project defines validated input and output models, a deterministic
drafting function, a local draft-preview API, and a terminal-based draft
review. It does not send replies, create tasks, or connect to external services.

The input contains a customer message and an order ID and status. The output
contains a proposed reply and a follow-up task. `unknown` is available when the
order status is not known.

The drafting function uses the supplied order ID and status to produce a
template reply and follow-up task. It does not interpret the customer message
or verify the order status. The result is a draft for the owner to review; no
message is sent and no task is created. Approval or rejection is saved locally
but does not trigger an action.

## Setup

Python 3.10 or later is required. Install [uv](https://docs.astral.sh/uv/getting-started/installation/),
then run from PowerShell in the project directory:

```powershell
uv sync --locked --extra dev
.\.venv\Scripts\python.exe -m pytest
```

SQLite is included with Python; no separate database service is needed.
A model provider can be added when the workflow needs one.

`uv.lock` records resolved dependencies across supported Python versions and
platforms. Use `uv sync --locked --extra dev` to install them without changing
the lockfile. When updating dependencies, run `uv lock --upgrade`, review the
changes to `pyproject.toml` and `uv.lock`, then sync and run the checks.
Build tools and the uv installer itself are not locked by `uv.lock`.

## Check before committing

After setup, run the local checks with Bash (for example, Git Bash on Windows):

```bash
bash scripts/check.sh
```

The script runs Ruff's configured error, Pyflakes, and formatting checks,
mypy type checking, the full pytest suite (unit and CLI integration tests),
and Git whitespace checks for staged and unstaged changes. It stops and returns
a nonzero exit code when a check fails. Git's whitespace checks do not include
untracked files; stage new files before running the script to check them. The
checks use the project virtual environment and do not install packages or
modify source files. If dependencies are missing, rerun the install command
above.

Mypy checks application code in `src` against Python 3.10, including function
bodies without annotations. Tests are not yet included in type checking.

To apply Python formatting before running the checks, run:

```powershell
.\.venv\Scripts\python.exe -m ruff format src tests
```

GitHub Actions runs the same script on pushes, pull requests, and manual
workflow dispatches. It tests Python 3.10 and 3.14 on Linux and Windows.
Each combination runs once with locked dependencies and once with a fresh pip
resolution from the declared ranges; the latter does not test every possible
combination within those ranges.
For pull requests, a separate CI job also checks the diff between the pull
request's base commit and its checked-out merge commit for whitespace errors.
The script's Git checks continue to inspect local staged and unstaged changes.

Dependabot checks the uv lockfile, Python dependency declarations, and GitHub
Actions for updates weekly and proposes changes through pull requests.

## Review a draft

After setup, run:

```powershell
.\.venv\Scripts\python.exe -m business_operations
```

Enter a customer message, order ID, and order status. You can optionally
replace the proposed reply before deciding whether to approve or reject it.
The saved review retains both the generated reply and the exact reply presented
for approval. An invalid input or decision ends the run without recording a
decision.

Completed reviews are saved to `business_operations.sqlite3` in the current
working directory, along with the customer message, order details, generated
reply, reply presented for approval, decision, and UTC review time. Existing
databases are upgraded automatically when a new review is saved; earlier
reviews remain readable. Runs from different directories use different
databases. The file is ignored by Git, but is not encrypted: use sample data
until appropriate data protection is in place. If saving fails, the program
reports an error instead of confirming the decision.

To inspect saved reviews from PowerShell in the same directory:

```powershell
.\.venv\Scripts\python.exe -m business_operations list
.\.venv\Scripts\python.exe -m business_operations list --order-id ORD-123 --decision approved
.\.venv\Scripts\python.exe -m business_operations show 1
```

`list` shows up to 50 reviews, newest first, with their IDs, UTC review times,
order IDs, and decisions. `show` displays the saved request and draft for a
specific review ID. Optionally filter `list` by exact, case-sensitive
`--order-id`, `--decision` (`approved` or `rejected`), or both. Filters apply
before the 50-result limit. These commands only read the database; they do not
create one if it is missing or change any review.

## Use the drafting function

After setup, start Python with `.\.venv\Scripts\python.exe` and enter:

```python
from business_operations.models import Order, OrderStatus, OverdueOrderInput
from business_operations.workflows import draft_overdue_order_response

request = OverdueOrderInput(
    customer_message="Where is my order?",
    order=Order(order_id="ORD-123", status=OrderStatus.DELAYED),
)
draft = draft_overdue_order_response(request)
print(draft.proposed_reply)
print(draft.follow_up_task)
```

## Preview a draft through the API

Start the local server from the project directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn business_operations.api:app --host 127.0.0.1 --port 8000
```

In another PowerShell terminal, send a sample request:

```powershell
$body = @{
    customer_message = "Where is my order?"
    order = @{ order_id = "ORD-123"; status = "delayed" }
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/overdue-order/draft" -Method Post -ContentType "application/json" -Body $body
```

The endpoint returns a proposed reply and follow-up task, or a validation error
for invalid input. It does not save reviews, approve or send replies, or create
tasks. This development API has no authentication; keep it bound to localhost
and use sample data. Interactive API documentation is available at
`http://127.0.0.1:8000/docs` while the server is running.
