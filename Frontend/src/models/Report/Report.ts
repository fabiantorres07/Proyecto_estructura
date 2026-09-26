import { Station } from "../Station";
export interface Report{
    event_id: string;
    revision_num?: number | null;
    station: Station;
    magnitude: number;
    depth: number;
    x: number;
    y: number;
    ocurred_at: Date;
}