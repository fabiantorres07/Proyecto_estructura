from typing import Literal
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def _check_one_decimal(value: float) -> float:
    """Rechaza cantidades con más de un decimal (sección 3 del enunciado).
    Se compara contra el valor redondeado a una cifra con una tolerancia
    mínima, para no rechazar por errores de representación de float."""
    if abs(value * 10 - round(value * 10)) > 1e-9:
        raise ValueError("must have at most one decimal place")
    return round(value, 1)


class ReportCreate(BaseModel):
    """Data sent by the user when preparing a report from a station.

    Range and format validations that DO NOT depend on the scenario state
    happen here (agreed policy: ranges go in the schemas). What DOES
    depend on the state —that the station exists and that the date is not
    later than the simulation clock— is validated by
    Scenario.enqueue_report.

    The check of whether the id is active, archived, or eliminated is NOT
    done here: it is decided when PROCESSING the report, because between
    enqueue and process the state of the id can change (for example, when
    undoing a deletion).

    The `revision_num` is the revision CLAIMED BY THE EMITTING STATION,
    not a value the backend computes. That is what makes confirmation,
    conflict, and old reports possible (section 6 table):
      - revision > current                     -> correction
      - revision == current, same data         -> confirmation
      - revision == current, different data    -> conflict
      - revision < current                     -> old
    If the backend always computed "current + 1", every report would land
    as a correction and the other cases would never trigger.
    """

    event_id: int = Field(ge=1, le=999999)
    revision_num: int = Field(ge=1)
    station_id: str = Field(min_length=1)
    magnitude: float = Field(ge=-2.0, le=10.0, allow_inf_nan=False)
    depth: float = Field(ge=0.0, le=700.0, allow_inf_nan=False)
    x: float = Field(ge=0.0, le=1000.0, allow_inf_nan=False)
    y: float = Field(ge=0.0, le=1000.0, allow_inf_nan=False)
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0)
    )

    @field_validator("magnitude", "depth", "x", "y")
    @classmethod
    def one_decimal(cls, value: float) -> float:
        return _check_one_decimal(value)

    @field_validator("occurred_at")
    @classmethod
    def utc_with_seconds_precision(cls, value: datetime) -> datetime:
        """Requires timezone, requires second precision, normalizes to UTC.
        Storing always in UTC makes the "same data" comparison (section 6)
        independent of the input format."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        if value.microsecond != 0:
            raise ValueError("occurred_at must have a precision of seconds")
        return value.astimezone(timezone.utc)

class ReportBatchCreate(BaseModel):
    """Ráfaga de reportes de N estaciones (N >= 1, sección 8). Se encolan
    todos en el orden recibido, o ninguno si alguno es inválido."""

    reports: list[ReportCreate] = Field(min_length=1)


class ReportResponse(BaseModel):
    """Un reporte en la cola. `position` es su lugar en el orden de
    recepción: 1 = el próximo que se procesará."""

    position: int
    event_id: int
    revision_num: int
    station_id: str
    magnitude: float
    depth: float
    x: float
    y: float
    occurred_at: datetime


class ReportQueueCleared(BaseModel):
    """Respuesta al vaciar la cola: cuántos reportes se descartaron."""

    removed: int
    
    
class ReportReviewEvent(BaseModel):
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
    
    
class ReportReviewResponse(BaseModel):
    report: ReportResponse
    current_event_status: Literal["new", "active", "archived", "deleted"]
    current_event: ReportReviewEvent | None
    
    
class ReportProcessedResponse(BaseModel):
    case: str
    event_id: int
    revision_num: int
