import ReportFormValidator from '../../components/reports/ReportFormValidator';
import { ReportFormValues } from '../../models/Report/ReportFormValues';
import { Station } from '../../models/Station';
import { stationService } from '../../services/stationService';
import { eventService } from '../../services/eventService';
import Swal from 'sweetalert2';
import Breadcrumb from '../../components/Breadcrumb';
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from 'react';
import { getApiErrorMessage } from '../../utils/utils';
import { SCENARIO_STATE_CHANGED_EVENT } from '../../services/undoService';


const CreateEvent = () => {
    const navigate = useNavigate();
    const [stations, setStations] = useState<Station[]>([]);
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
    const handleCreateEvent = async (values: ReportFormValues) => {

        try {
            const createdEvent = await eventService.createEvent({
                event_id: values.event_id,
                station_id: values.station_id,
                magnitude: values.magnitude,
                depth: values.depth,
                x: values.x,
                y: values.y,
                ...(values.ocurred_at ? { occurred_at: values.ocurred_at } : {}),
            });
            if (createdEvent) {
                Swal.fire({
                    title: "Completado",
                    text: `Se ha creado el evento ${createdEvent.event_id}`,
                    icon: "success",
                    timer: 3000
                })
                navigate("/eventos/arboles");
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
            <h2>Crear evento</h2>
            <Breadcrumb pageName="Crear evento" />
            <ReportFormValidator
                handleAction={handleCreateEvent}
                mode={1} // 1 stands for creation
                stations= {stations}
            />
        </div>
    );
};

export default CreateEvent;

