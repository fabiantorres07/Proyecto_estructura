import { AttentionStatus } from "./AttentionStatus";

export interface EventTreeNode {
    event_id: number;
    priority: number;
    magnitude: number;
    attention_status: AttentionStatus;
    children: EventTreeNode[];
}