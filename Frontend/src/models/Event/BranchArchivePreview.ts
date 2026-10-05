export interface BranchArchivePreview {
    eligible: boolean;
    reason?: string | null;
    root_id?: number | null;
    size?: number | null;
    depth?: number | null;
    event_ids: number[];
}