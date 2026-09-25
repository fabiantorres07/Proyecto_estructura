import axios from "axios";
import { Zone } from "../models/Zone";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/zones`;

class ZoneService {
    async getZones(): Promise<Zone[]> {
        try {
            const response = await axios.get<Zone[]>(API_URL);
            return response.data;
        } catch (error) {
            console.error("Error al obtener zonas:", error);
            return [];
        }
    }

    async getZoneByName(name: string): Promise<Zone | null> {
        try {
            const response = await axios.get<Zone>(`${API_URL}/${name}`);
            return response.data;
        } catch (error) {
            console.error("Zona no encontrada:", error);
            return null;
        }
    }

    async createZone(Zone: Zone): Promise<Zone | null> {
        try {
            const response = await axios.post<Zone>(API_URL, Zone);
            return response.data;
        } catch (error) {
            console.error("Error al crear zona:", error);
            return null;
        }
    }

    async updateZone(original_name: string, zone: Partial<Zone>): Promise<Zone | null> {
        try {
            const response = await axios.put<Zone>(`${API_URL}/${original_name}`, zone);
            return response.data;
        } catch (error) {
            console.error("Error al actualizar zona:", error);
            return null;
        }
    }

    async deleteZone(zone_name: string): Promise<boolean> {
        try {
            await axios.delete(`${API_URL}/${zone_name}`);
            return true;
        } catch (error) {
            console.error("Error al eliminar zona:", error);
            return false;
        }
    }
}

export const zoneService = new ZoneService();
