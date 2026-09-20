export interface ReportFormValues{
    event_id: string;
    revision_num?: number | null;
    station: string;
    magnitude: number;
    depth: number;
    x: number;
    y: number;
    ocurred_at: Date;
}