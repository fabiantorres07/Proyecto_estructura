export interface VersionSummary {
    name: string;
    simulation_clock: string | null;
    mode: string | null;
    active_events: number;
    archived_events: number;
    queued_reports: number;
}

export interface VersionSaved {
    saved: string;
    total_versions: number;
}