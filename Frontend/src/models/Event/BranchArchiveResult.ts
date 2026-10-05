import { BranchArchiveRotation } from "./BranchArchiveRotation";

export interface BranchArchiveResult {
    archived: boolean;
    reason?: string | null;
    root_id?: number | null;
    size?: number | null;
    depth?: number | null;
    event_ids: number[];
    rotations: BranchArchiveRotation[];
    rotation_delta: Record<string, number>;
}