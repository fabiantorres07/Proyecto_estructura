from pydantic import BaseModel, field_validator
from app.domain.mode import Mode

class modeUpdate(BaseModel):
    mode: Mode

class modedeResponse(BaseModel):
    mode: Mode