import pytest

from business_operations.models import Order, OrderStatus, OverdueOrderInput
from business_operations.workflows import draft_overdue_order_response


@pytest.mark.parametrize(
    ("status", "status_message", "follow_up"),
    [
        (
            OrderStatus.PROCESSING,
            "The order is still being processed.",
            "Check the order's processing status.",
        ),
        (
            OrderStatus.SHIPPED,
            "The order has shipped.",
            "Check the shipment's tracking status.",
        ),
        (
            OrderStatus.DELAYED,
            "The order is delayed.",
            "Check the cause of the delay and the latest delivery estimate.",
        ),
        (
            OrderStatus.DELIVERED,
            "The order is marked as delivered.",
            "Check the delivery details and whether the customer received the order.",
        ),
        (
            OrderStatus.UNKNOWN,
            "The order's status is currently unknown.",
            "Check the current order status.",
        ),
    ],
)
def test_draft_uses_order_status_and_identifies_follow_up(
    status, status_message, follow_up
):
    workflow_input = OverdueOrderInput(
        customer_message="Where is my order?",
        order=Order(order_id="ORD-123", status=status),
    )

    output = draft_overdue_order_response(workflow_input)

    assert output.proposed_reply == (
        "Thank you for contacting us about order ORD-123. "
        f"{status_message} We will check the details and follow up."
    )
    assert output.follow_up_task == f"Order ORD-123: {follow_up}"


def test_draft_uses_the_supplied_order_id():
    workflow_input = OverdueOrderInput(
        customer_message="Please check my order.",
        order=Order(order_id="OTHER-456", status=OrderStatus.UNKNOWN),
    )

    output = draft_overdue_order_response(workflow_input)

    assert "OTHER-456" in output.proposed_reply
    assert "OTHER-456" in output.follow_up_task
