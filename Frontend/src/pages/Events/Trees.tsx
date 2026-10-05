import { hierarchy, tree } from "d3-hierarchy";
import { ListFilter, MessageSquareText, Plus, RefreshCw, RotateCw } from "lucide-react";
import { KeyboardEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { EventTreeNode } from "../../models/Event/EventTreeNode";
import { EventTreesResponse } from "../../models/Event/EventTreesResponse";
import { BalanceRecovery } from "../../models/Mode/BalanceRecovery";
import { eventService } from "../../services/eventService";
import { modeService } from "../../services/modeService";
import { SCENARIO_UNDONE_EVENT } from "../../services/undoService";
import { getApiErrorMessage } from "../../utils/utils";

interface TreePanelProps {
    title: string;
    rootNode: EventTreeNode | null;
}

const NODE_WIDTH = 164;
const NODE_HEIGHT = 82;
const NODE_X_GAP = 190;
const NODE_Y_GAP = 132;
const HORIZONTAL_PADDING = 40;
const VERTICAL_PADDING = 32;

const TreePanel: React.FC<TreePanelProps> = ({ title, rootNode }) => {
    const navigate = useNavigate();

    if (!rootNode) {
        return (
            <section className="min-w-0 border border-stroke bg-white">
                <h2 className="border-b border-stroke px-5 py-4 text-lg font-semibold text-black">{title}</h2>
                <div className="flex min-h-56 items-center justify-center text-sm text-gray-500">No hay eventos activos</div>
            </section>
        );
    }

    const layoutRoot = tree<EventTreeNode>()
        .nodeSize([NODE_X_GAP, NODE_Y_GAP])(
            hierarchy(rootNode, (node) => node.children),
        );
    const nodes = layoutRoot.descendants();
    const links = layoutRoot.links();
    const minimumX = Math.min(...nodes.map((node) => node.x));
    const maximumX = Math.max(...nodes.map((node) => node.x));
    const width = Math.max(
        480,
        maximumX - minimumX + NODE_WIDTH + HORIZONTAL_PADDING * 2,
    );
    const height = Math.max(
        200,
        layoutRoot.height * NODE_Y_GAP + NODE_HEIGHT + VERTICAL_PADDING * 2,
    );
    const nodeX = (x: number) => x - minimumX + HORIZONTAL_PADDING + NODE_WIDTH / 2;
    const nodeY = (y: number) => y + VERTICAL_PADDING + NODE_HEIGHT / 2;

    const openEvent = (eventId: number) => navigate(`/eventos/${eventId}`);
    const handleNodeKeyDown = (event: KeyboardEvent<SVGGElement>, eventId: number) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openEvent(eventId);
        }
    };

    return (
        <section className="min-w-0 border border-stroke bg-white">
            <h2 className="border-b border-stroke px-5 py-4 text-lg font-semibold text-black">{title}</h2>
            <div className="overflow-auto p-4">
                <svg
                    aria-label={`${title}, árbol interactivo de eventos`}
                    className="block max-w-none"
                    width={width}
                    height={height}
                    viewBox={`0 0 ${width} ${height}`}
                    role="tree"
                >
                    <g fill="none" stroke="#cbd5e1" strokeWidth="1.5">
                        {links.map(({ source, target }) => {
                            const sourceX = nodeX(source.x);
                            const sourceY = nodeY(source.y) + NODE_HEIGHT / 2;
                            const targetX = nodeX(target.x);
                            const targetY = nodeY(target.y) - NODE_HEIGHT / 2;
                            const midpointY = (sourceY + targetY) / 2;
                            return (
                                <path
                                    key={`${source.data.event_id}-${target.data.event_id}`}
                                    d={`M ${sourceX} ${sourceY} C ${sourceX} ${midpointY}, ${targetX} ${midpointY}, ${targetX} ${targetY}`}
                                />
                            );
                        })}
                    </g>
                    {nodes.map((node) => {
                        const { event_id, priority, magnitude, attention_status } = node.data;
                        const fill = priority === 3 ? "#dc4a3d" : priority === 2 ? "#d99a22" : "#168c83";
                        return (
                            <g
                                key={event_id}
                                transform={`translate(${nodeX(node.x)}, ${nodeY(node.y)})`}
                                role="treeitem"
                                tabIndex={0}
                                aria-label={`Evento SIS-${event_id}, prioridad ${priority}, magnitud ${magnitude}, ${attention_status}`}
                                className="cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-primary"
                                onClick={() => openEvent(event_id)}
                                onKeyDown={(event) => handleNodeKeyDown(event, event_id)}
                            >
                                <rect
                                    x={-NODE_WIDTH / 2}
                                    y={-NODE_HEIGHT / 2}
                                    width={NODE_WIDTH}
                                    height={NODE_HEIGHT}
                                    rx="8"
                                    fill="white"
                                    stroke={fill}
                                    strokeWidth="3"
                                />
                                <text x={-NODE_WIDTH / 2 + 12} y="-17" textAnchor="start" fill={fill} fontSize="12" fontWeight="700">
                                    Prioridad: {priority}
                                </text>
                                <text x={-NODE_WIDTH / 2 + 12} y="4" textAnchor="start" fill="#334155" fontSize="12" fontWeight="600">
                                    Magnitud: {magnitude.toFixed(1)}
                                </text>
                                <text x={-NODE_WIDTH / 2 + 12} y="25" textAnchor="start" fill="#334155" fontSize="12" fontWeight="600">
                                    ID: SIS-{event_id}
                                </text>
                                <circle cx={NODE_WIDTH / 2 - 13} cy={-NODE_HEIGHT / 2 + 13} r="5" fill={attention_status === "reviewed" ? "#a7f3d0" : "#fef3c7"} stroke="white" strokeWidth="1.5" />
                            </g>
                        );
                    })}
                </svg>
            </div>
        </section>
    );
};

const EventTrees = () => {
    const [trees, setTrees] = useState<EventTreesResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [isRecovering, setIsRecovering] = useState(false);
    const [rotationHistory, setRotationHistory] = useState<{
        recordedAt: Date;
        result: BalanceRecovery;
    }[]>([]);
    const navigate = useNavigate();

    const loadTrees = async () => {
        setLoading(true);
        setError(null);
        try {
            setTrees(await eventService.getTrees());
        } catch (loadError) {
            setError(getApiErrorMessage(loadError, "No se pudieron cargar los árboles de eventos"));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const reloadAfterUndo = () => void loadTrees();
        void loadTrees();
        window.addEventListener(SCENARIO_UNDONE_EVENT, reloadAfterUndo);
        return () => window.removeEventListener(SCENARIO_UNDONE_EVENT, reloadAfterUndo);
    }, []);

    const balanceAvl = async () => {
        setIsRecovering(true);
        setError(null);
        try {
            const result = await modeService.recoverBalance();
            setRotationHistory((history) => [...history, { recordedAt: new Date(), result }]);
            await loadTrees();
            if (!result.audit.is_valid || !result.audit.is_avl) {
                setError("La recuperación terminó, pero la auditoría aún detecta problemas en el AVL.");
            }
        } catch (recoveryError) {
            setError(getApiErrorMessage(recoveryError, "No se pudo balancear el AVL"));
        } finally {
            setIsRecovering(false);
        }
    };

    return (
        <main className="mx-auto max-w-screen-2xl space-y-6 p-4 md:p-6 2xl:p-8">
            <header className="flex flex-wrap items-end justify-between gap-4 border-b border-stroke pb-5">
                <div>
                    <p className="text-sm font-medium uppercase text-meta-5">Estructuras activas</p>
                    <h1 className="mt-1 text-2xl font-semibold text-black">Árboles de eventos</h1>
                </div>
                <div className="flex gap-2">
                    <button type="button" onClick={() => navigate("/eventos/consultas")} className="inline-flex items-center gap-2 border border-stroke px-4 py-2.5 font-medium text-black hover:bg-gray-2">
                        <ListFilter size={17} aria-hidden="true" /> Consultas
                    </button>
                    <button type="button" onClick={() => void loadTrees()} title="Actualizar árboles" aria-label="Actualizar árboles" className="inline-flex h-10 w-10 items-center justify-center border border-stroke text-gray-600 hover:bg-gray-2">
                        <RefreshCw size={17} />
                    </button>
                    <button
                        type="button"
                        disabled={isRecovering}
                        onClick={() => void balanceAvl()}
                        className="inline-flex items-center gap-2 border border-primary px-4 py-2.5 font-medium text-primary hover:bg-primary hover:text-white disabled:cursor-wait disabled:opacity-60"
                    >
                        <RotateCw size={17} aria-hidden="true" />
                        Balancear AVL
                    </button>
                    <button type="button" onClick={() => navigate("/eventos/crear")} className="inline-flex items-center gap-2 bg-primary px-4 py-2.5 font-medium text-white hover:bg-opacity-90">
                        <Plus size={17} /> Crear evento
                    </button>
                </div>
            </header>

            {error && <p role="alert" className="border-l-4 border-danger bg-danger/5 px-4 py-3 text-danger">{error}</p>}
            {loading ? (
                <p className="py-12 text-center text-gray-500">Cargando árboles...</p>
            ) : trees ? (
                <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                    <TreePanel title="AVL · balanceado" rootNode={trees.avl} />
                    <TreePanel title="BST · sin balanceo" rootNode={trees.bst} />
                </div>
            ) : null}

            <section className="border border-stroke bg-white">
                <header className="flex items-center justify-between gap-3 border-b border-stroke px-5 py-4">
                    <h2 className="flex items-center gap-2 text-lg font-semibold text-black">
                        <MessageSquareText size={19} aria-hidden="true" />
                        Registro de rotaciones
                    </h2>
                    <span className="text-sm text-gray-500">
                        {rotationHistory.reduce((total, entry) => total + entry.result.elementary_rotations, 0)} giros
                    </span>
                </header>
                <div role="log" aria-label="Rotaciones realizadas durante la recuperación" aria-live="polite" className="max-h-96 space-y-4 overflow-y-auto bg-gray-2 p-4">
                    {rotationHistory.length === 0 ? (
                        <p className="py-6 text-center text-sm text-gray-500">Sin rotaciones registradas</p>
                    ) : rotationHistory.map((entry, recoveryIndex) => (
                        <article key={`${entry.recordedAt.getTime()}-${recoveryIndex}`} className="space-y-3">
                            <div className="ml-auto max-w-lg rounded-md bg-white p-3 shadow-sm">
                                <p className="text-xs font-medium uppercase text-meta-5">
                                    Recuperación {recoveryIndex + 1} · {entry.recordedAt.toLocaleTimeString()}
                                </p>
                                <p className="mt-1 text-sm text-black">
                                    {entry.result.cases} casos · {entry.result.elementary_rotations} rotaciones elementales · modo {entry.result.mode}
                                </p>
                            </div>
                            {entry.result.rotations.length === 0 ? (
                                <div className="max-w-lg rounded-md border border-stroke bg-white p-3 text-sm text-gray-600">
                                    El árbol ya estaba balanceado; no se necesitaron giros.
                                </div>
                            ) : entry.result.rotations.map((rotation, rotationIndex) => (
                                <div key={`${recoveryIndex}-${rotationIndex}`} className="max-w-lg rounded-md border border-stroke bg-white p-3 shadow-sm">
                                    <p className="font-medium text-black">
                                        Caso {rotation.case} · Evento SIS-{rotation.event_id}
                                    </p>
                                    <p className="mt-1 text-sm text-gray-600">
                                        Factor de balance {rotation.balance_factor} · {rotation.rotations.map((direction) => direction === "left" ? "giro izquierdo" : "giro derecho").join(" → ")}
                                    </p>
                                </div>
                            ))}
                        </article>
                    ))}
                </div>
            </section>
        </main>
    );
};

export default EventTrees;