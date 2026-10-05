export interface UndoResponse {
    undone: string;
    event_id?: number | null;
    parameter?: string | null;
    root_id?: number | null;
}