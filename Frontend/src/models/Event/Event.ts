export interface Event {
    event_id?: string;
    magnitude?: number;
    depth?: number;
    x: number;
    y: number;
    ocurred_at?: Date;
    revision?: number;
    stations?: string[];
    attention_status?: string;
    is_in_populated_zone?: boolean;
    priority?: number;
}