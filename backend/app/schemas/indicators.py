from pydantic import BaseModel

from app.domain.mode import Mode
from app.schemas.tree import TreeTraversals


class IndicatorCounters(BaseModel):
    """Contadores de la sección 14 (Scenario.metrics, COUNTER_KEYS)."""

    corrections_accepted: int
    reports_discarded: int
    conflicts: int
    mass_archives: int
    archived_events: int


class RotationMetrics(BaseModel):
    """Casos atendidos y giros elementales (un caso doble = 1 caso LR o RL
    y 2 giros)."""

    LL: int
    RR: int
    LR: int
    RL: int
    simple_left: int
    simple_right: int


class EventsByPriority(BaseModel):
    P1: int
    P2: int
    P3: int


class IndicatorsResponse(BaseModel):
    """Respuesta de GET /indicators (Scenario.get_indicators)."""

    mode: Mode
    L: int
    active_events: int
    archived_events: int
    eliminated_events: int
    height: int
    leaves: int
    traversals: TreeTraversals
    counters: IndicatorCounters
    rotations: RotationMetrics
    events_by_priority: EventsByPriority
    pending_attention: int
    costly_access: int
