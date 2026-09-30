from pydantic import BaseModel, field_validator
from app.domain.mode import Mode

class ModeUpdate(BaseModel):
    mode: Mode

class ModeResponse(BaseModel):
    mode: Mode