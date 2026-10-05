from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.undo import UndoResponse

router = APIRouter(prefix="/undo", tags=["undo"])


@router.post("", response_model=UndoResponse)
def undo_last_action(scenario: Scenario = Depends(get_scenario)):
    try:
        return scenario.undo()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error