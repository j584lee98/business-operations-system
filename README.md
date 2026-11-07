# Business Operations System

An early foundation for an AI operations manager. The first workflow will help
an owner respond to a customer asking about an overdue order.

## Current scope

This project defines validated input and output models and a deterministic
drafting function for that workflow. It does not send replies, approve actions,
connect to external services, or save workflow state.

The input contains a customer message and an order ID and status. The output
contains a proposed reply and a follow-up task. `unknown` is available when the
order status is not known.

The drafting function uses the supplied order ID and status to produce a
template reply and follow-up task. It does not interpret the customer message
or verify the order status. The result is a draft for the owner to review; no
message is sent and no task is created.

## Setup

Python 3.10 or later is required. From PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

FastAPI, a database, and a model provider can be added when the workflow needs
them; they are not required for these initial models.

## Try the workflow

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
