import axios from "axios";
import { EventApiResponse } from "../models/Event/EventApiResponse";
import { EventCreateRequest } from "../models/Event/EventCreateRequest";
import { EventTreesResponse } from "../models/Event/EventTreesResponse";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/events`;

class EventService {
    async getTrees(): Promise<EventTreesResponse> {
        const response = await axios.get<EventTreesResponse>(`${API_URL}/trees`);
        return response.data;
    }

    async getEvent(eventId: number | string): Promise<EventApiResponse> {
        const response = await axios.get<EventApiResponse>(`${API_URL}/${eventId}`);
        return response.data;
    }

    async createEvent(event: EventCreateRequest): Promise<EventApiResponse> {
        const response = await axios.post<EventApiResponse>(API_URL, event);
        return response.data;
    }

    async markReviewed(eventId: number): Promise<EventApiResponse> {
        const response = await axios.patch<EventApiResponse>(
            `${API_URL}/${eventId}/status`,
            { attention_status: "reviewed" },
        );
        return response.data;
    }
}

export const eventService = new EventService();