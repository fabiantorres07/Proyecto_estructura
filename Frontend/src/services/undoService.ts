import axios from "axios";
import { UndoResponse } from "../models/Undo/UndoResponse";
import { notifyScenarioStateChanged } from "../utils/utils";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/undo`;

export { SCENARIO_STATE_CHANGED_EVENT, SCENARIO_UNDONE_EVENT } from "../utils/utils";

class UndoService {
    async undo(): Promise<UndoResponse> {
        const response = await axios.post<UndoResponse>(API_URL);
        notifyScenarioStateChanged();
        return response.data;
    }
}

export const undoService = new UndoService();