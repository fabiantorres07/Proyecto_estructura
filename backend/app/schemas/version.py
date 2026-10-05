from pydantic import BaseModel, Field, field_validator


class VersionCreate(BaseModel):
    """Name of the version to save. It goes in the URL when restoring or
    deleting, so slashes are not allowed."""

    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Version name cannot be empty")
        if "/" in value or "\\" in value:
            raise ValueError("Version name cannot contain slashes")
        return value


class VersionSummary(BaseModel):
    name: str
    simulation_clock: str | None
    mode: str | None
    active_events: int
    archived_events: int
    queued_reports: int


class VersionSaved(BaseModel):
    saved: str
    total_versions: int
