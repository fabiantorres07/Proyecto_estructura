import { StructureAudit } from "./StructureAudit";

export interface BalanceRecovery {
    previous_mode: string;
    mode: string;
    cases: number;
    elementary_rotations: number;
    rotations: {
        case: string;
        event_id: number;
        balance_factor: number;
        rotations: string[];
    }[];
    rotation_delta: Record<string, number>;
    audit: StructureAudit;
    recorded: boolean;
}