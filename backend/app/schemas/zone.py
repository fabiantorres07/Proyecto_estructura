from pydantic import BaseModel, ConfigDict, Field

class ZoneCreate(BaseModel):
    name: str = Field(min_length=1)
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    is_populated: bool

class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    x_min: float |  None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    is_populated: bool | None = None

class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    is_populated: bool