import axios from "axios";

interface ClockResponse {
    simulation_clock: string;
}

const API_URL = `${(import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL ?? ""}/clock`;

class ClockService {
    async getClock(): Promise<Date> {
        try {
            const response = await axios.get<ClockResponse>(API_URL);
            return new Date(response.data.simulation_clock);
        } catch (error) {
            console.error("Error al obtener el reloj:", error);
            throw error;
        }
    }

    async updateClock(simulationClock: Date): Promise<void> {
        try {
            await axios.put<ClockResponse>(API_URL, {
                simulation_clock: simulationClock.toISOString(),
            });
        } catch (error) {
            console.error("Error al actualizar el reloj:", error);
            throw error;
        }
    }
}

export const clockService = new ClockService();