"""Local API for previewing the overdue-order workflow."""

from fastapi import FastAPI

from business_operations.models import OverdueOrderInput, OverdueOrderOutput
from business_operations.workflows import draft_overdue_order_response


app = FastAPI(title="Business Operations System", version="0.1.0")


@app.post("/overdue-order/draft", response_model=OverdueOrderOutput)
def create_draft(request: OverdueOrderInput) -> OverdueOrderOutput:
    return draft_overdue_order_response(request)
