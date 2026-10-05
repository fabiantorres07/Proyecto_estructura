import axios from "axios";
import { VersionRestoreSummary } from "../models/Version/VersionRestoreSummary";
import { VersionSaved, VersionSummary } from "../models/Version/VersionSummary";
import { notifyScenarioStateChanged } from "./undoService";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/versions`;

class VersionService {
    async getVersions(): Promise<VersionSummary[]> {
        const response = await axios.get<VersionSummary[]>(API_URL);
        return response.data;
    }

    async saveVersion(name: string): Promise<VersionSaved> {
        const response = await axios.post<VersionSaved>(API_URL, { name });
        return response.data;
    }

    async restoreVersion(name: string): Promise<VersionRestoreSummary> {
        const response = await axios.post<VersionRestoreSummary>(`${API_URL}/${encodeURIComponent(name)}/restore`);
        notifyScenarioStateChanged();
        return response.data;
    }

    async deleteVersion(name: string): Promise<void> {
        await axios.delete(`${API_URL}/${encodeURIComponent(name)}`);
    }
}

export const versionService = new VersionService();