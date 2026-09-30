from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.mode import ModeResponse, ModeUpdate

router = APIRouter(prefix="/mode", tags=["mode"])

@router.get("", response_model=ModeResponse)
def get_mode(scenario: Scenario = Depends(get_scenario)):
    return {"mode": scenario.get_mode()}

@router.put("", response_model=ModeResponse)
def update_mode(
    data: ModeUpdate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        updated_mode = scenario.set_mode(data.mode)
        return {"mode": updated_mode}
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error