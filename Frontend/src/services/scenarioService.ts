import axios from "axios";
import { ScenarioLoadSummary } from "../models/Scenario/ScenarioLoadSummary";
import { notifyScenarioStateChanged } from "../utils/utils";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/scenario`;

export type ScenarioLoadMode = "insertions" | "topology";

class ScenarioService {
    async exportScenario(loadMode: ScenarioLoadMode): Promise<Record<string, unknown>> {
        const response = await axios.get<Record<string, unknown>>(`${API_URL}/export`, {
            params: { load_mode: loadMode },
        });
        return response.data;
    }

    async loadScenario(data: Record<string, unknown>): Promise<ScenarioLoadSummary> {
        const response = await axios.post<ScenarioLoadSummary>(`${API_URL}/load`, data);
        notifyScenarioStateChanged();
        return response.data;
    }
}

export const scenarioService = new ScenarioService();