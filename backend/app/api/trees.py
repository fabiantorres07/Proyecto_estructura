from fastapi import APIRouter, Depends

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.tree import AvlStateResponse, BstStateResponse, TreeComparisonResponse

router = APIRouter(prefix="/trees", tags=["trees"])

# Vistas de solo lectura de los árboles (secciones 11 y 15). Ninguna
# modifica el escenario ni apila acciones. GET /events/trees (árbol anidado)
# se mantiene igual porque el frontend ya lo usa.


@router.get("/avl", response_model=AvlStateResponse)
def get_avl_state(scenario: Scenario = Depends(get_scenario)):
    """AVL en topología plana: nodos con enlaces por id, profundidad, altura,
    factor, costo de búsqueda y acceso costoso; recorridos y métricas."""
    return scenario.get_avl_state()


@router.get("/bst", response_model=BstStateResponse)
def get_bst_state(scenario: Scenario = Depends(get_scenario)):
    """BST de comparación con la misma forma de respuesta que el AVL."""
    return scenario.get_bst_state()


@router.get("/compare", response_model=TreeComparisonResponse)
def compare_trees(scenario: Scenario = Depends(get_scenario)):
    """Comparación AVL vs BST (sección 11): altura, hojas y comparaciones al
    buscar las mismas claves en ambos árboles."""
    return scenario.compare_avl_bst()
