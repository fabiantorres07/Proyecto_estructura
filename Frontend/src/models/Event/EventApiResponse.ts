import { AttentionStatus } from "./AttentionStatus";

export interface EventApiResponse {
    event_id: number;
    status?: "active" | "archived";
    magnitude: number;
    depth: number;
    x: number;
    y: number;
    occurred_at: string;
    revision: number;
    stations: string[];
    attention_status: AttentionStatus;
    is_in_populated_zone: boolean;
    priority: number;
}