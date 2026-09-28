from pydantic import BaseModel, ConfigDict, Field

class StationCreate(BaseModel):
    station_id: str = Field(min_length=1)
    x: float
    y: float


class StationUpdate(BaseModel):
    station_id: str | None = Field(default=None, min_length=1)
    x: float | None = None
    y: float | None = None

class StationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    station_id: str
    x: float
    y: float