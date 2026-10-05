from pydantic import BaseModel


class UndoResponse(BaseModel):
    undone: str
    event_id: int | None = None
    parameter: str | None = None
    root_id: int | None = None
    zone_name: str | None = None
    station_id: str | None = None
    removed: int | None = None
    count: int | None = None