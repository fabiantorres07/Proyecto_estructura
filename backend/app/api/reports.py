from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.report import Report
from app.domain.scenario import Scenario
from app.schemas.report import (
    ReportBatchCreate,
    ReportCreate,
    ReportQueueCleared,
    ReportResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])

# Endpoints de la cola de reportes (sección 8). Solo preparan y muestran
# reportes; procesarlos (POST /reports/process-next, etc.) se agregará
# cuando Scenario tenga la creación y corrección de eventos.
# No hay DELETE /reports/{...}: por decisión del equipo un reporte
# encolado no se puede quitar individualmente, solo vaciar toda la cola.


def _build_report(data: ReportCreate, scenario: Scenario) -> Report:
    """Convierte el schema en el objeto de dominio. La estación se busca en
    el escenario porque Report guarda el objeto Station, no solo su id.
    Lanza KeyError si la estación no existe."""
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
