export interface IndicatorsResponse {
    mode: "Normal" | "Stress";
    L: number;
    active_events: number;
    archived_events: number;
    eliminated_events: number;
    height: number;
    leaves: number;
    traversals: {
        inorder: number[];
        preorder: number[];
        postorder: number[];
        level_order: number[];
    };
    counters: {
        corrections_accepted: number;
        reports_discarded: number;
        conflicts: number;
        mass_archives: number;
        archived_events: number;
    };
    rotations: {
        LL: number;
        RR: number;
        LR: number;
        RL: number;
        simple_left: number;
        simple_right: number;
    };
    events_by_priority: {
        P1: number;
        P2: number;
        P3: number;
    };
    pending_attention: number;
    costly_access: number;
}