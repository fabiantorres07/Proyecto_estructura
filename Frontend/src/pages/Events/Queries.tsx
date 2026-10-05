import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import GenericTable from "../../components/GenericTable";
import { CostlyAccessEventResponse } from "../../models/Event/CostlyAccessEventResponse";
import { EventApiResponse } from "../../models/Event/EventApiResponse";
import { EventAssociationsResponse } from "../../models/Event/EventAssociationsResponse";
import { EventDirectoryRow } from "../../models/Event/EventDirectoryRow";
import { EventQueryResponse } from "../../models/Event/EventQueryResponse";
import { eventService } from "../../services/eventService";
import { SCENARIO_UNDONE_EVENT } from "../../services/undoService";
import { getApiErrorMessage } from "../../utils/utils";

type QueryTab = "directory" | "pending" | "magnitude" | "depth-date" | "associations" | "costly";

const tabs: { id: QueryTab; label: string }[] = [
    { id: "directory", label: "Todos los eventos" },
    { id: "pending", label: "Pendientes" },
    { id: "magnitude", label: "Magnitud" },
    { id: "depth-date", label: "Profundidad y fecha" },
    { id: "associations", label: "Asociaciones" },
    { id: "costly", label: "Acceso costoso" },
];

const eventTableColumns = ["event_id", "magnitude", "hypocenter_depth", "priority", "attention_status", "occurred_at"];
const eventTableLabels = {
    event_id: "Evento",
    magnitude: "Magnitud",
    hypocenter_depth: "Profundidad hipocentral",
    priority: "Prioridad",
    attention_status: "Atención",
    occurred_at: "Ocurrencia",
};

const dateLabel = (value: string | null) => value ? new Date(value).toLocaleString() : "-";

const asEventRow = (event: EventApiResponse, relationship?: string) => ({
    event_key: event.event_id,
    ...(relationship ? { relationship } : {}),
    event_id: `SIS-${event.event_id}`,
    magnitude: event.magnitude.toFixed(1),
    hypocenter_depth: `${event.depth.toFixed(1)} km`,
    priority: event.priority,
    attention_status: event.attention_status === "pending" ? "Pendiente" : "Revisado",
    occurred_at: dateLabel(event.occurred_at),
});

const EventQueries = () => {
    const navigate = useNavigate();
    const [tab, setTab] = useState<QueryTab>("directory");
    const [directory, setDirectory] = useState<EventDirectoryRow[]>([]);
    const [queryResult, setQueryResult] = useState<EventQueryResponse | null>(null);
    const [associations, setAssociations] = useState<EventAssociationsResponse | null>(null);
    const [costlyEvents, setCostlyEvents] = useState<CostlyAccessEventResponse[] | null>(null);
    const [visitedNodes, setVisitedNodes] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [k, setK] = useState("5");
    const [minMagnitude, setMinMagnitude] = useState("-2");
    const [maxMagnitude, setMaxMagnitude] = useState("10");
    const [maximumDepth, setMaximumDepth] = useState("700");
    const [minimumDate, setMinimumDate] = useState("");
    const [maximumDate, setMaximumDate] = useState("");
    const [associationEventId, setAssociationEventId] = useState("");

    const loadDirectory = async () => {
        setLoading(true);
        setError(null);
        try {
            setDirectory(await eventService.getDirectory());
        } catch (loadError) {
            setError(getApiErrorMessage(loadError, "No se pudo cargar el directorio de eventos"));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const reloadAfterUndo = () => void loadDirectory();
        void loadDirectory();
        window.addEventListener(SCENARIO_UNDONE_EVENT, reloadAfterUndo);
        return () => window.removeEventListener(SCENARIO_UNDONE_EVENT, reloadAfterUndo);
    }, []);

    const runEventQuery = async (query: () => Promise<EventQueryResponse>) => {
        setLoading(true);
        setError(null);
        setQueryResult(null);
        try {
            const result = await query();
            setQueryResult(result);
            setVisitedNodes(result.visited_nodes);
        } catch (queryError) {
            setError(getApiErrorMessage(queryError, "No se pudo completar la consulta"));
        } finally {
            setLoading(false);
        }
    };

    const submitPending = (formEvent: FormEvent) => {
        formEvent.preventDefault();
        void runEventQuery(() => eventService.getPending(Number(k)));
    };

    const submitMagnitude = (formEvent: FormEvent) => {
        formEvent.preventDefault();
        void runEventQuery(() => eventService.getMagnitudeRange(Number(minMagnitude), Number(maxMagnitude)));
    };

    const submitDepthDate = (formEvent: FormEvent) => {
        formEvent.preventDefault();
        void runEventQuery(() => eventService.getDepthDateRange(
            Number(maximumDepth),
            new Date(minimumDate).toISOString(),
            new Date(maximumDate).toISOString(),
        ));
    };

    const submitAssociations = async (formEvent: FormEvent) => {
        formEvent.preventDefault();
        setLoading(true);
        setError(null);
        setAssociations(null);
        try {
            setAssociations(await eventService.getAssociations(Number(associationEventId)));
        } catch (queryError) {
            setError(getApiErrorMessage(queryError, "No se pudieron cargar las asociaciones"));
        } finally {
            setLoading(false);
        }
    };

    const loadCostlyEvents = async () => {
        setLoading(true);
        setError(null);
        setCostlyEvents(null);
        try {
            setCostlyEvents(await eventService.getCostlyAccess());
        } catch (queryError) {
            setError(getApiErrorMessage(queryError, "No se pudo cargar el acceso costoso"));
        } finally {
            setLoading(false);
        }
    };

    const directoryRows = directory.map((event) => ({
        event_key: event.event_id,
        event_id: `SIS-${event.event_id}`,
        status: event.status === "active" ? "Activo" : event.status === "archived" ? "Archivado" : "Eliminado",
        magnitude: event.magnitude == null ? "-" : event.magnitude.toFixed(1),
        hypocenter_depth: event.hypocenter_depth == null ? "-" : `${event.hypocenter_depth.toFixed(1)} km`,
        priority: event.priority ?? "-",
        attention_status: event.attention_status === "pending" ? "Pendiente" : event.attention_status === "reviewed" ? "Revisado" : "-",
        occurred_at: dateLabel(event.occurred_at),
        node_depth: event.node_depth ?? "-",
        cost: event.cost ?? "-",
    }));

    const queryRows = queryResult?.events.map((event) => asEventRow(event)) ?? [];
    const associationRows = associations ? [
        ...(associations.reference ? [asEventRow(associations.reference.event, "Referencia elegida")] : []),
        ...associations.candidates.map((item) => asEventRow(item.event, `Candidato · ${item.status === "active" ? "activo" : "archivado"}`)),
        ...associations.used_as_reference_by.map((item) => asEventRow(item.event, `Usa este evento · ${item.status === "active" ? "activo" : "archivado"}`)),
    ] : [];
    const costlyRows = costlyEvents?.map((item) => ({
        event_id: `SIS-${item.event.event_id}`,
        magnitude: item.event.magnitude.toFixed(1),
        node_depth: item.depth,
        limit: item.limit,
        visited: item.visited,
    })) ?? [];

    const selectTab = (nextTab: QueryTab) => {
        setTab(nextTab);
        setError(null);
        setQueryResult(null);
        setAssociations(null);
        setCostlyEvents(null);
        setVisitedNodes(null);
    };

    return (
        <main className="mx-auto max-w-screen-2xl space-y-6 p-4 md:p-6 2xl:p-8">
            <header className="border-b border-stroke pb-5">
                <p className="text-sm font-medium uppercase text-meta-5">Consultas e inventario</p>
                <h1 className="mt-1 text-2xl font-semibold text-black">Eventos</h1>
            </header>

            <nav aria-label="Consultas de eventos" className="flex gap-1 overflow-x-auto border-b border-stroke">
                {tabs.map((item) => (
                    <button
                        key={item.id}
                        type="button"
                        aria-pressed={tab === item.id}
                        onClick={() => selectTab(item.id)}
                        className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium ${tab === item.id ? "border-primary text-primary" : "border-transparent text-gray-500 hover:text-black"}`}
                    >
                        {item.label}
                    </button>
                ))}
            </nav>

            {error && <p role="alert" className="border-l-4 border-danger bg-danger/5 px-4 py-3 text-danger">{error}</p>}

            {tab === "directory" && (
                <section className="space-y-4">
                    <div className="flex items-end justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-semibold text-black">Inventario completo</h2>
                            <p className="mt-1 text-sm text-gray-500">El costo del nodo corresponde a su profundidad en el AVL.</p>
                        </div>
                        <button type="button" disabled={loading} onClick={() => void loadDirectory()} className="border border-stroke px-4 py-2 text-sm font-medium text-black hover:bg-gray-2 disabled:opacity-60">
                            Actualizar
                        </button>
                    </div>
                    {loading ? <p className="py-8 text-center text-gray-500">Cargando eventos...</p> : directoryRows.length ? (
                        <GenericTable
                            data={directoryRows}
                            columns={["event_id", "status", "magnitude", "hypocenter_depth", "priority", "attention_status", "occurred_at", "node_depth", "cost"]}
                            columnLabels={{ event_id: "Evento", status: "Estado", magnitude: "Magnitud", hypocenter_depth: "Profundidad hipocentral", priority: "Prioridad", attention_status: "Atención", occurred_at: "Ocurrencia", node_depth: "Profundidad del nodo", cost: "Costo" }}
                            actions={[{ name: "view", label: "Ver evento activo" }]}
                            onAction={(_action, item) => {
                                if (item.status === "Activo") navigate(`/eventos/${item.event_key}`);
                            }}
                        />
                    ) : <p className="py-8 text-center text-gray-500">No hay eventos registrados.</p>}
                </section>
            )}

            {tab === "pending" && (
                <section className="space-y-5">
                    <form onSubmit={submitPending} className="flex flex-wrap items-end gap-4 border-b border-stroke pb-5">
                        <label className="grid gap-1 text-sm font-medium text-black">Cantidad k
                            <input type="number" min="1" step="1" required value={k} onChange={(event) => setK(event.target.value)} className="w-36 border border-stroke px-3 py-2" />
                        </label>
                        <button disabled={loading} className="bg-primary px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">Buscar pendientes</button>
                    </form>
                    {queryResult && <p className="text-sm text-gray-600">Nodos examinados: {visitedNodes}</p>}
                    {queryResult && (queryRows.length ? <GenericTable data={queryRows} columns={eventTableColumns} columnLabels={eventTableLabels} actions={[{ name: "view", label: "Ver evento" }]} onAction={(_action, item) => navigate(`/eventos/${item.event_key}`)} /> : <p className="py-6 text-center text-gray-500">No hay eventos pendientes.</p>)}
                </section>
            )}

            {tab === "magnitude" && (
                <section className="space-y-5">
                    <form onSubmit={submitMagnitude} className="flex flex-wrap items-end gap-4 border-b border-stroke pb-5">
                        <label className="grid gap-1 text-sm font-medium text-black">Magnitud mínima
                            <input type="number" min="-2" max="10" step="0.1" required value={minMagnitude} onChange={(event) => setMinMagnitude(event.target.value)} className="w-40 border border-stroke px-3 py-2" />
                        </label>
                        <label className="grid gap-1 text-sm font-medium text-black">Magnitud máxima
                            <input type="number" min="-2" max="10" step="0.1" required value={maxMagnitude} onChange={(event) => setMaxMagnitude(event.target.value)} className="w-40 border border-stroke px-3 py-2" />
                        </label>
                        <button disabled={loading} className="bg-primary px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">Buscar intervalo</button>
                    </form>
                    {queryResult && <p className="text-sm text-gray-600">Nodos examinados: {visitedNodes}</p>}
                    {queryResult && (queryRows.length ? <GenericTable data={queryRows} columns={eventTableColumns} columnLabels={eventTableLabels} actions={[{ name: "view", label: "Ver evento" }]} onAction={(_action, item) => navigate(`/eventos/${item.event_key}`)} /> : <p className="py-6 text-center text-gray-500">No hay eventos en ese intervalo.</p>)}
                </section>
            )}

            {tab === "depth-date" && (
                <section className="space-y-5">
                    <form onSubmit={submitDepthDate} className="flex flex-wrap items-end gap-4 border-b border-stroke pb-5">
                        <label className="grid gap-1 text-sm font-medium text-black">Profundidad máxima (km)
                            <input type="number" min="0" max="700" step="0.1" required value={maximumDepth} onChange={(event) => setMaximumDepth(event.target.value)} className="w-44 border border-stroke px-3 py-2" />
                        </label>
                        <label className="grid gap-1 text-sm font-medium text-black">Desde
                            <input type="datetime-local" step="1" required value={minimumDate} onChange={(event) => setMinimumDate(event.target.value)} className="border border-stroke px-3 py-2" />
                        </label>
                        <label className="grid gap-1 text-sm font-medium text-black">Hasta
                            <input type="datetime-local" step="1" required value={maximumDate} onChange={(event) => setMaximumDate(event.target.value)} className="border border-stroke px-3 py-2" />
                        </label>
                        <button disabled={loading} className="bg-primary px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">Buscar eventos</button>
                    </form>
                    {queryResult && <p className="text-sm text-gray-600">Nodos examinados: {visitedNodes}</p>}
                    {queryResult && (queryRows.length ? <GenericTable data={queryRows} columns={eventTableColumns} columnLabels={eventTableLabels} actions={[{ name: "view", label: "Ver evento" }]} onAction={(_action, item) => navigate(`/eventos/${item.event_key}`)} /> : <p className="py-6 text-center text-gray-500">No hay eventos que coincidan con los límites.</p>)}
                </section>
            )}

            {tab === "associations" && (
                <section className="space-y-5">
                    <form onSubmit={submitAssociations} className="flex flex-wrap items-end gap-4 border-b border-stroke pb-5">
                        <label className="grid gap-1 text-sm font-medium text-black">ID del evento
                            <input type="number" min="1" max="999999" step="1" required value={associationEventId} onChange={(event) => setAssociationEventId(event.target.value)} className="w-44 border border-stroke px-3 py-2" />
                        </label>
                        <button disabled={loading} className="bg-primary px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">Consultar asociaciones</button>
                    </form>
                    {associations && <>
                        {!associationRows.length ? <p className="py-6 text-center text-gray-500">No se encontraron asociaciones para este evento.</p> : <GenericTable data={associationRows} columns={["relationship", ...eventTableColumns]} columnLabels={{ relationship: "Relación", ...eventTableLabels }} />}
                    </>}
                </section>
            )}

            {tab === "costly" && (
                <section className="space-y-5">
                    <div className="flex flex-wrap items-end justify-between gap-4 border-b border-stroke pb-5">
                        <p className="max-w-2xl text-sm text-gray-600">Eventos de prioridad alta cuya profundidad en el AVL supera el límite configurado. El costo de búsqueda es la cantidad de nodos visitados.</p>
                        <button type="button" disabled={loading} onClick={() => void loadCostlyEvents()} className="bg-primary px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">Consultar acceso costoso</button>
                    </div>
                    {costlyEvents && (costlyRows.length ? (
                        <GenericTable data={costlyRows} columns={["event_id", "magnitude", "node_depth", "limit", "visited"]} columnLabels={{ event_id: "Evento", magnitude: "Magnitud", node_depth: "Profundidad del nodo", limit: "Límite L", visited: "Nodos visitados" }} />
                    ) : <p className="py-6 text-center text-gray-500">No hay eventos con acceso costoso.</p>)}
                </section>
            )}
        </main>
    );
};

export default EventQueries;