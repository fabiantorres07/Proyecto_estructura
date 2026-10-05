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
    """Datos que envía el usuario al preparar un reporte de una estación.

    Aquí se validan los rangos y formatos que NO dependen del estado del
    escenario (política acordada: los rangos van en los schemas). Lo que sí
    depende del estado —que la estación exista y que la fecha no sea
    posterior al reloj de simulación— lo valida Scenario.enqueue_report.

    No se valida aquí si el id está activo, archivado o eliminado: eso se
    decide al PROCESAR el reporte, porque entre encolar y procesar el estado
    del id puede cambiar (por ejemplo, al deshacer una eliminación)."""

    event_id: int = Field(ge=1, le=999999)
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
        """Exige zona horaria, exige precisión de segundos y normaliza a UTC.
        Guardar siempre en UTC hace que la comparación de "iguales datos"
        (sección 6) no dependa del formato con que llegó la fecha."""
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
