"""Review an overdue-order draft from the terminal."""

import sqlite3
import sys
from pathlib import Path

from pydantic import ValidationError

from business_operations.models import OverdueOrderInput
from business_operations.reviews import ReviewDecision, save_review
from business_operations.workflows import draft_overdue_order_response


DATABASE_PATH = Path("business_operations.sqlite3")


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

    decisions = {"yes": ReviewDecision.APPROVED, "no": ReviewDecision.REJECTED}
    if decision not in decisions:
        print("Invalid decision; enter yes or no. No decision recorded.", file=sys.stderr)
        return 2

    review_decision = decisions[decision]
    try:
        review_id = save_review(DATABASE_PATH, request, draft, review_decision)
    except sqlite3.Error as error:
        print(f"Could not save review; no decision recorded: {error}", file=sys.stderr)
        return 1

    print(
        f"Draft {review_decision.value} and saved as review {review_id}. "
        "No message was sent and no task was created."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
