export interface ReportFormValues{
    position: number;
    event_id: string;
    revision_num?: number | null;
    station_id: string;
    magnitude: number;
    depth: number;
    x: number;
    y: number;
    ocurred_at: Date;
}

