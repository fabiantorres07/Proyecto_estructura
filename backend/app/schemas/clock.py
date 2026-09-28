from datetime import datetime

from pydantic import BaseModel, field_validator


class ClockUpdate(BaseModel):
    simulation_clock: datetime

    @field_validator("simulation_clock")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("simulation_clock must include a timezone")
        return value


class ClockResponse(BaseModel):
    simulation_clock: datetime
