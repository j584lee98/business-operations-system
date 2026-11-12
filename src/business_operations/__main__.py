"""Review an overdue-order draft from the terminal."""

import argparse
import sqlite3
import sys
from pathlib import Path

from pydantic import ValidationError

from business_operations.models import OverdueOrderInput, OverdueOrderOutput
from business_operations.reviews import (
    ReviewDecision,
    get_review,
    list_reviews,
    save_review,
)
from business_operations.workflows import draft_overdue_order_response


DATABASE_PATH = Path("business_operations.sqlite3")


def main() -> int:
    parser = argparse.ArgumentParser(description="Review overdue-order drafts.")
    commands = parser.add_subparsers(dest="command")
    list_parser = commands.add_parser(
        "list", help="List the 50 most recent saved reviews."
    )
    list_parser.add_argument(
        "--order-id", type=nonempty_order_id, help="Exact order ID."
    )
    list_parser.add_argument(
        "--decision",
        choices=[decision.value for decision in ReviewDecision],
        help="Filter by review decision.",
    )
    show_parser = commands.add_parser("show", help="Show a saved review.")
    show_parser.add_argument("review_id", type=int, help="Positive review ID.")
    args = parser.parse_args()

    if args.command == "show" and args.review_id <= 0:
        show_parser.error("review_id must be a positive integer")
    if args.command == "list":
        decision = ReviewDecision(args.decision) if args.decision is not None else None
        return show_saved_reviews("list", None, args.order_id, decision)
    if args.command == "show":
        return show_saved_reviews("show", args.review_id)

    return review_draft()


def nonempty_order_id(value: str) -> str:
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("order ID must not be blank")
    return value


def show_saved_reviews(
    command: str,
    review_id: int | None,
    order_id: str | None = None,
    decision: ReviewDecision | None = None,
) -> int:
    if not DATABASE_PATH.exists():
        print("No review database found in the current directory.", file=sys.stderr)
        return 1
    try:
        if command == "list":
            reviews = list_reviews(DATABASE_PATH, order_id=order_id, decision=decision)
            if not reviews:
                if order_id is not None or decision is not None:
                    print("No saved reviews match the filters.")
                else:
                    print("No saved reviews.")
            for summary in reviews:
                print(
                    f"{summary.id}\t{summary.reviewed_at}\t"
                    f"{summary.order_id}\t{summary.decision.value}"
                )
            return 0

        assert review_id is not None
        review = get_review(DATABASE_PATH, review_id)
        if review is None:
            print(f"Review {review_id} not found.", file=sys.stderr)
            return 1
        reviewed_reply_text = (
            f"\nReply presented for approval:\n{review.reviewed_reply}\n"
            if review.reviewed_reply is not None
            else ""
        )
        print(
            f"Review: {review.summary.id}\n"
            f"Reviewed at (UTC): {review.summary.reviewed_at}\n"
            f"Decision: {review.summary.decision.value}\n"
            f"Order ID: {review.summary.order_id}\n"
            f"Order status: {review.order_status}\n"
            f"\nCustomer message:\n{review.customer_message}\n"
            f"\nProposed reply:\n{review.proposed_reply}\n"
            f"{reviewed_reply_text}"
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
        status = input(
            "Order status (processing, shipped, delayed, delivered, unknown): "
        )
        request = OverdueOrderInput.model_validate(
            {
                "customer_message": customer_message,
                "order": {"order_id": order_id, "status": status},
            }
        )
        draft = draft_overdue_order_response(request)
        print(f"\nProposed reply:\n{draft.proposed_reply}")
        edited_reply = input("Edit reply (press Enter to keep as proposed): ")
        reviewed_reply = OverdueOrderOutput(
            proposed_reply=edited_reply
            if edited_reply.strip()
            else draft.proposed_reply,
            follow_up_task=draft.follow_up_task,
        )
        print(f"\nReply presented for approval:\n{reviewed_reply.proposed_reply}")
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
        print(
            "Invalid decision; enter yes or no. No decision recorded.", file=sys.stderr
        )
        return 2

    review_decision = decisions[decision]
    try:
        review_id = save_review(
            DATABASE_PATH, request, draft, reviewed_reply, review_decision
        )
    except sqlite3.Error as error:
        print(f"Could not save review; no decision recorded: {error}", file=sys.stderr)
        return 1

    print(
        f"Reply {review_decision.value} and saved as review {review_id}. "
        "No message was sent and no task was created."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
