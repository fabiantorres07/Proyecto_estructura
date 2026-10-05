from typing import Literal

from pydantic import BaseModel

from app.domain.mode import Mode


class TreeTraversals(BaseModel):
    """Recorridos del árbol como listas de ids de evento."""

    inorder: list[int]
    preorder: list[int]
    postorder: list[int]
    level_order: list[int]


class TreeNodeState(BaseModel):
    """Un nodo en topología PLANA: nombra a sus vecinos por id.
    costly_access solo viene en el AVL."""

    event_id: int
    label: str
    key: list[int | float]
    priority: int
    magnitude: float
    attention_status: Literal["pending", "reviewed"]
    parent_id: int | None
    left_id: int | None
    right_id: int | None
    depth: int
    height: int
    balance_factor: int
    search_cost: int
    costly_access: bool | None = None


class AvlStateResponse(BaseModel):
    """GET /trees/avl (Scenario.get_avl_state)."""

    tree: Literal["AVL"]
    mode: Mode
    size: int
    root_id: int | None
    height: int
    leaves: int
    is_avl: bool
    unbalanced_ids: list[int]
    L: int
    nodes: list[TreeNodeState]
    traversals: TreeTraversals
    rotation_metrics: dict[str, int]
    counters: dict[str, int]


class BstStateResponse(BaseModel):
    """GET /trees/bst (Scenario.get_bst_state)."""

    tree: Literal["BST"]
    size: int
    root_id: int | None
    height: int
    leaves: int
    nodes: list[TreeNodeState]
    traversals: TreeTraversals


class TreeComparisonSide(BaseModel):
    size: int
    height: int
    leaves: int
    total_comparisons: int
    max_single_search: int
    avg_comparisons: float


class TreeComparisonResponse(BaseModel):
    """GET /trees/compare (Scenario.compare_avl_bst, sección 11)."""

    avl: TreeComparisonSide
    bst: TreeComparisonSide
    n_searches: int
