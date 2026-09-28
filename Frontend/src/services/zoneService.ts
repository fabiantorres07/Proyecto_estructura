import axios from "axios";
import { Zone } from "../models/Zone";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/zones`;

const toApiName = (name: string) => name.replace(/ /g, "_");
const toDisplayName = (name: string) => name.replace(/_/g, " ");
const fromApiZone = (zone: Zone): Zone => ({
    ...zone,
    name: zone.name ? toDisplayName(zone.name) : zone.name,
});
const toApiPath = (name: string) => encodeURIComponent(toApiName(name));

class ZoneService {
    async getZones(): Promise<Zone[]> {
        try {
            const response = await axios.get<Zone[]>(API_URL);
            return response.data.map(fromApiZone);
        } catch (error) {
            console.error("Error al obtener zonas:", error);
            throw error;
        }
    }

    async getZoneByName(name: string): Promise<Zone | null> {
        try {
            const response = await axios.get<Zone>(`${API_URL}/${toApiPath(name)}`);
            return fromApiZone(response.data);
        } catch (error) {
            console.error("Zona no encontrada:", error);
            throw error;
        }
    }

    async createZone(zone: Zone): Promise<Zone | null> {
        try {
            const response = await axios.post<Zone>(API_URL, {
                ...zone,
                name: zone.name ? toApiName(zone.name) : zone.name,
            });
            return fromApiZone(response.data);
        } catch (error) {
            console.error("Error al crear zona:", error);
            throw error;
        }
    }

    async updateZone(original_name: string, zone: Partial<Zone>): Promise<Zone | null> {
        try {
            const response = await axios.put<Zone>(`${API_URL}/${toApiPath(original_name)}`, {
                ...zone,
                ...(zone.name ? { name: toApiName(zone.name) } : {}),
            });
            return fromApiZone(response.data);
        } catch (error) {
            console.error("Error al actualizar zona:", error);
            throw error;
        }
    }

    async deleteZone(zone_name: string): Promise<boolean> {
        try {
            await axios.delete(`${API_URL}/${toApiPath(zone_name)}`);
            return true;
        } catch (error) {
            console.error("Error al eliminar zona:", error);
            throw error;
        }
    }
}

export const zoneService = new ZoneService();
