import { EventApiResponse } from "./EventApiResponse";

export interface EventAssociationItem {
    status: "active" | "archived";
    event: EventApiResponse;
}