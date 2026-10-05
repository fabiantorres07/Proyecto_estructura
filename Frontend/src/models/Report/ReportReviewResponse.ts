import { EventApiResponse } from "../Event/EventApiResponse";
import { ReportFormValues } from "./ReportFormValues";

export interface ReportReviewResponse {
    report: ReportFormValues;
    current_event_status: "new" | "active" | "archived" | "deleted";
    current_event: EventApiResponse | null;
}