import { EventApiResponse } from "./EventApiResponse";

export interface EventQueryResponse {
    events: EventApiResponse[];
    visited_nodes: number;
}