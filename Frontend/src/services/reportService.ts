import axios from "axios";
import { Report } from "../models/Report/Report";
import { ReportFormValues } from "../models/Report/ReportFormValues";
import { ReportReviewResponse } from "../models/Report/ReportReviewResponse";
import { ReportProcessedResponse } from "../models/Report/ReportProcessedResponse";
import { notifyScenarioStateChanged } from "./undoService";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/reports`;

class ReportService {
    private toFormValues(report: Omit<ReportFormValues, "ocurred_at"> & { occurred_at: string }): ReportFormValues {
        const { occurred_at, ...values } = report;
        return { ...values, ocurred_at: new Date(occurred_at) };
    }

    async getQueue(): Promise<ReportFormValues[]> {
        try {
            const response = await axios.get<ReportFormValues[]>(API_URL);
            return response.data;
        } catch (error) {
            console.error("Error al obtener cola de reportes:", error);
            throw error;
        }
    }

    async clearQueue(): Promise<number> {
        const response = await axios.delete<{ removed: number }>(API_URL);
        notifyScenarioStateChanged();
        return response.data.removed;
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
            const { ocurred_at, ...reportData } = report;
            const requestBody = {
                ...reportData,
                ...(ocurred_at ? { occurred_at: ocurred_at.toISOString() } : {}),
            };
            const response = await axios.post<ReportFormValues>(API_URL, requestBody);
            notifyScenarioStateChanged();
            return response.data;
        } catch (error) {
            console.error("Error al crear reporte:", error);
            throw error;
        }
    }

    async createReportsBatch(reports: Report[]): Promise<ReportFormValues[]> {
        const response = await axios.post<ReportFormValues[]>(`${API_URL}/batch`, {
            reports: reports.map(({ ocurred_at, ...report }) => ({
                ...report,
                ...(ocurred_at ? { occurred_at: ocurred_at.toISOString() } : {}),
            })),
        });
        notifyScenarioStateChanged();
        return response.data;
    }

    async getNextReport(): Promise<ReportReviewResponse> {
        const response = await axios.get<{
            report: Omit<ReportFormValues, "ocurred_at"> & { occurred_at: string };
            current_event_status: ReportReviewResponse["current_event_status"];
            current_event: ReportReviewResponse["current_event"];
        }>(`${API_URL}/next`);
        return {
            ...response.data,
            report: this.toFormValues(response.data.report),
        };
    }

    async updateNextReport(report: ReportFormValues): Promise<ReportFormValues> {
        const { position: _position, revision_num: _revision, ocurred_at, ...values } = report;
        const response = await axios.put<Omit<ReportFormValues, "ocurred_at"> & { occurred_at: string }>(
            `${API_URL}/next`,
            {
                ...values,
                ...(ocurred_at ? { occurred_at: ocurred_at.toISOString() } : {}),
            },
        );
        notifyScenarioStateChanged();
        return this.toFormValues(response.data);
    }

    async processNextReport(): Promise<ReportProcessedResponse> {
        const response = await axios.post<ReportProcessedResponse>(`${API_URL}/process-next`);
        notifyScenarioStateChanged();
        return response.data;
    }

    async discardNextReport(): Promise<ReportFormValues> {
        const response = await axios.delete<Omit<ReportFormValues, "ocurred_at"> & { occurred_at: string }>(`${API_URL}/next`);
        notifyScenarioStateChanged();
        return this.toFormValues(response.data);
    }
}

export const reportService = new ReportService();
