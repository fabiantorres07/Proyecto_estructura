from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.report import ReportCreate, _check_one_decimal


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


class EventCorrection(BaseModel):
    """Corrección manual de un evento activo (PATCH /events/{id}).

    Todos los campos son opcionales: solo se cambia lo que se envía. Mismos
    rangos y formatos que ReportCreate (un decimal, fecha con zona horaria y
    precisión de segundos, normalizada a UTC). El id no se corrige: es
    inmutable. Que la fecha no sea posterior al reloj lo valida Scenario,
    porque depende del estado."""

    magnitude: float | None = Field(default=None, ge=-2.0, le=10.0, allow_inf_nan=False)
    depth: float | None = Field(default=None, ge=0.0, le=700.0, allow_inf_nan=False)
    x: float | None = Field(default=None, ge=0.0, le=1000.0, allow_inf_nan=False)
    y: float | None = Field(default=None, ge=0.0, le=1000.0, allow_inf_nan=False)
    occurred_at: datetime | None = None

    @field_validator("magnitude", "depth", "x", "y", "occurred_at", mode="before")
    @classmethod
    def reject_null_values(cls, value):
        # Mismo criterio que ParameterUpdate: un campo enviado como null es
        # un error; para no cambiarlo basta con no enviarlo.
        if value is None:
            raise ValueError("Correction values cannot be null")
        return value

    @field_validator("magnitude", "depth", "x", "y")
    @classmethod
    def one_decimal(cls, value: float) -> float:
        return _check_one_decimal(value)

    @field_validator("occurred_at")
    @classmethod
    def utc_with_seconds_precision(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        if value.microsecond != 0:
            raise ValueError("occurred_at must have a precision of seconds")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be corrected")
        return self


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


class BranchArchivePreviewResponse(BaseModel):
    eligible: bool
    reason: str | None = None
    root_id: int | None = None
    size: int | None = None
    depth: int | None = None
    event_ids: list[int] = Field(default_factory=list)


class BranchArchiveRotation(BaseModel):
    case: str
    event_id: int
    balance_factor: int
    rotations: list[str]


class BranchArchiveResponse(BaseModel):
    archived: bool
    reason: str | None = None
    root_id: int | None = None
    size: int | None = None
    depth: int | None = None
    event_ids: list[int] = Field(default_factory=list)
    rotations: list[BranchArchiveRotation] = Field(default_factory=list)
    rotation_delta: dict[str, int] = Field(default_factory=dict)