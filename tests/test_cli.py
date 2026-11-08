import subprocess
import sys

import pytest


def run_review(input_text):
    return subprocess.run(
        [sys.executable, "-m", "business_operations"],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(("decision", "result"), [("yes", "approved"), ("no", "rejected")])
def test_review_shows_draft_and_records_decision_for_session(decision, result):
    completed = run_review(f"Where is my order?\nORD-123\ndelayed\n{decision}\n")

    assert completed.returncode == 0
    assert "The order is delayed." in completed.stdout
    assert "Check the cause of the delay" in completed.stdout
    assert f"Draft {result} for this session." in completed.stdout
    assert "No message was sent and no task was created." in completed.stdout
    assert completed.stderr == ""


@pytest.mark.parametrize(
    "input_text",
    [
        "Where is my order?\nORD-123\nlate\n",
        "Where is my order?\n\nunknown\n",
    ],
)
def test_review_rejects_invalid_order_input(input_text):
    completed = run_review(input_text)

    assert completed.returncode == 2
    assert "Invalid workflow input:" in completed.stderr
    assert "Proposed reply:" not in completed.stdout


def test_review_rejects_invalid_decision():
    completed = run_review("Where is my order?\nORD-123\ndelayed\nmaybe\n")

    assert completed.returncode == 2
    assert "No decision recorded." in completed.stderr
    assert "Draft approved" not in completed.stdout
    assert "Draft rejected" not in completed.stdout


def test_review_cancellation_does_not_record_decision():
    completed = run_review("Where is my order?\nORD-123\ndelayed\n")

    assert completed.returncode == 1
    assert "Review cancelled; no decision recorded." in completed.stderr
    assert "Draft approved" not in completed.stdout
