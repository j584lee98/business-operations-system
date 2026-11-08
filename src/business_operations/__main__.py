"""Review an overdue-order draft from the terminal."""

import sys

from pydantic import ValidationError

from business_operations.models import OverdueOrderInput
from business_operations.workflows import draft_overdue_order_response


def main() -> int:
    try:
        customer_message = input("Customer message: ")
        order_id = input("Order ID: ")
        status = input("Order status (processing, shipped, delayed, delivered, unknown): ")
        request = OverdueOrderInput.model_validate(
            {
                "customer_message": customer_message,
                "order": {"order_id": order_id, "status": status},
            }
        )
        draft = draft_overdue_order_response(request)
        print(f"\nProposed reply:\n{draft.proposed_reply}")
        print(f"\nSuggested follow-up:\n{draft.follow_up_task}")
        decision = input("\nApprove this draft? (yes/no): ").strip().lower()
    except ValidationError as error:
        print(f"Invalid workflow input:\n{error}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\nReview cancelled; no decision recorded.", file=sys.stderr)
        return 1

    if decision == "yes":
        print("Draft approved for this session. No message was sent and no task was created.")
        return 0
    if decision == "no":
        print("Draft rejected for this session. No message was sent and no task was created.")
        return 0

    print("Invalid decision; enter yes or no. No decision recorded.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
