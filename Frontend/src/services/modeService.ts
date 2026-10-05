import axios from "axios";
import { BalanceRecovery } from "../models/Mode/BalanceRecovery";
import { Mode } from "../models/Mode/Mode";
import { StructureAudit } from "../models/Mode/StructureAudit";
import { notifyScenarioStateChanged } from "./undoService";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/mode`;

export const MODE_STATE_UPDATED_EVENT = "sismolab:mode-state-updated";

export interface ModeStateUpdateEvent {
    stressMode: boolean;
    isAvlBalanced: boolean;
}

class ModeService {
    async getMode(): Promise<boolean> {
        try {
            const response = await axios.get<Mode>(API_URL);
            return response.data.mode === "Stress"
        } catch (error) {
            console.error("Error al obtener el modo:", error);
            throw error;
        }
    }

    async updateMode(stressMode: boolean): Promise<void> {
        let mode = "";
        if (stressMode){
            mode = "Stress"
        }
        else{
            mode = "Normal"
        }
        const newMode: Mode ={
            mode,
        }
        try {
            await axios.put<Mode>(API_URL, newMode);
            notifyScenarioStateChanged();
        } catch (error) {
            console.error("Error al actualizar el modo:", error);
            throw error;
        }
    }

    async getStructureAudit(): Promise<StructureAudit> {
        const response = await axios.get<StructureAudit>(`${API_URL}/structure`);
        return response.data;
    }

    async recoverBalance(): Promise<BalanceRecovery> {
        const response = await axios.post<BalanceRecovery>(`${API_URL}/recover-balance`);
        const result = response.data;
        if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent<ModeStateUpdateEvent>(MODE_STATE_UPDATED_EVENT, {
                detail: {
                    stressMode: result.mode === "Stress",
                    isAvlBalanced: result.audit.is_valid && result.audit.is_avl,
                },
            }));
        }
        notifyScenarioStateChanged();
        return result;
    }
}

export const modeService = new ModeService();