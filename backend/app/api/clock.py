from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.clock import ClockResponse, ClockUpdate

router = APIRouter(prefix="/clock", tags=["clock"])


@router.get("", response_model=ClockResponse)
def get_clock(scenario: Scenario = Depends(get_scenario)):
    return {"simulation_clock": scenario.simulation_clock}


@router.put("", response_model=ClockResponse)
def update_clock(
    data: ClockUpdate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        updated_clock = scenario.update_simulation_clock(data.simulation_clock)
        return {"simulation_clock": updated_clock}
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
