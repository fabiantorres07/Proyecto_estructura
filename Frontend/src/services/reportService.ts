import axios from "axios";
import { Report } from "../models/Report/Report";
import { ReportFormValues } from "../models/Report/ReportFormValues";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/reports`;

class ReportService {
    async getQueue(): Promise<ReportFormValues[]> {
        try {
            const response = await axios.get<ReportFormValues[]>(API_URL);
            return response.data;
        } catch (error) {
            console.error("Error al obtener cola de reportes:", error);
            throw error;
        }
    }

    async getReport(event_id: string, revision_number: string): Promise<ReportFormValues | null> {
        try {
            const response = await axios.get<ReportFormValues>(`${API_URL}/${event_id}/${revision_number}`);
            return response.data;
        } catch (error) {
            console.error("Reporte no encontrado:", error);
            throw error;
        }
    }

    async createReport(report: Report): Promise<ReportFormValues | null> {
        try {
            const response = await axios.post<ReportFormValues>(API_URL, report);
            return response.data;
        } catch (error) {
            console.error("Error al crear reporte:", error);
            throw error;
        }
    }
}

export const reportService = new ReportService();
