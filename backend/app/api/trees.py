from fastapi import APIRouter, Depends

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.tree import AvlStateResponse, BstStateResponse, TreeComparisonResponse

router = APIRouter(prefix="/trees", tags=["trees"])

# Read-only views of the trees (sections 11 and 15). None of them
# modifies the scenario or stacks actions. GET /events/trees (nested tree)
# remains the same because the frontend already uses it.


@router.get("/avl", response_model=AvlStateResponse)
def get_avl_state(scenario: Scenario = Depends(get_scenario)):
    """AVL in flat topology: nodes with links by id, depth, height,
    factor, search cost and costly access; traversals and metrics."""
    return scenario.get_avl_state()


@router.get("/bst", response_model=BstStateResponse)
def get_bst_state(scenario: Scenario = Depends(get_scenario)):
    """Comparison BST with the same response shape as the AVL."""
    return scenario.get_bst_state()


@router.get("/compare", response_model=TreeComparisonResponse)
def compare_trees(scenario: Scenario = Depends(get_scenario)):
    """AVL vs BST comparison (section 11): height, leaves and comparisons when
    searching for the same keys in both trees."""
    return scenario.compare_avl_bst()
