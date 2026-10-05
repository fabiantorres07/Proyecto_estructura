from typing import NoReturn

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_scenario
from app.domain.event import Event
from app.domain.report import Report
from app.domain.scenario import Scenario
from app.schemas.event import (
    EventCreate,
    EventCorrection,
    BranchArchivePreviewResponse,
    BranchArchiveResponse,
    EventAssociationsResponse,
    EventDirectoryRow,
    EventQueryResponse,
    CostlyAccessEventResponse,
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


def _directory_row(event: Event, status_name: str, node_depth: int | None = None) -> dict:
    return {
        "event_id": event.event_id,
        "status": status_name,
        "magnitude": event.magnitude,
        "hypocenter_depth": event.depth,
        "priority": event.priority,
        "attention_status": event.attention_status.value,
        "occurred_at": event.occurred_at,
        "node_depth": node_depth,
        "cost": node_depth,
    }


def _associated_event(item: dict | None) -> dict | None:
    if item is None:
        return None
    return {"status": item["status"], "event": _event_response(item["event"])}


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
            # Manual creation starts at revision 1 (section 6) unless the
            # form sends a revision explicitly.
            revision_num=data.revision_num if data.revision_num is not None else 1,
            station=station,
            magnitude=data.magnitude,
            depth=data.depth,
            x=data.x,
            y=data.y,
            # No date in the payload -> the current simulation clock.
            occurred_at=(
                data.occurred_at if data.occurred_at is not None else scenario.simulation_clock
            ),
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


@router.get("/directory", response_model=list[EventDirectoryRow])
def list_all_events(scenario: Scenario = Depends(get_scenario)):
    rows = [
        _directory_row(
            node.event,
            "active",
            scenario.avl_tree.depth_of(node),
        )
        for node in scenario.event_index.values()
    ]
    rows.extend(
        _directory_row(event, "archived")
        for event in scenario.archived_history.values()
    )
    rows.extend(
        {"event_id": event_id, "status": "deleted"}
        for event_id in scenario.eliminated_IDs
    )
    return sorted(rows, key=lambda row: row["event_id"])


@router.get("/active", response_model=list[EventResponse])
def list_active_events(scenario: Scenario = Depends(get_scenario)):
    return [_event_response(event) for event in scenario.avl_tree.inorder()]


@router.get("/queries/pending", response_model=EventQueryResponse)
def query_pending_events(
    k: int = Query(gt=0),
    scenario: Scenario = Depends(get_scenario),
):
    try:
        events, visited_nodes = scenario.first_k_pending(k)
        return {
            "events": [_event_response(event) for event in events],
            "visited_nodes": visited_nodes,
        }
    except ValueError as error:
        _raise_http(error)


@router.get("/queries/magnitude", response_model=EventQueryResponse)
def query_magnitude_range(
    min_mag: float = Query(ge=-2, le=10),
    max_mag: float = Query(ge=-2, le=10),
    scenario: Scenario = Depends(get_scenario),
):
    try:
        events, visited_nodes = scenario.events_in_magnitude_range(min_mag, max_mag)
        return {
            "events": [_event_response(event) for event in events],
            "visited_nodes": visited_nodes,
        }
    except ValueError as error:
        _raise_http(error)


@router.get("/queries/depth-date", response_model=EventQueryResponse)
def query_depth_and_date_range(
    max_depth: float = Query(ge=0, le=700),
    min_date: datetime = Query(...),
    max_date: datetime = Query(...),
    scenario: Scenario = Depends(get_scenario),
):
    try:
        events, visited_nodes = scenario.events_by_depth_and_date(
            max_depth,
            min_date,
            max_date,
        )
        return {
            "events": [_event_response(event) for event in events],
            "visited_nodes": visited_nodes,
        }
    except ValueError as error:
        _raise_http(error)


@router.get("/queries/costly-access", response_model=list[CostlyAccessEventResponse])
def query_costly_access(scenario: Scenario = Depends(get_scenario)):
    return [
        {
            **item,
            "event": _event_response(item["event"]),
        }
        for item in scenario.costly_access_events()
    ]


@router.get(
    "/queries/associations/{event_id}",
    response_model=EventAssociationsResponse,
)
def query_event_associations(
    event_id: int,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        associations = scenario.event_associations(event_id)
    except ValueError as error:
        _raise_http(error)
    return {
        "reference": _associated_event(associations["reference"]),
        "candidates": [
            _associated_event(item) for item in associations["candidates"]
        ],
        "used_as_reference_by": [
            _associated_event(item)
            for item in associations["used_as_reference_by"]
        ],
    }


@router.post("/archive/preview", response_model=BranchArchivePreviewResponse)
def preview_branch_archive(scenario: Scenario = Depends(get_scenario)):
    return scenario.preview_branch_archive()


@router.post(
    "/archive/{winner_root_id}",
    response_model=BranchArchiveResponse,
)
def archive_branch(
    winner_root_id: int,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        return scenario.branch_archive(winner_root_id)
    except (KeyError, ValueError) as error:
        _raise_http(error)


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        result = scenario.get_event(event_id)
    except KeyError as error:
        _raise_http(error)

    # Active and archived events keep their data (section 6), so both are
    # returned, with their status. An eliminated id only keeps the id.
    if result["status"] == "eliminated":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} was eliminated",
        )
    return {**_event_response(result["event"]), "status": result["status"]}


@router.patch("/{event_id}", response_model=EventResponse)
def correct_event(
    event_id: int,
    data: EventCorrection,
    scenario: Scenario = Depends(get_scenario),
):
    """Corrección manual de un evento activo (sección 6: "r + 1"). Solo se
    cambian los campos enviados. Se puede deshacer con POST /undo."""
    try:
        event = scenario.correct_event(event_id, data.model_dump(exclude_unset=True))
        return _event_response(event)
    except (KeyError, ValueError) as error:
        _raise_http(error)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        scenario.delete_event(event_id)
    except (KeyError, ValueError) as error:
        _raise_http(error)


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