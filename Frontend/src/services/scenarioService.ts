import axios from "axios";
import { ScenarioLoadSummary } from "../models/Scenario/ScenarioLoadSummary";
import { SCENARIO_STATE_CHANGED_EVENT } from "./undoService";

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
        if (typeof window !== "undefined") {
            window.dispatchEvent(new Event(SCENARIO_STATE_CHANGED_EVENT));
        }
        return response.data;
    }
}

export const scenarioService = new ScenarioService();