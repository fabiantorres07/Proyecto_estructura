import axios from "axios";
import { Mode } from "../models/mode";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/mode`;

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
        } catch (error) {
            console.error("Error al actualizar el modo:", error);
            throw error;
        }
    }
}

export const modeService = new ModeService();