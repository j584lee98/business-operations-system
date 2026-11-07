"""Input and output models for the overdue-order workflow."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OrderStatus(str, Enum):
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    UNKNOWN = "unknown"


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: NonEmptyText
    status: OrderStatus


class OverdueOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_message: NonEmptyText
    order: Order


class OverdueOrderOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_reply: NonEmptyText
    follow_up_task: NonEmptyText
