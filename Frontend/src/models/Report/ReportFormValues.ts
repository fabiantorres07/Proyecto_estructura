export interface ReportFormValues{
    position: number;
    event_id: number;
    revision_num?: number | null;
    station_id: string;
    magnitude: number;
    depth: number;
    x: number;
    y: number;
    ocurred_at?: Date;
}

