export interface TreeComparisonSide {
    size: number;
    height: number;
    leaves: number;
    total_comparisons: number;
    max_single_search: number;
    avg_comparisons: number;
}

export interface TreeComparisonResponse {
    avl: TreeComparisonSide;
    bst: TreeComparisonSide;
    n_searches: number;
}