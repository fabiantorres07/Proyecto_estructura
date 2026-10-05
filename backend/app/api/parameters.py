from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.parameters import ParameterResponse, ParameterUpdate

router = APIRouter(prefix="/parameters", tags=["parameters"])


@router.get("", response_model=ParameterResponse)
def get_parameters(scenario: Scenario = Depends(get_scenario)):
    return {name: getattr(scenario, name) for name in ("L", "W", "R", "T")}


@router.patch("", response_model=ParameterResponse)
def update_parameters(
    data: ParameterUpdate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        scenario.change_parameters(data.model_dump(exclude_unset=True))
        return {name: getattr(scenario, name) for name in ("L", "W", "R", "T")}
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error