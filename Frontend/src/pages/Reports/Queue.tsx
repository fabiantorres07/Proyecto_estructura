import React, { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { ReportFormValues } from "../../models/Report/ReportFormValues"
import GenericTable from "../../components/GenericTable";
import { useNavigate } from "react-router-dom";
import { reportService } from "../../services/reportService";
import { getApiErrorMessage } from "../../utils/utils";
import Swal from "sweetalert2";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";

const ReportQueue: React.FC = () => {
    const navigate = useNavigate();
    const [isClearing, setIsClearing] = useState(false);
    const [queue, setQueue] = useState<ReportFormValues[]>([
    ]);
        
    useEffect(() => {
        const refreshQueue = () => void fetchData();
        void fetchData();
        window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshQueue);
        return () => window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshQueue);
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

    const clearQueue = async () => {
        if (queue.length === 0) return;
        const confirmation = await Swal.fire({
            title: "Limpiar cola de reportes",
            text: `Se descartarán ${queue.length} reportes. Esta acción no se puede deshacer.`,
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Limpiar cola",
            cancelButtonText: "Cancelar",
            confirmButtonColor: "#dc2626",
        });
        if (!confirmation.isConfirmed) return;

        setIsClearing(true);
        try {
            const removed = await reportService.clearQueue();
            await Swal.fire({
                title: "Cola limpiada",
                text: `Se descartaron ${removed} reportes.`,
                icon: "success",
            });
        } catch (error) {
            await Swal.fire({
                title: "No se pudo limpiar la cola",
                text: getApiErrorMessage(error, "Ocurrió un error al descartar los reportes."),
                icon: "error",
            });
        } finally {
            setIsClearing(false);
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
            <button
                type="button"
                disabled={queue.length === 0 || isClearing}
                onClick={() => void clearQueue()}
                className="ml-2 inline-flex items-center gap-2 border border-danger px-4 py-2 text-danger hover:bg-danger hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
                <Trash2 size={16} aria-hidden="true" />
                {isClearing ? "Limpiando..." : "Limpiar cola"}
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
