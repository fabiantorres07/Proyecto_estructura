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
import { SCENARIO_STATE_CHANGED_EVENT } from '../../services/undoService';


const CreateReport = () => {
    const navigate = useNavigate();
    const [stations, setStations] = useState<Station[]>([]);
    const [batchMode, setBatchMode] = useState(false);
    const [selectedStationIds, setSelectedStationIds] = useState<string[]>([]);
    useEffect(() => {
        const refreshStations = () => void fetchData();
        void fetchData();
        window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshStations);
        return () => window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshStations);
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
            const commonReport = {
                event_id: report.event_id,
                ...(report.revision_num != null ? { revision_num: report.revision_num } : {}),
                magnitude: report.magnitude,
                depth: report.depth,
                x: report.x,
                y: report.y,
                ...(report.ocurred_at ? { ocurred_at: report.ocurred_at } : {}),
            };

            if (batchMode) {
                if (selectedStationIds.length === 0) {
                    await Swal.fire({
                        title: "Selecciona estaciones",
                        text: "El lote necesita al menos una estación emisora.",
                        icon: "warning",
                    });
                    return;
                }
                const batch = selectedStationIds.map((station_id) => ({ ...commonReport, station_id }));
                const createdReports = await reportService.createReportsBatch(batch);
                await Swal.fire({
                    title: "Lote agregado",
                    text: `${createdReports.length} reportes idénticos agregados para las estaciones ${selectedStationIds.join(", ")}. Posiciones ${createdReports[0].position}–${createdReports[createdReports.length - 1].position}.`,
                    icon: "success",
                });
            } else {
                const newReport: Report = { ...commonReport, station_id: report.station_id };
                const createdReport = await reportService.createReport(newReport);
                if (!createdReport) {
                    await Swal.fire({
                        title: "Error",
                        text: "Existe un problema al momento de crear el reporte",
                        icon: "error",
                        timer: 3000,
                    });
                    return;
                }
                await Swal.fire({
                    title: "Completado",
                    text: `Se agregó el reporte a la cola con revisión ${createdReport.revision_num}, en la posición ${createdReport.position}.`,
                    icon: "success",
                    timer: 3000,
                });
            }
            navigate("/reportes/cola");
        } catch (error) {
            await Swal.fire({
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
            <div className="mb-4 inline-flex border border-stroke" role="group" aria-label="Modo de creación de reportes">
                <button type="button" aria-pressed={!batchMode} onClick={() => setBatchMode(false)} className={`px-4 py-2 text-sm font-medium ${!batchMode ? "bg-primary text-white" : "text-body hover:bg-gray-2"}`}>
                    Individual
                </button>
                <button type="button" aria-pressed={batchMode} onClick={() => setBatchMode(true)} className={`border-l border-stroke px-4 py-2 text-sm font-medium ${batchMode ? "bg-primary text-white" : "text-body hover:bg-gray-2"}`}>
                    Lote
                </button>
            </div>
            <ReportFormValidator
                handleAction={handleCreateReport}
                mode={1} // 1 stands for creation
                stations={stations}
                batchMode={batchMode}
                selectedStationIds={selectedStationIds}
                onSelectedStationIdsChange={setSelectedStationIds}
            />
        </div>
    );
};

export default CreateReport;

