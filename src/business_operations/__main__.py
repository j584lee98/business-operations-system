"""Review an overdue-order draft from the terminal."""

import argparse
import sqlite3
import sys
from pathlib import Path

from pydantic import ValidationError

from business_operations.models import OverdueOrderInput
from business_operations.reviews import ReviewDecision, get_review, list_reviews, save_review
from business_operations.workflows import draft_overdue_order_response


DATABASE_PATH = Path("business_operations.sqlite3")


def main() -> int:
    parser = argparse.ArgumentParser(description="Review overdue-order drafts.")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("list", help="List the 50 most recent saved reviews.")
    show_parser = commands.add_parser("show", help="Show a saved review.")
    show_parser.add_argument("review_id", type=int, help="Positive review ID.")
    args = parser.parse_args()

    if args.command == "show" and args.review_id <= 0:
        show_parser.error("review_id must be a positive integer")
    if args.command in ("list", "show"):
        return show_saved_reviews(args.command, args.review_id if args.command == "show" else None)

    return review_draft()


def show_saved_reviews(command: str, review_id: int | None) -> int:
    if not DATABASE_PATH.exists():
        print("No review database found in the current directory.", file=sys.stderr)
        return 1
    try:
        if command == "list":
            reviews = list_reviews(DATABASE_PATH)
            if not reviews:
                print("No saved reviews.")
            for review in reviews:
                print(
                    f"{review.id}\t{review.reviewed_at}\t"
                    f"{review.order_id}\t{review.decision.value}"
                )
            return 0

        assert review_id is not None
        review = get_review(DATABASE_PATH, review_id)
        if review is None:
            print(f"Review {review_id} not found.", file=sys.stderr)
            return 1
        print(
            f"Review: {review.summary.id}\n"
            f"Reviewed at (UTC): {review.summary.reviewed_at}\n"
            f"Decision: {review.summary.decision.value}\n"
            f"Order ID: {review.summary.order_id}\n"
            f"Order status: {review.order_status}\n"
            f"\nCustomer message:\n{review.customer_message}\n"
            f"\nProposed reply:\n{review.proposed_reply}\n"
            f"\nSuggested follow-up:\n{review.follow_up_task}"
        )
        return 0
    except (sqlite3.Error, ValueError) as error:
        print(f"Could not read reviews: {error}", file=sys.stderr)
        return 1


def review_draft() -> int:
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
