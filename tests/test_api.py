import asyncio

import httpx
import pytest

from business_operations.api import app
from business_operations.models import OverdueOrderInput
from business_operations.workflows import draft_overdue_order_response


def post_draft(payload):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.post("/overdue-order/draft", json=payload)

    return asyncio.run(send())


@pytest.mark.parametrize(
    "status", ["processing", "shipped", "delayed", "delivered", "unknown"]
)
def test_draft_endpoint_reuses_workflow_and_does_not_save_reviews(
    status, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    payload = {
        "customer_message": "Where is my order?",
        "order": {"order_id": "ORD-123", "status": status},
    }

    response = post_draft(payload)

    expected = draft_overdue_order_response(OverdueOrderInput.model_validate(payload))
    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    assert not (tmp_path / "business_operations.sqlite3").exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"customer_message": "", "order": {"order_id": "ORD-123", "status": "delayed"}},
        {
            "customer_message": "Where is it?",
            "order": {"order_id": "ORD-123", "status": "late"},
        },
        {"customer_message": "Where is it?", "order": {"order_id": "ORD-123"}},
        {
            "customer_message": "Where is it?",
            "order": {"order_id": "ORD-123", "status": "unknown"},
            "extra": True,
        },
    ],
)
def test_draft_endpoint_rejects_invalid_input(payload, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = post_draft(payload)

    assert response.status_code == 422
    assert not (tmp_path / "business_operations.sqlite3").exists()
