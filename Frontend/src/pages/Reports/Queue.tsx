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

    const handleAction = (action: string, item: Report) => {
        if (action === "edit") {
            console.log("Edit report:", item);
        } else if (action === "delete") {
            console.log("Delete report:", item);
        }
    };
    
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
            <GenericTable
                data={queue}
                columns={["position", "event_id", "revision_num", "station"]}
                actions={[
                    { name: "edit", label: "Editar" },
                    { name: "delete", label: "Borrar" },
                ]}
                onAction={handleAction}
            />
        </div>
    );
};

export default ReportQueue;
