export interface ReportProcessedResponse {
    case: string;
    event_id: number;
    revision_num: number;
    station_id: string;
    rotations: {
        case: string;
        event_id: number;
        balance_factor: number;
        rotations: string[];
    }[];
    rotation_delta: Record<string, number>;
}