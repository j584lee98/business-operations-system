import pytest
from pydantic import ValidationError

from business_operations.models import OrderStatus, OverdueOrderInput, OverdueOrderOutput


def test_workflow_input_accepts_sample_order():
    workflow_input = OverdueOrderInput(
        customer_message="  Where is my order?  ",
        order={"order_id": "ORD-123", "status": "delayed"},
    )

    assert workflow_input.customer_message == "Where is my order?"
    assert workflow_input.order.status is OrderStatus.DELAYED
    assert workflow_input.model_dump(mode="json") == {
        "customer_message": "Where is my order?",
        "order": {"order_id": "ORD-123", "status": "delayed"},
    }


def test_workflow_output_accepts_a_draft_and_follow_up():
    output = OverdueOrderOutput(
        proposed_reply="Your order is delayed. We will follow up.",
        follow_up_task="Check the shipment status.",
    )

    assert output.follow_up_task == "Check the shipment status."


@pytest.mark.parametrize(
    "data",
    [
        {"customer_message": " ", "order": {"order_id": "ORD-123", "status": "delayed"}},
        {"customer_message": "Where is it?", "order": {"order_id": "", "status": "delayed"}},
        {"customer_message": "Where is it?", "order": {"order_id": "ORD-123", "status": "late"}},
        {"customer_message": "Where is it?", "order": {"order_id": "ORD-123"}},
        {"customer_message": "Where is it?", "order": {"order_id": "ORD-123", "status": "delayed"}, "extra": True},
    ],
)
def test_workflow_input_rejects_invalid_data(data):
    with pytest.raises(ValidationError):
        OverdueOrderInput.model_validate(data)


@pytest.mark.parametrize(
    "data",
    [
        {"proposed_reply": "", "follow_up_task": "Check the shipment status."},
        {"proposed_reply": "We will check.", "follow_up_task": " "},
        {"proposed_reply": "We will check."},
        {"proposed_reply": "We will check.", "follow_up_task": "Check.", "approved": True},
    ],
)
def test_workflow_output_rejects_invalid_data(data):
    with pytest.raises(ValidationError):
        OverdueOrderOutput.model_validate(data)
