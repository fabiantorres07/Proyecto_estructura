import { Event } from '../../models/event';
import EventFormValidator from '../../components/events/EventFormValidator';
import { Station } from '../../models/Station';
import { stationService } from '../../services/stationService';
import Swal from 'sweetalert2';
import Breadcrumb from '../../components/Breadcrumb';
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from 'react';
import { getApiErrorMessage } from '../../utils/utils';


const CreateEvent = () => {
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
    const handleCreateEvent = async (event: Event) => {

        try {
            const createdEvent = await eventService.createReport(event);
            if (createdEvent) {
                Swal.fire({
                    title: "Completado",
                    text: `Se ha creado el evento ${createdEvent.event_id}`,
                    icon: "success",
                    timer: 3000
                })
                console.log("Evento creado con éxito: ", createdEvent );
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
            <h2>Crear evento</h2>
            <Breadcrumb pageName="Crear reporte" />
            <EventFormValidator
                handleAction={handleCreateEvent}
                mode={1} // 1 stands for creation
                stations= {stations}
            />
        </div>
    );
};

export default CreateEvent;

