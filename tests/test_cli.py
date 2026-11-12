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


def review_input(message, order_id, status, decision, edited_reply=""):
    return f"{message}\n{order_id}\n{status}\n{edited_reply}\n{decision}\n"


@pytest.mark.parametrize(
    ("decision", "result"), [("yes", "approved"), ("no", "rejected")]
)
def test_review_shows_draft_and_saves_decision(decision, result, tmp_path):
    completed = run_review(
        review_input("Where is my order?", "ORD-123", "delayed", decision), tmp_path
    )

    assert completed.returncode == 0
    assert "The order is delayed." in completed.stdout
    assert "Check the cause of the delay" in completed.stdout
    assert f"Reply {result} and saved as review 1." in completed.stdout
    assert "No message was sent and no task was created." in completed.stdout
    assert completed.stderr == ""

    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        row = connection.execute(
            "SELECT reviewed_at, customer_message, order_id, order_status, "
            "proposed_reply, reviewed_reply, follow_up_task, decision FROM reviews"
        ).fetchone()
    assert row is not None
    (
        reviewed_at,
        message,
        order_id,
        status,
        reply,
        reviewed_reply,
        follow_up,
        saved_decision,
    ) = row
    assert reviewed_at.endswith("Z")
    assert (message, order_id, status, saved_decision) == (
        "Where is my order?",
        "ORD-123",
        "delayed",
        result,
    )
    assert reply in completed.stdout
    assert reviewed_reply == reply
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
    completed = run_review(
        review_input("Where is my order?", "ORD-123", "delayed", "maybe"),
        tmp_path,
    )

    assert completed.returncode == 2
    assert "No decision recorded." in completed.stderr
    assert "Reply approved" not in completed.stdout
    assert "Reply rejected" not in completed.stdout
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_review_cancellation_does_not_record_decision(tmp_path):
    completed = run_review("Where is my order?\nORD-123\ndelayed\n", tmp_path)

    assert completed.returncode == 1
    assert "Review cancelled; no decision recorded." in completed.stderr
    assert "Reply approved" not in completed.stdout
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_reviews_persist_across_runs(tmp_path):
    first = run_review(
        review_input("First message", "ORD-123", "delayed", "yes"), tmp_path
    )
    second = run_review(
        review_input("Second message", "ORD-456", "unknown", "no"), tmp_path
    )

    assert first.returncode == second.returncode == 0
    assert "saved as review 2" in second.stdout
    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        rows = connection.execute(
            "SELECT order_id, decision FROM reviews ORDER BY id"
        ).fetchall()
    assert rows == [("ORD-123", "approved"), ("ORD-456", "rejected")]


def test_review_reports_storage_failure(tmp_path):
    (tmp_path / "business_operations.sqlite3").mkdir()

    completed = run_review(
        review_input("Where is my order?", "ORD-123", "delayed", "yes"),
        tmp_path,
    )

    assert completed.returncode == 1
    assert "Could not save review; no decision recorded:" in completed.stderr
    assert "Reply approved" not in completed.stdout


def test_review_persists_owner_edit_separately_from_generated_draft(tmp_path):
    edited_reply = "I checked your order and expect delivery tomorrow."
    completed = run_review(
        review_input(
            "Where is my order?",
            "ORD-123",
            "delayed",
            "yes",
            edited_reply,
        ),
        tmp_path,
    )

    assert completed.returncode == 0
    assert "The order is delayed." in completed.stdout
    assert f"Reply presented for approval:\n{edited_reply}" in completed.stdout
    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        original, reviewed, follow_up = connection.execute(
            "SELECT proposed_reply, reviewed_reply, follow_up_task FROM reviews"
        ).fetchone()
    assert original != edited_reply
    assert reviewed == edited_reply
    assert "Check the cause of the delay" in follow_up

    shown = run_command(tmp_path, "show", "1")
    assert shown.returncode == 0
    assert f"Proposed reply:\n{original}" in shown.stdout
    assert f"Reply presented for approval:\n{edited_reply}" in shown.stdout


def test_review_migrates_existing_database_without_losing_history(tmp_path):
    database_path = tmp_path / "business_operations.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE reviews (
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
        connection.execute(
            "INSERT INTO reviews (customer_message, order_id, order_status, "
            "proposed_reply, follow_up_task, decision) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Old message",
                "OLD-1",
                "shipped",
                "Old reply",
                "Old follow-up",
                "approved",
            ),
        )

    old_review_before_migration = run_command(tmp_path, "show", "1")
    assert old_review_before_migration.returncode == 0
    assert "Proposed reply:\nOld reply" in old_review_before_migration.stdout
    assert "Reply presented for approval:" not in old_review_before_migration.stdout

    completed = run_review(
        review_input("New message", "NEW-2", "delayed", "no", "Revised response"),
        tmp_path,
    )

    assert completed.returncode == 0
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT order_id, proposed_reply, reviewed_reply, decision "
            "FROM reviews ORDER BY id"
        ).fetchall()
    assert rows[0] == ("OLD-1", "Old reply", None, "approved")
    assert rows[1][0] == "NEW-2"
    assert rows[1][1] != "Revised response"
    assert rows[1][2:] == ("Revised response", "rejected")

    old_review = run_command(tmp_path, "show", "1")
    assert old_review.returncode == 0
    assert "Proposed reply:\nOld reply" in old_review.stdout
    assert "Reply presented for approval:" not in old_review.stdout


def test_cancelling_after_edit_does_not_save_review(tmp_path):
    completed = run_review(
        "Where is my order?\nORD-123\ndelayed\nEdited reply\n",
        tmp_path,
    )

    assert completed.returncode == 1
    assert "Review cancelled; no decision recorded." in completed.stderr
    assert not (tmp_path / "business_operations.sqlite3").exists()


def run_command(cwd, *args):
    return subprocess.run(
        [sys.executable, "-m", "business_operations", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_list_and_show_saved_reviews(tmp_path):
    first = run_review(
        review_input("First message", "ORD-123", "delayed", "yes"), tmp_path
    )
    second = run_review(
        review_input("Second message", "ORD-456", "unknown", "no"), tmp_path
    )
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
    assert f"Reply presented for approval:\n{reply}" in shown.stdout
    assert f"Suggested follow-up:\n{follow_up}" in shown.stdout
    assert database_path.read_bytes() == original_database


@pytest.mark.parametrize("args", [("list",), ("show", "1")])
def test_history_does_not_create_missing_database(tmp_path, args):
    completed = run_command(tmp_path, *args)
    assert completed.returncode == 1
    assert "No review database found" in completed.stderr
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_show_missing_review(tmp_path):
    assert (
        run_review(
            review_input("Message", "ORD-123", "delayed", "yes"), tmp_path
        ).returncode
        == 0
    )
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
    assert (
        run_review(
            review_input("Message", "ORD-123", "delayed", "yes"), tmp_path
        ).returncode
        == 0
    )
    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        connection.execute("DELETE FROM reviews")
    empty = run_command(tmp_path, "list")
    assert empty.returncode == 0
    assert "No saved reviews." in empty.stdout

    with sqlite3.connect(tmp_path / "business_operations.sqlite3") as connection:
        connection.executemany(
            "INSERT INTO reviews (customer_message, order_id, order_status, "
            "proposed_reply, follow_up_task, decision) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Message", f"ORD-{i}", "unknown", "Reply", "Follow up", "approved")
                for i in range(55)
            ],
        )
    listed = run_command(tmp_path, "list")
    assert listed.returncode == 0
    lines = listed.stdout.splitlines()
    assert len(lines) == 50
    assert lines[0].startswith("55\t")
    assert lines[-1].startswith("6\t")


def test_list_filters_older_reviews_before_limit(tmp_path):
    assert (
        run_review(
            review_input("Message", "ORD-OLD", "delayed", "yes"), tmp_path
        ).returncode
        == 0
    )
    database_path = tmp_path / "business_operations.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO reviews (customer_message, order_id, order_status, "
            "proposed_reply, follow_up_task, decision) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Message", "ORD-NEW", "unknown", "Reply", "Follow up", "rejected")
                for _ in range(55)
            ],
        )
    original_database = database_path.read_bytes()

    filtered = run_command(
        tmp_path, "list", "--order-id", "ORD-OLD", "--decision", "approved"
    )
    assert filtered.returncode == 0
    assert filtered.stdout.splitlines()[0].startswith("1\t")
    assert filtered.stdout.splitlines()[0].endswith("\tORD-OLD\tapproved")
    assert len(filtered.stdout.splitlines()) == 1
    assert database_path.read_bytes() == original_database


def test_list_filters_order_and_decision_independently(tmp_path):
    for order_id, decision in (
        ("ORD-1", "yes"),
        ("ORD-1", "no"),
        ("ORD-2", "yes"),
    ):
        assert (
            run_review(
                review_input("Message", order_id, "delayed", decision), tmp_path
            ).returncode
            == 0
        )

    by_order = run_command(tmp_path, "list", "--order-id", "ORD-1")
    assert by_order.returncode == 0
    assert [line.split("\t")[0] for line in by_order.stdout.splitlines()] == ["2", "1"]
    approved = run_command(tmp_path, "list", "--decision", "approved")
    assert approved.returncode == 0
    assert [line.split("\t")[0] for line in approved.stdout.splitlines()] == ["3", "1"]
    both = run_command(
        tmp_path, "list", "--order-id", "ORD-1", "--decision", "rejected"
    )
    assert both.returncode == 0
    assert [line.split("\t")[0] for line in both.stdout.splitlines()] == ["2"]
    no_match = run_command(tmp_path, "list", "--order-id", "ord-1")
    assert no_match.returncode == 0
    assert "No saved reviews match the filters." in no_match.stdout


@pytest.mark.parametrize("args", [("--order-id", "  "), ("--decision", "maybe")])
def test_list_rejects_invalid_filters_before_accessing_database(tmp_path, args):
    completed = run_command(tmp_path, "list", *args)
    assert completed.returncode == 2
    assert "error:" in completed.stderr
    assert not (tmp_path / "business_operations.sqlite3").exists()


def test_list_treats_order_id_as_data(tmp_path):
    order_id = "ORD-' OR 1=1 --"
    assert (
        run_review(
            review_input("Message", order_id, "unknown", "yes"), tmp_path
        ).returncode
        == 0
    )
    assert (
        run_review(
            review_input("Message", "OTHER", "unknown", "yes"), tmp_path
        ).returncode
        == 0
    )
    result = run_command(tmp_path, "list", "--order-id", order_id)
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1
    assert result.stdout.splitlines()[0].endswith(f"\t{order_id}\tapproved")
