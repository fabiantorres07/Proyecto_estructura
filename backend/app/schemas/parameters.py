from pydantic import BaseModel, Field, field_validator


class ParameterUpdate(BaseModel):
    L: int | None = Field(default=None, strict=True, ge=0)
    W: float | None = Field(default=None, gt=0)
    R: float | None = Field(default=None, gt=0)
    T: float | None = Field(default=None, gt=0)

    @field_validator("L", "W", "R", "T", mode="before")
    @classmethod
    def reject_null_values(cls, value):
        if value is None:
            raise ValueError("Parameter values cannot be null")
        return value


class ParameterResponse(BaseModel):
    L: int
    W: float
    R: float
    T: float