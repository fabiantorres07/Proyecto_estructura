import { StructureIssue } from "./StructureIssue";

export interface StructureAudit {
    mode: string;
    checked_nodes: number;
    is_valid: boolean;
    is_avl: boolean;
    error_count: number;
    expected_count: number;
    inconsistent_event_ids: number[];
    issues: StructureIssue[];
}