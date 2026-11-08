# Business Operations System

An early foundation for an AI operations manager. The first workflow will help
an owner respond to a customer asking about an overdue order.

## Current scope

This project defines validated input and output models, a deterministic
drafting function, and a terminal-based draft review. It does not send replies,
create tasks, or connect to external services.

The input contains a customer message and an order ID and status. The output
contains a proposed reply and a follow-up task. `unknown` is available when the
order status is not known.

The drafting function uses the supplied order ID and status to produce a
template reply and follow-up task. It does not interpret the customer message
or verify the order status. The result is a draft for the owner to review; no
message is sent and no task is created. Approval or rejection is saved locally
but does not trigger an action.

## Setup

Python 3.10 or later is required. From PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

SQLite is included with Python; no separate database service is needed.
FastAPI and a model provider can be added when the workflow needs them.

## Review a draft

After setup, run:

```powershell
.\.venv\Scripts\python.exe -m business_operations
```

Enter a customer message, order ID, and order status, then review the proposed
reply and follow-up. Enter `yes` to approve the draft or `no` to reject it.
An invalid input or decision ends the run without recording a decision.

Completed reviews are saved to `business_operations.sqlite3` in the current
working directory, along with the customer message, order details, draft,
decision, and UTC review time. Runs from different directories use different
databases. The file is ignored by Git, but is not encrypted: use sample data
until appropriate data protection is in place. If saving fails, the program
reports an error instead of confirming the decision.

To inspect saved reviews from PowerShell in the same directory:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; con = sqlite3.connect('business_operations.sqlite3'); print(*con.execute('SELECT id, reviewed_at, order_id, decision FROM reviews'), sep='\n'); con.close()"
```

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
