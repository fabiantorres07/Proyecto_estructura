import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import Swal from "sweetalert2";
import EventFormValidator from "../../components/events/EventFormValidator";
import Breadcrumb from "../../components/Breadcrumb";
import { Event } from "../../models/Event/Event";
import { EventApiResponse } from "../../models/Event/EventApiResponse";
import { eventService } from "../../services/eventService";
import { getApiErrorMessage } from "../../utils/utils";

const EventDetail = () => {
    const { eventId } = useParams<{ eventId: string }>();
    const navigate = useNavigate();
    const [event, setEvent] = useState<EventApiResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [deleting, setDeleting] = useState(false);

    useEffect(() => {
        let active = true;
        const loadEvent = async () => {
            try {
                const result = await eventService.getEvent(eventId ?? "");
                if (active) setEvent(result);
            } catch (error) {
                if (active) {
                    await Swal.fire({
                        title: "Error",
                        text: getApiErrorMessage(error, "No se pudo cargar el evento"),
                        icon: "error",
                    });
                    navigate("/eventos/arboles", { replace: true });
                }
            } finally {
                if (active) setLoading(false);
            }
        };
        void loadEvent();
        return () => { active = false; };
    }, [eventId, navigate]);

    const markReviewed = async (values: Event | EventApiResponse) => {
        if (!event || event.attention_status === "reviewed") return;
        try {
            setEvent(await eventService.markReviewed(Number(values.event_id)));
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: getApiErrorMessage(error, "No se pudo marcar el evento como revisado"),
                icon: "error",
            });
        }
    };

    const deleteEvent = async () => {
        if (!event) return;
        const confirmation = await Swal.fire({
            title: "Eliminar evento",
            text: `SIS-${event.event_id} se marcará como eliminado y no podrá reactivarse mediante reportes.`,
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Eliminar",
            cancelButtonText: "Cancelar",
            confirmButtonColor: "#dc2626",
        });
        if (!confirmation.isConfirmed) return;

        setDeleting(true);
        try {
            await eventService.deleteEvent(event.event_id);
            await Swal.fire({
                title: "Evento eliminado",
                text: `SIS-${event.event_id} ya no está activo.`,
                icon: "success",
            });
            navigate("/eventos/consultas");
        } catch (error) {
            await Swal.fire({
                title: "No se pudo eliminar el evento",
                text: getApiErrorMessage(error, "Verifica que el evento siga activo"),
                icon: "error",
            });
        } finally {
            setDeleting(false);
        }
    };

    return (
        <main className="mx-auto max-w-screen-xl space-y-5 p-4 md:p-6 2xl:p-8">
            <Breadcrumb pageName="Detalle del evento" />
            {loading ? (
                <p className="py-12 text-center text-gray-500">Cargando evento...</p>
            ) : event ? (
                <>
                    <div className="flex justify-end">
                        <button
                            type="button"
                            disabled={deleting}
                            onClick={() => void deleteEvent()}
                            className="inline-flex items-center gap-2 border border-danger px-4 py-2 font-medium text-danger hover:bg-danger hover:text-white disabled:cursor-wait disabled:opacity-60"
                        >
                            <Trash2 size={16} aria-hidden="true" />
                            {deleting ? "Eliminando..." : "Eliminar evento"}
                        </button>
                    </div>
                    <EventFormValidator
                        mode={3}
                        event={event}
                        stations={[]}
                        handleAction={markReviewed}
                    />
                </>
            ) : null}
        </main>
    );
};

export default EventDetail;