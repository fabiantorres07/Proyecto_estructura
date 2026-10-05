from fastapi import APIRouter, Depends

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.indicators import IndicatorsResponse

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("", response_model=IndicatorsResponse)
def get_indicators(scenario: Scenario = Depends(get_scenario)):
    """Indicadores de la sección 14: cantidades, altura, hojas, recorridos,
    contadores, rotaciones, eventos por prioridad, pendientes y acceso
    costoso. Solo lectura."""
    return scenario.get_indicators()
