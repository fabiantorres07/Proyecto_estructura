from pydantic import BaseModel


class UndoResponse(BaseModel):
    undone: str
    event_id: int | None = None
    parameter: str | None = None
    root_id: int | None = None