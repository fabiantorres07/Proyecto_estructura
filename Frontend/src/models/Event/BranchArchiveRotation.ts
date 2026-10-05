export interface BranchArchiveRotation {
    case: string;
    event_id: number;
    balance_factor: number;
    rotations: string[];
}