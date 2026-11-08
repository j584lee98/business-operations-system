"""Store completed overdue-order reviews locally."""

import sqlite3
from contextlib import closing
from enum import Enum
from pathlib import Path

from business_operations.models import OverdueOrderInput, OverdueOrderOutput


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


def save_review(
    database_path: Path,
    request: OverdueOrderInput,
    draft: OverdueOrderOutput,
    decision: ReviewDecision,
) -> int:
    """Save a completed review and return its local ID."""
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                reviewed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                customer_message TEXT NOT NULL,
                order_id TEXT NOT NULL,
                order_status TEXT NOT NULL,
                proposed_reply TEXT NOT NULL,
                follow_up_task TEXT NOT NULL,
                decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected'))
            )
            """
        )
        cursor = connection.execute(
            """
            INSERT INTO reviews
                (customer_message, order_id, order_status, proposed_reply, follow_up_task, decision)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.customer_message,
                request.order.order_id,
                request.order.status.value,
                draft.proposed_reply,
                draft.follow_up_task,
                decision.value,
            ),
        )
        review_id = cursor.lastrowid
        if review_id is None:
            raise RuntimeError("SQLite did not return a review ID")
        return review_id
