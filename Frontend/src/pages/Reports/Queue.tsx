import React, { useEffect, useState } from "react";
import { ReportFormValues } from "../../models/Report/ReportFormValues"
import GenericTable from "../../components/GenericTable";
import { useNavigate } from "react-router-dom";
import { reportService } from "../../services/reportService";
import { getApiErrorMessage } from "../../utils/utils";
import Swal from "sweetalert2";

const ReportQueue: React.FC = () => {
    const navigate = useNavigate();
    const [queue, setQueue] = useState<ReportFormValues[]>([
    ]);
        
    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const queue = await reportService.getQueue();
            setQueue(queue);
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: getApiErrorMessage(error, "No se pudieron cargar las zonas"),
                icon: "error",
            });
        }
    };

    return (
        <div>
            <h2>Cola de reportes</h2>
            <button
                onClick={() => navigate("/reportes/crear")}
                className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-700"
            >
                Crear
            </button>
            <button
                type="button"
                disabled={queue.length === 0}
                onClick={() => navigate("/reportes/revisar")}
                className="ml-2 px-4 py-2 border border-primary text-primary hover:bg-primary hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
                Revisar siguiente
            </button>
            <GenericTable
                data={queue}
                columnLabels={{ position: "posición", event_id: "id evento", revision_num: "número de revisión", station_id: "estación" }}
                columns={["position", "event_id", "revision_num", "station_id"]}
            />
        </div>
    );
};

export default ReportQueue;
