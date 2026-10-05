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


class EventQueryResponse(BaseModel):
    events: list[EventResponse]
    visited_nodes: int


class AssociatedEventResponse(BaseModel):
    status: Literal["active", "archived"]
    event: EventResponse


class EventAssociationsResponse(BaseModel):
    reference: AssociatedEventResponse | None
    candidates: list[AssociatedEventResponse]
    used_as_reference_by: list[AssociatedEventResponse]


class CostlyAccessEventResponse(BaseModel):
    event: EventResponse
    depth: int
    limit: int
    visited: int


class EventDirectoryRow(BaseModel):
    event_id: int
    status: Literal["active", "archived", "deleted"]
    magnitude: float | None = None
    hypocenter_depth: float | None = None
    priority: int | None = None
    attention_status: Literal["pending", "reviewed"] | None = None
    occurred_at: datetime | None = None
    node_depth: int | None = None
    cost: int | None = None