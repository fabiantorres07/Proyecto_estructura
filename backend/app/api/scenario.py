from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario

router = APIRouter(prefix="/scenario", tags=["scenario"])


@router.get("/export")
def export_scenario(
    load_mode: Literal["insertions", "topology"] = Query(default="topology"),
    scenario: Scenario = Depends(get_scenario),
):
    try:
        return scenario.export_scenario(load_mode)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error


@router.post("/load")
def load_scenario(data: dict, scenario: Scenario = Depends(get_scenario)):
    try:
        return scenario.load_scenario(data)
    except (KeyError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error