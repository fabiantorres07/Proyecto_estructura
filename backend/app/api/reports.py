from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.report import Report
from app.domain.scenario import Scenario
from app.schemas.report import (
    ReportBatchCreate,
    ReportCreate,
    ReportProcessedResponse,
    ReportQueueCleared,
    ReportResponse,
    ReportReviewEvent,
    ReportReviewResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])

# Endpoints de la cola de reportes (sección 8). Solo preparan y muestran
# reportes; procesarlos (POST /reports/process-next, etc.) se agregará
# cuando Scenario tenga la creación y corrección de eventos.
# No hay DELETE /reports/{...}: por decisión del equipo un reporte
# encolado no se puede quitar individualmente, solo vaciar toda la cola.


def _build_report(data: ReportCreate, scenario: Scenario) -> Report:
    """Turn the schema into the domain object.

    The revision comes directly from the payload (it is what the emitting
    station claims), so the backend does NOT recompute it. Recomputing it
    with next_report_revision() would always produce "current + 1" and
    force every report into the correction case, breaking the confirmation,
    conflict, and old cases of the section 6 table.

    The station is looked up in the scenario because Report stores the
    Station object, not just its id. Raises KeyError if it does not exist.
    """
    return Report(
        event_id=data.event_id,
        revision_num=data.revision_num,
        station=scenario.get_station(data.station_id),
        magnitude=data.magnitude,
        depth=data.depth,
        x=data.x,
        y=data.y,
        occurred_at=data.occurred_at,
    )

def _to_response(report: Report, position: int) -> dict:
    """Report -> datos de ReportResponse. Se arma a mano porque el
    schema expone station_id y la posición, que no son atributos directos
    de Report."""
    return {
        "position": position,
        "event_id": report.event_id,
        "revision_num": report.revision_num,
        "station_id": report.station.station_id,
        "magnitude": report.magnitude,
        "depth": report.depth,
        "x": report.x,
        "y": report.y,
        "occurred_at": report.occurred_at,
    }


def _raise_http(error: Exception):
    """Traduce los errores de dominio al mismo criterio de los otros
    routers: KeyError -> 404, ValueError -> 409."""
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
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def enqueue_report(
    data: ReportCreate,
    scenario: Scenario = Depends(get_scenario),
):
    """Prepara un reporte: lo agrega al final de la cola sin procesarlo."""
    try:
        report = _build_report(data, scenario)
        position = scenario.enqueue_report(report)
        return _to_response(report, position)
    except (KeyError, ValueError) as error:
        _raise_http(error)


@router.post(
    "/batch",
    response_model=list[ReportResponse],
    status_code=status.HTTP_201_CREATED,
)
def enqueue_report_batch(
    data: ReportBatchCreate,
    scenario: Scenario = Depends(get_scenario),
):
    """Prepara una ráfaga de reportes de N estaciones. Todo o nada: si uno
    falla, no se encola ninguno."""
    try:
        reports = [_build_report(item, scenario) for item in data.reports]
        first_position = scenario.enqueue_reports(reports)
        return [
            _to_response(report, first_position + offset)
            for offset, report in enumerate(reports)
        ]
    except (KeyError, ValueError) as error:
        _raise_http(error)


@router.get("", response_model=list[ReportResponse])
def list_reports(scenario: Scenario = Depends(get_scenario)):
    """Cola completa en orden de recepción (position 1 = el próximo)."""
    return [
        _to_response(report, position)
        for position, report in enumerate(scenario.list_reports(), start=1)
    ]


@router.delete("", response_model=ReportQueueCleared)
def clear_report_queue(scenario: Scenario = Depends(get_scenario)):
    """Vacía la cola completa y devuelve cuántos reportes se descartaron."""
    return {"removed": scenario.clear_report_queue()}
    
    
def _current_event_for_report(event_id: int, scenario: Scenario):
    if event_id in scenario.event_index:
        event = scenario.event_index[event_id].event
        state = "active"
    elif event_id in scenario.archived_history:
        event = scenario.archived_history[event_id]
        state = "archived"
    elif event_id in scenario.eliminated_IDs:
        return "deleted", None
    else:
        return "new", None
    
    return state, ReportReviewEvent(
        event_id=event.event_id,
        magnitude=event.magnitude,
        depth=event.depth,
        x=event.x,
        y=event.y,
        occurred_at=event.occurred_at,
        revision=event.revision,
        stations=sorted(station.station_id for station in event.stations),
        attention_status=event.attention_status.value,
        is_in_populated_zone=event.is_in_populated_zone,
        priority=event.priority,
    )
    
    
@router.get("/next", response_model=ReportReviewResponse)
def get_next_report(scenario: Scenario = Depends(get_scenario)):
    reports = scenario.list_reports()
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay reportes pendientes en la cola",
        )
    
    report = reports[0]
    current_status, current_event = _current_event_for_report(report.event_id, scenario)
    return {
        "report": _to_response(report, 1),
        "current_event_status": current_status,
        "current_event": current_event,
    }
    
    
@router.put("/next", response_model=ReportResponse)
def update_next_report(
    data: ReportCreate,
    scenario: Scenario = Depends(get_scenario),
):
    try:
        reports = scenario.list_reports()
        if not reports:
            raise ValueError("No hay reportes pendientes en la cola")
        report = _build_report(data, scenario)
        report.revision_num = reports[0].revision_num
        updated_report = scenario.replace_next_report(report)
        return _to_response(updated_report, 1)
    except (KeyError, ValueError) as error:
        _raise_http(error)
    
    
@router.post("/process-next", response_model=ReportProcessedResponse)
def process_next_report(scenario: Scenario = Depends(get_scenario)):
    try:
        result = scenario.process_next_report()
        report = result["report"]
        return {
            "case": result["case"],
            "event_id": result["event_id"],
            "revision_num": report.revision_num,
        }
    except ValueError as error:
        _raise_http(error)
    
    
@router.delete("/next", response_model=ReportResponse)
def discard_next_report(scenario: Scenario = Depends(get_scenario)):
    try:
        report = scenario.discard_next_report()
        return _to_response(report, 1)
    except ValueError as error:
        _raise_http(error)
