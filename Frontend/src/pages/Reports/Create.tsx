import { ReportFormValues } from '../../models/Report/ReportFormValues';
import ReportFormValidator from '../../components/reports/ReportFormValidator';
import { reportService } from '../../services/reportService';
import { Report } from '../../models/Report/Report';
import { Station } from '../../models/Station';
import { stationService } from '../../services/stationService';
import Swal from 'sweetalert2';
import Breadcrumb from '../../components/Breadcrumb';
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from 'react';
import { getApiErrorMessage } from '../../utils/utils';


const CreateReport = () => {
    const navigate = useNavigate();
    const [stations, setStations] = useState<Station[]>([]);
    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const stations = await stationService.getStations();
            setStations(stations);
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: getApiErrorMessage(error, "No se pudieron cargar las estaciones"),
                icon: "error",
            });
        }
    };
    // Creation logic
    const handleCreateReport = async (report: ReportFormValues) => {

        try {
            const newReport: Report = {
                event_id: report.event_id,
                station_id: report.station_id,
                magnitude: report.magnitude,
                depth: report.depth,
                x: report.x,
                y: report.y,
                ...(report.ocurred_at ? { ocurred_at: report.ocurred_at } : {}),
            }
            const createdReport = await reportService.createReport(newReport);
            if (createdReport) {
                Swal.fire({
                    title: "Completado",
                    text: `Se ha agregado el reporte a la cola, el número de revisión es ${createdReport.revision_num} y su posición actual en la cola es ${createdReport.position}`,
                    icon: "success",
                    timer: 3000
                })
                console.log("Reporte creado con éxito:", createdReport);
                navigate("/reportes/cola");
            } else {
                Swal.fire({
                    title: "Error",
                    text: "Existe un problema al momento de crear el reporte",
                    icon: "error",
                    timer: 3000
                })
            }
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: getApiErrorMessage(error, "Existe un problema al momento de crear el reporte"),
                icon: "error",
                timer: 3000
            })
        }
    };
    return (
        <div>
            {/* Form for report creation */}
            <h2>Crear reporte</h2>
            <Breadcrumb pageName="Crear reporte" />
            <ReportFormValidator
                handleAction={handleCreateReport}
                mode={1} // 1 stands for creation
                stations= {stations}
            />
        </div>
    );
};

export default CreateReport;

