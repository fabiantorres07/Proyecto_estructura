import axios from "axios";
import { UndoResponse } from "../models/Undo/UndoResponse";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/undo`;

export const SCENARIO_STATE_CHANGED_EVENT = "sismolab:scenario-state-changed";
export const SCENARIO_UNDONE_EVENT = SCENARIO_STATE_CHANGED_EVENT;

export const notifyScenarioStateChanged = () => {
    if (typeof window !== "undefined") {
        window.dispatchEvent(new Event(SCENARIO_STATE_CHANGED_EVENT));
    }
};

class UndoService {
    async undo(): Promise<UndoResponse> {
        const response = await axios.post<UndoResponse>(API_URL);
        notifyScenarioStateChanged();
        return response.data;
    }
}

export const undoService = new UndoService();