from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.scenario import Scenario
from app.domain.zone import Zone
from app.api.dependencies import get_scenario
from app.schemas.zone import ZoneCreate, ZoneResponse, ZoneUpdate

router = APIRouter(prefix="/zones", tags=["zones"])


@router.post(
    "",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_zone(
    data: ZoneCreate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        zone = Zone(
            name=data.name,
            x_min=data.x_min,
            x_max=data.x_max,
            y_min=data.y_min,
            y_max=data.y_max,
            is_populated=data.is_populated,
        )
        return scenario.add_zone(zone)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

@router.get("", response_model=list[ZoneResponse])
def list_zones(scenario: Scenario = Depends(get_scenario)):
    return scenario.list_zones()


@router.get("/{zone_name}", response_model=ZoneResponse)
def get_zone(
    zone_name: str,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        return scenario.get_zone(zone_name)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.put("/{zone_name}", response_model=ZoneResponse)
def update_zone(
    zone_name: str,
    data: ZoneUpdate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        changes = data.model_dump(exclude_unset=True)
        return scenario.update_zone(zone_name, changes)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete("/{zone_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(
    zone_name: str,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        scenario.delete_zone(zone_name)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error