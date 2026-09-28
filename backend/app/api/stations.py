from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.scenario import Scenario
from app.domain.station import Station
from app.api.dependencies import get_scenario
from app.schemas.station import StationCreate, StationResponse, StationUpdate

router = APIRouter(prefix="/stations", tags=["stations"])


@router.post(
    "",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_station(
    data: StationCreate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        station = Station(
            station_id=data.station_id,
            x=data.x,
            y=data.y,
        )
        return scenario.add_station(station)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

@router.get("", response_model=list[StationResponse])
def list_stations(scenario: Scenario = Depends(get_scenario)):
    return scenario.list_stations()


@router.get("/{station_id}", response_model=StationResponse)
def get_station(
    station_id: str,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        return scenario.get_station(station_id)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.put("/{station_id}", response_model=StationResponse)
def update_station(
    station_id: str,
    data: StationUpdate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        changes = data.model_dump(exclude_unset=True)
        return scenario.update_station(station_id, changes)
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


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(
    station_id: str,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        scenario.delete_station(station_id)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error