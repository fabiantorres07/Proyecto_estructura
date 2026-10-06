import axios from "axios";
import { GlobalParameters } from "../models/Parameters/GlobalParameters";
import { notifyScenarioStateChanged } from "../utils/utils";

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/parameters`;

class ParametersService {
    async getParameters(): Promise<GlobalParameters> {
        const response = await axios.get<GlobalParameters>(API_URL);
        return response.data;
    }

    async updateParameters(parameters: GlobalParameters): Promise<GlobalParameters> {
        const response = await axios.patch<GlobalParameters>(API_URL, parameters);
        notifyScenarioStateChanged();
        return response.data;
    }
}

export const parametersService = new ParametersService();