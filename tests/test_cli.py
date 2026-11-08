import sqlite3
import subprocess
import sys

import pytest


def run_review(input_text, cwd):
    return subprocess.run(
        [sys.executable, "-m", "business_operations"],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


@pytest.mark.parametrize(("decision", "result"), [("yes", "approved"), ("no", "rejected")])
def test_review_shows_draft_and_saves_decision(decision, result, tmp_path):
    completed = run_review(f"Where is my order?\nORD-123\ndelayed\n{decision}\n", tmp_path)

    assert completed.returncode == 0
    assert "The order is delayed." in completed.stdout
    assert "Check the cause of the delay" in completed.stdout
    assert f"Draft {result} and saved as review 1." in completed.stdout
    assert "No message was sent and no task was created." in completed.stdout
    assert completed.stderr == ""

    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        row = connection.execute(
            "SELECT reviewed_at, customer_message, order_id, order_status, "
            "proposed_reply, follow_up_task, decision FROM reviews"
        ).fetchone()
    assert row is not None
    reviewed_at, message, order_id, status, reply, follow_up, saved_decision = row
    assert reviewed_at.endswith("Z")
    assert (message, order_id, status, saved_decision) == (
        "Where is my order?", "ORD-123", "delayed", result
    )
    assert reply in completed.stdout
    assert follow_up in completed.stdout


@pytest.mark.parametrize(
    "input_text",
    [
        "Where is my order?\nORD-123\nlate\n",
        "Where is my order?\n\nunknown\n",
    ],
)
def test_review_rejects_invalid_order_input(input_text, tmp_path):
    completed = run_review(input_text, tmp_path)

    assert completed.returncode == 2
    assert "Invalid workflow input:" in completed.stderr
    assert "Proposed reply:" not in completed.stdout
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_review_rejects_invalid_decision(tmp_path):
    completed = run_review("Where is my order?\nORD-123\ndelayed\nmaybe\n", tmp_path)

    assert completed.returncode == 2
    assert "No decision recorded." in completed.stderr
    assert "Draft approved" not in completed.stdout
    assert "Draft rejected" not in completed.stdout
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_review_cancellation_does_not_record_decision(tmp_path):
    completed = run_review("Where is my order?\nORD-123\ndelayed\n", tmp_path)

    assert completed.returncode == 1
    assert "Review cancelled; no decision recorded." in completed.stderr
    assert "Draft approved" not in completed.stdout
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_reviews_persist_across_runs(tmp_path):
    first = run_review("First message\nORD-123\ndelayed\nyes\n", tmp_path)
    second = run_review("Second message\nORD-456\nunknown\nno\n", tmp_path)

    assert first.returncode == second.returncode == 0
    assert "saved as review 2" in second.stdout
    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        rows = connection.execute(
            "SELECT order_id, decision FROM reviews ORDER BY id"
        ).fetchall()
    assert rows == [("ORD-123", "approved"), ("ORD-456", "rejected")]


def test_review_reports_storage_failure(tmp_path):
    (tmp_path / "business_operations.sqlite3").mkdir()

    completed = run_review("Where is my order?\nORD-123\ndelayed\nyes\n", tmp_path)

    assert completed.returncode == 1
    assert "Could not save review; no decision recorded:" in completed.stderr
    assert "Draft approved" not in completed.stdout
