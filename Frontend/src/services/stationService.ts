import axios from "axios";
import { Station } from "../models/Station";
import { notifyScenarioStateChanged } from "./undoService";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/stations`;

class StationService {
    async getStations(): Promise<Station[]> {
        try {
            const response = await axios.get<Station[]>(API_URL);
            return response.data;
        } catch (error) {
            console.error("Error al obtener estaciones:", error);
            throw error;
        }
    }

    async getStation(id: string): Promise<Station | null> {
        try {
            const response = await axios.get<Station>(`${API_URL}/${id}`);
            return response.data;
        } catch (error) {
            console.error("Estación no encontrada:", error);
            throw error;
        }
    }

    async createStation(station: Station): Promise<Station | null> {
        try {
            const response = await axios.post<Station>(API_URL, station);
            notifyScenarioStateChanged();
            return response.data;
        } catch (error) {
            console.error("Error al crear estación:", error);
            throw error;
        }
    }

    async updateStation(original_id: string, station: Partial<Station>): Promise<Station | null> {
        try {
            const response = await axios.put<Station>(`${API_URL}/${original_id}`, station);
            notifyScenarioStateChanged();
            return response.data;
        } catch (error) {
            console.error("Error al actualizar estación:", error);
            throw error;
        }
    }

    async deleteStation(station_id: string): Promise<boolean> {
        try {
            await axios.delete(`${API_URL}/${station_id}`);
            notifyScenarioStateChanged();
            return true;
        } catch (error) {
            console.error("Error al eliminar estación:", error);
            throw error;
        }
    }
}

export const stationService = new StationService();
