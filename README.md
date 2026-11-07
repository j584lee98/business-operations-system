# Business Operations System

An early foundation for an AI operations manager. The first workflow will help
an owner respond to a customer asking about an overdue order.

## Current scope

This project currently defines validated input and output models for that
workflow. It does not generate or send replies, approve actions, connect to
external services, or save workflow state.

The input contains a customer message and an order ID and status. The output
contains a proposed reply and a follow-up task. `unknown` is available when the
order status is not known.

## Setup

Python 3.10 or later is required. From PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

FastAPI, a database, and a model provider can be added when the workflow needs
them; they are not required for these initial models.
