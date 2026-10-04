from pydantic import BaseModel, field_validator
from app.domain.mode import Mode

class ModeUpdate(BaseModel):
    mode: Mode

class ModeResponse(BaseModel):
    mode: Mode


class StructureIssueResponse(BaseModel):
    event_id: int | None
    type: str
    severity: str
    detail: str


class StructureAuditResponse(BaseModel):
    mode: Mode
    checked_nodes: int
    is_valid: bool
    is_avl: bool
    error_count: int
    expected_count: int
    inconsistent_event_ids: list[int]
    issues: list[StructureIssueResponse]


class RecoveryRotationResponse(BaseModel):
    case: str
    event_id: int
    balance_factor: int
    rotations: list[str]


class BalanceRecoveryResponse(BaseModel):
    previous_mode: Mode
    mode: Mode
    cases: int
    elementary_rotations: int
    rotations: list[RecoveryRotationResponse]
    rotation_delta: dict[str, int]
    audit: StructureAuditResponse
    recorded: bool