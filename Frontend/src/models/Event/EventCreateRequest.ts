export interface EventCreateRequest {
    event_id: number;
    station_id: string;
    magnitude: number;
    depth: number;
    x: number;
    y: number;
    occurred_at?: Date;
}