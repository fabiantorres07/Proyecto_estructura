export interface ScenarioLoadSummary {
    load_mode: "insertions" | "topology";
    mode: string;
    active_events: number;
    archived_events: number;
    eliminated_ids: number;
    queued_reports: number;
    warnings: string[];
    inherited: string[];
    avl: {
        root_id: number | null;
        height: number;
        max_depth: number | null;
        leaves: number;
    };
    bst: {
        root_id: number | null;
        height: number;
        max_depth: number | null;
        leaves: number;
    };
}