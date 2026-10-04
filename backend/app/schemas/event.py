from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.report import ReportCreate


class EventCreate(ReportCreate):
    """Direct event creation uses the same input fields as a report."""


class EventResponse(BaseModel):
    event_id: int
    magnitude: float
    depth: float
    x: float
    y: float
    occurred_at: datetime
    revision: int
    stations: list[str]
    attention_status: Literal["pending", "reviewed"]
    is_in_populated_zone: bool
    priority: int


class EventStatusUpdate(BaseModel):
    attention_status: Literal["reviewed"]


class EventTreeNode(BaseModel):
    event_id: int
    priority: int
    magnitude: float
    attention_status: Literal["pending", "reviewed"]
    children: list["EventTreeNode"] = Field(default_factory=list)


class EventTreesResponse(BaseModel):
    avl: EventTreeNode | None
    bst: EventTreeNode | None