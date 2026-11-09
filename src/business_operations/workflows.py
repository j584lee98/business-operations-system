"""Small, deterministic workflows for business operations."""

from business_operations.models import (
    OrderStatus,
    OverdueOrderInput,
    OverdueOrderOutput,
)


def draft_overdue_order_response(
    workflow_input: OverdueOrderInput,
) -> OverdueOrderOutput:
    """Prepare a draft and follow-up for an owner to review."""
    status_messages = {
        OrderStatus.PROCESSING: (
            "The order is still being processed.",
            "Check the order's processing status.",
        ),
        OrderStatus.SHIPPED: (
            "The order has shipped.",
            "Check the shipment's tracking status.",
        ),
        OrderStatus.DELAYED: (
            "The order is delayed.",
            "Check the cause of the delay and the latest delivery estimate.",
        ),
        OrderStatus.DELIVERED: (
            "The order is marked as delivered.",
            "Check the delivery details and whether the customer received the order.",
        ),
        OrderStatus.UNKNOWN: (
            "The order's status is currently unknown.",
            "Check the current order status.",
        ),
    }
    status_message, follow_up = status_messages[workflow_input.order.status]

    return OverdueOrderOutput(
        proposed_reply=(
            f"Thank you for contacting us about order {workflow_input.order.order_id}. "
            f"{status_message} We will check the details and follow up."
        ),
        follow_up_task=f"Order {workflow_input.order.order_id}: {follow_up}",
    )
