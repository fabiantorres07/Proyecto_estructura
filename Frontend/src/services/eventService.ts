import axios from "axios";
import { EventApiResponse } from "../models/Event/EventApiResponse";
import { EventCreateRequest } from "../models/Event/EventCreateRequest";
import { EventAssociationsResponse } from "../models/Event/EventAssociationsResponse";
import { EventDirectoryRow } from "../models/Event/EventDirectoryRow";
import { EventQueryResponse } from "../models/Event/EventQueryResponse";
import { CostlyAccessEventResponse } from "../models/Event/CostlyAccessEventResponse";
import { EventTreesResponse } from "../models/Event/EventTreesResponse";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/events`;

class EventService {
    async getTrees(): Promise<EventTreesResponse> {
        const response = await axios.get<EventTreesResponse>(`${API_URL}/trees`);
        return response.data;
    }

    async getActiveEvents(): Promise<EventApiResponse[]> {
        const response = await axios.get<EventApiResponse[]>(`${API_URL}/active`);
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

    async getDirectory(): Promise<EventDirectoryRow[]> {
        const response = await axios.get<EventDirectoryRow[]>(`${API_URL}/directory`);
        return response.data;
    }

    async getPending(k: number): Promise<EventQueryResponse> {
        const response = await axios.get<EventQueryResponse>(`${API_URL}/queries/pending`, { params: { k } });
        return response.data;
    }

    async getMagnitudeRange(min_mag: number, max_mag: number): Promise<EventQueryResponse> {
        const response = await axios.get<EventQueryResponse>(`${API_URL}/queries/magnitude`, { params: { min_mag, max_mag } });
        return response.data;
    }

    async getDepthDateRange(max_depth: number, min_date: string, max_date: string): Promise<EventQueryResponse> {
        const response = await axios.get<EventQueryResponse>(`${API_URL}/queries/depth-date`, {
            params: { max_depth, min_date, max_date },
        });
        return response.data;
    }

    async getAssociations(eventId: number): Promise<EventAssociationsResponse> {
        const response = await axios.get<EventAssociationsResponse>(`${API_URL}/queries/associations/${eventId}`);
        return response.data;
    }

    async getCostlyAccess(): Promise<CostlyAccessEventResponse[]> {
        const response = await axios.get<CostlyAccessEventResponse[]>(`${API_URL}/queries/costly-access`);
        return response.data;
    }
}

export const eventService = new EventService();