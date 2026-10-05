import { EventApiResponse } from "./EventApiResponse";

export interface CostlyAccessEventResponse {
    event: EventApiResponse;
    depth: number;
    limit: number;
    visited: number;
}