from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.event import Event
from app.domain.report import Report
from app.domain.scenario import Scenario
from app.schemas.event import (
    EventCreate,
    EventResponse,
    EventStatusUpdate,
    EventTreesResponse,
)

router = APIRouter(prefix="/events", tags=["events"])


def _event_response(event: Event) -> dict:
    return {
        "event_id": event.event_id,
        "magnitude": event.magnitude,
        "depth": event.depth,
        "x": event.x,
        "y": event.y,
        "occurred_at": event.occurred_at,
        "revision": event.revision,
        "stations": sorted(station.station_id for station in event.stations),
        "attention_status": event.attention_status.value,
        "is_in_populated_zone": event.is_in_populated_zone,
        "priority": event.priority,
    }


def _tree_node(node) -> dict | None:
    if node is None:
        return None
    return {
        "event_id": node.event.event_id,
        "priority": node.event.priority,
        "magnitude": node.event.magnitude,
        "attention_status": node.event.attention_status.value,
        "children": [
            child
            for child in (
                _tree_node(node.left_son),
                _tree_node(node.right_son),
            )
            if child is not None
        ],
    }


def _raise_http(error: Exception) -> NoReturn:
    """Translate domain errors to the API's standard HTTP responses."""
    if isinstance(error, KeyError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error.args[0]) if error.args else str(error),
        ) from error
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(error),
    ) from error


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    data: EventCreate,
    scenario: Scenario = Depends(get_scenario),
):
    """Create an event directly from a report-shaped form, without enqueueing."""
    try:
        station = scenario.get_station(data.station_id)
        report = Report(
            event_id=data.event_id,
            revision_num=scenario.next_report_revision(data.event_id),
            station=station,
            magnitude=data.magnitude,
            depth=data.depth,
            x=data.x,
            y=data.y,
            occurred_at=data.occurred_at,
        )
        scenario._validate_report(report)
        event = scenario.create_event(
            event_id=report.event_id,
            magnitude=report.magnitude,
            depth=report.depth,
            x=report.x,
            y=report.y,
            occurred_at=report.occurred_at,
            stations={station},
            revision=report.revision_num,
        )
        return _event_response(event)
    except (KeyError, ValueError) as error:
        _raise_http(error)


@router.get("/trees", response_model=EventTreesResponse)
def get_event_trees(
    scenario: Scenario = Depends(get_scenario),
):
    return {
        "avl": _tree_node(scenario.avl_tree.root),
        "bst": _tree_node(scenario.bst_tree.root),
    }


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        result = scenario.get_event(event_id)
    except KeyError as error:
        _raise_http(error)

    if result["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} is not active",
        )
    return _event_response(result["event"])


@router.patch("/{event_id}/status", response_model=EventResponse)
def update_event_status(
    event_id: int,
    data: EventStatusUpdate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        if data.attention_status != "reviewed":
            raise ValueError("Only reviewed status is supported")
        event = scenario.mark_reviewed(event_id)
        return _event_response(event)
    except (KeyError, ValueError) as error:
        _raise_http(error)