import axios from "axios";
import { IndicatorsResponse } from "../models/Indicators/IndicatorsResponse";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/indicators`;

class IndicatorsService {
    async getIndicators(): Promise<IndicatorsResponse> {
        const response = await axios.get<IndicatorsResponse>(API_URL);
        return response.data;
    }
}

export const indicatorsService = new IndicatorsService();