import { AttentionStatus } from "./AttentionStatus";

export interface EventDirectoryRow {
    event_id: number;
    status: "active" | "archived" | "deleted";
    magnitude: number | null;
    hypocenter_depth: number | null;
    priority: number | null;
    attention_status: AttentionStatus | null;
    occurred_at: string | null;
    node_depth: number | null;
    cost: number | null;
}