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


def run_command(cwd, *args):
    return subprocess.run(
        [sys.executable, "-m", "business_operations", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_list_and_show_saved_reviews(tmp_path):
    first = run_review("First message\nORD-123\ndelayed\nyes\n", tmp_path)
    second = run_review("Second message\nORD-456\nunknown\nno\n", tmp_path)
    assert first.returncode == second.returncode == 0
    database_path = tmp_path / "business_operations.sqlite3"
    original_database = database_path.read_bytes()
    with sqlite3.connect(database_path) as connection:
        reviewed_at, reply, follow_up = connection.execute(
            "SELECT reviewed_at, proposed_reply, follow_up_task FROM reviews WHERE id = 1"
        ).fetchone()

    listed = run_command(tmp_path, "list")
    assert listed.returncode == 0
    lines = listed.stdout.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("2\t") and lines[0].endswith("\tORD-456\trejected")
    assert lines[1].startswith("1\t") and lines[1].endswith("\tORD-123\tapproved")

    shown = run_command(tmp_path, "show", "1")
    assert shown.returncode == 0
    assert "Review: 1" in shown.stdout
    assert "Decision: approved" in shown.stdout
    assert "Order ID: ORD-123" in shown.stdout
    assert "Order status: delayed" in shown.stdout
    assert "Customer message:\nFirst message" in shown.stdout
    assert f"Reviewed at (UTC): {reviewed_at}" in shown.stdout
    assert f"Proposed reply:\n{reply}" in shown.stdout
    assert f"Suggested follow-up:\n{follow_up}" in shown.stdout
    assert database_path.read_bytes() == original_database


@pytest.mark.parametrize("args", [("list",), ("show", "1")])
def test_history_does_not_create_missing_database(tmp_path, args):
    completed = run_command(tmp_path, *args)
    assert completed.returncode == 1
    assert "No review database found" in completed.stderr
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_show_missing_review(tmp_path):
    assert run_review("Message\nORD-123\ndelayed\nyes\n", tmp_path).returncode == 0
    completed = run_command(tmp_path, "show", "99")
    assert completed.returncode == 1
    assert "Review 99 not found." in completed.stderr


@pytest.mark.parametrize("review_id", ["0", "-1", "abc"])
def test_show_rejects_invalid_id(tmp_path, review_id):
    completed = run_command(tmp_path, "show", review_id)
    assert completed.returncode == 2
    assert "review_id" in completed.stderr
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_history_reports_invalid_database(tmp_path):
    (tmp_path / "business_operations.sqlite3").write_text("not a database")
    completed = run_command(tmp_path, "list")
    assert completed.returncode == 1
    assert "Could not read reviews:" in completed.stderr


def test_list_empty_database_and_limits_results(tmp_path):
    assert run_review("Message\nORD-123\ndelayed\nyes\n", tmp_path).returncode == 0
    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        connection.execute("DELETE FROM reviews")
    empty = run_command(tmp_path, "list")
    assert empty.returncode == 0
    assert "No saved reviews." in empty.stdout

    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        connection.executemany(
            "INSERT INTO reviews (customer_message, order_id, order_status, "
            "proposed_reply, follow_up_task, decision) VALUES (?, ?, ?, ?, ?, ?)",
            [("Message", f"ORD-{i}", "unknown", "Reply", "Follow up", "approved") for i in range(55)],
        )
    listed = run_command(tmp_path, "list")
    assert listed.returncode == 0
    lines = listed.stdout.splitlines()
    assert len(lines) == 50
    assert lines[0].startswith("55\t")
    assert lines[-1].startswith("6\t")
