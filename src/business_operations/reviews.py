"""Store completed overdue-order reviews locally."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from business_operations.models import OverdueOrderInput, OverdueOrderOutput


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReviewSummary:
    id: int
    reviewed_at: str
    order_id: str
    decision: ReviewDecision


@dataclass(frozen=True)
class SavedReview:
    summary: ReviewSummary
    customer_message: str
    order_status: str
    proposed_reply: str
    reviewed_reply: str | None
    follow_up_task: str


def _open_readonly(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)


def list_reviews(database_path: Path, limit: int = 50) -> list[ReviewSummary]:
    """Return recent reviews without creating or changing the database."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    with closing(_open_readonly(database_path)) as connection:
        rows = connection.execute(
            "SELECT id, reviewed_at, order_id, decision FROM reviews ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        ReviewSummary(
            id=row[0],
            reviewed_at=row[1],
            order_id=row[2],
            decision=ReviewDecision(row[3]),
        )
        for row in rows
    ]


def get_review(database_path: Path, review_id: int) -> SavedReview | None:
    """Return the exact stored review, or None when its ID does not exist."""
    with closing(_open_readonly(database_path)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(reviews)")}
        reviewed_reply_column = (
            "reviewed_reply" if "reviewed_reply" in columns else "NULL"
        )
        row = connection.execute(
            f"""
            SELECT id, reviewed_at, order_id, decision, customer_message,
                   order_status, proposed_reply, {reviewed_reply_column}, follow_up_task
            FROM reviews WHERE id = ?
            """,
            (review_id,),
        ).fetchone()
    if row is None:
        return None
    return SavedReview(
        summary=ReviewSummary(
            id=row[0],
            reviewed_at=row[1],
            order_id=row[2],
            decision=ReviewDecision(row[3]),
        ),
        customer_message=row[4],
        order_status=row[5],
        proposed_reply=row[6],
        reviewed_reply=row[7],
        follow_up_task=row[8],
    )


def save_review(
    database_path: Path,
    request: OverdueOrderInput,
    draft: OverdueOrderOutput,
    reviewed_reply: OverdueOrderOutput,
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
                reviewed_reply TEXT,
                follow_up_task TEXT NOT NULL,
                decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected'))
            )
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(reviews)")}
        if "reviewed_reply" not in columns:
            connection.execute("ALTER TABLE reviews ADD COLUMN reviewed_reply TEXT")
        cursor = connection.execute(
            """
            INSERT INTO reviews
                (customer_message, order_id, order_status, proposed_reply,
                 reviewed_reply, follow_up_task, decision)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.customer_message,
                request.order.order_id,
                request.order.status.value,
                draft.proposed_reply,
                reviewed_reply.proposed_reply,
                draft.follow_up_task,
                decision.value,
            ),
        )
        review_id = cursor.lastrowid
        if review_id is None:
            raise RuntimeError("SQLite did not return a review ID")
        return review_id
