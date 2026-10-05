import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import Swal from "sweetalert2";
import EventFormValidator from "../../components/events/EventFormValidator";
import CartesianPlane from "../../components/map/Plane";
import Breadcrumb from "../../components/Breadcrumb";
import { Event } from "../../models/Event/Event";
import { EventMapPoint } from "../../models/Event/EventMapPoint";
import { EventApiResponse } from "../../models/Event/EventApiResponse";
import { EventAssociationsResponse } from "../../models/Event/EventAssociationsResponse";
import { Station } from "../../models/Station";
import { Zone } from "../../models/Zone";
import { eventService } from "../../services/eventService";
import { stationService } from "../../services/stationService";
import { zoneService } from "../../services/zoneService";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";
import { getApiErrorMessage } from "../../utils/utils";

const EventDetail = () => {
    const { eventId } = useParams<{ eventId: string }>();
    const navigate = useNavigate();
    const [event, setEvent] = useState<EventApiResponse | null>(null);
    const [associations, setAssociations] = useState<EventAssociationsResponse | null>(null);
    const [stations, setStations] = useState<Station[]>([]);
    const [zones, setZones] = useState<Zone[]>([]);
    const [mapError, setMapError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [deleting, setDeleting] = useState(false);

    useEffect(() => {
        let active = true;
        const loadEvent = async () => {
            try {
                const [result, eventAssociations] = await Promise.all([
                    eventService.getEvent(eventId ?? ""),
                    eventService.getAssociations(Number(eventId)),
                ]);
                if (active) {
                    setEvent(result);
                    setAssociations(eventAssociations);
                }
                try {
                    const [loadedStations, loadedZones] = await Promise.all([
                        stationService.getStations(),
                        zoneService.getZones(),
                    ]);
                    if (active) {
                        setStations(loadedStations);
                        setZones(loadedZones);
                    }
                } catch (mapLoadError) {
                    if (active) setMapError(getApiErrorMessage(mapLoadError, "No se pudieron cargar estaciones y zonas"));
                }
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
        const refreshEvent = () => void loadEvent();
        window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshEvent);
        return () => {
            active = false;
            window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshEvent);
        };
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

    const relatedEvents = associations ? [
        ...(associations.reference ? [{ relationship: "Referencia elegida", ...associations.reference }] : []),
        ...associations.candidates.map((item) => ({
            relationship: `Candidato · ${item.status === "active" ? "activo" : "archivado"}`,
            ...item,
        })),
        ...associations.used_as_reference_by.map((item) => ({
            relationship: `Lo referencia · ${item.status === "active" ? "activo" : "archivado"}`,
            ...item,
        })),
    ] : [];
    const associatedEventsById = new Map<number, EventApiResponse>();
    relatedEvents.forEach(({ event: relatedEvent }) => {
        associatedEventsById.set(relatedEvent.event_id, relatedEvent);
    });
    const associatedEventIds = Array.from(associatedEventsById.keys());
    const mapEvents: EventMapPoint[] = event
        ? [event, ...Array.from(associatedEventsById.values())].map(({ event_id, x, y }) => ({
            event_id,
            x,
            y,
        }))
        : [];
    const highlightedStationIds = Array.from(new Set([
        ...(event?.stations ?? []),
        ...Array.from(associatedEventsById.values()).flatMap((relatedEvent) => relatedEvent.stations),
    ]));

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
                    <section className="space-y-4 border border-stroke bg-white p-5">
                        <header className="border-b border-stroke pb-3">
                            <h2 className="text-lg font-semibold text-black">Eventos asociados</h2>
                            <p className="mt-1 text-sm text-gray-500">Referencia elegida, candidatos y eventos que utilizan SIS-{event.event_id} como referencia.</p>
                        </header>
                        {relatedEvents.length ? (
                            <ul className="divide-y divide-stroke">
                                {relatedEvents.map(({ relationship, status, event: relatedEvent }) => (
                                    <li key={`${relationship}-${relatedEvent.event_id}`} className="flex flex-wrap items-center justify-between gap-3 py-3">
                                        <div>
                                            <p className="font-medium text-black">SIS-{relatedEvent.event_id}</p>
                                            <p className="text-sm text-gray-500">{relationship} · magnitud {relatedEvent.magnitude.toFixed(1)} · {status}</p>
                                        </div>
                                        <button type="button" onClick={() => navigate(`/eventos/${relatedEvent.event_id}`)} className="text-sm font-medium text-primary hover:underline">
                                            Ver evento
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="py-4 text-sm text-gray-500">No hay eventos asociados.</p>
                        )}
                    </section>
                    <section className="space-y-3">
                        <div>
                            <h2 className="text-lg font-semibold text-black">Mapa de eventos asociados</h2>
                            <p className="mt-1 text-sm text-gray-500">El evento seleccionado aparece en ámbar; los relacionados, en verde azulado.</p>
                        </div>
                        {mapError && <p role="alert" className="text-sm text-danger">{mapError}</p>}
                        <div className="h-[60vh] min-h-96 w-full">
                            <CartesianPlane
                                stations={stations}
                                zones={zones}
                                events={mapEvents}
                                highlightedEventId={event.event_id}
                                associatedEventIds={associatedEventIds}
                                highlightedStationIds={highlightedStationIds}
                            />
                        </div>
                    </section>
                </>
            ) : null}
        </main>
    );
};

export default EventDetail;