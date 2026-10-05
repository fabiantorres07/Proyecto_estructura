import { hierarchy, tree } from "d3-hierarchy";
import { Archive, ListFilter, MessageSquareText, Plus, RefreshCw, RotateCw } from "lucide-react";
import { KeyboardEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Swal from "sweetalert2";
import { CostlyAccessEventResponse } from "../../models/Event/CostlyAccessEventResponse";
import { EventTreeNode } from "../../models/Event/EventTreeNode";
import { EventTreesResponse } from "../../models/Event/EventTreesResponse";
import { TreeComparisonResponse } from "../../models/Event/TreeComparisonResponse";
import { eventService } from "../../services/eventService";
import { modeService } from "../../services/modeService";
import { SCENARIO_UNDONE_EVENT } from "../../services/undoService";
import { getApiErrorMessage } from "../../utils/utils";

interface TreePanelProps {
    title: string;
    rootNode: EventTreeNode | null;
    costlyAccessByEvent?: Map<number, CostlyAccessEventResponse>;
}

const NODE_WIDTH = 164;
const NODE_HEIGHT = 82;
const NODE_X_GAP = 190;
const NODE_Y_GAP = 132;
const HORIZONTAL_PADDING = 40;
const VERTICAL_PADDING = 32;

interface RotationLogEntry {
    recordedAt: Date;
    title: string;
    cases: number;
    elementaryRotations: number;
    mode?: string;
    rotations: {
        case: string;
        event_id: number;
        balance_factor: number;
        rotations: string[];
    }[];
}

const TreePanel: React.FC<TreePanelProps> = ({ title, rootNode, costlyAccessByEvent }) => {
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
                        const costlyAccess = costlyAccessByEvent?.get(event_id);
                        const fill = priority === 3 ? "#dc4a3d" : priority === 2 ? "#d99a22" : "#168c83";
                        return (
                            <g
                                key={event_id}
                                transform={`translate(${nodeX(node.x)}, ${nodeY(node.y)})`}
                                role="treeitem"
                                tabIndex={0}
                                aria-label={`Evento SIS-${event_id}, prioridad ${priority}, magnitud ${magnitude}, ${attention_status}${costlyAccess ? `, acceso costoso: profundidad ${costlyAccess.depth} mayor que L (${costlyAccess.limit})` : ""}`}
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
                                {costlyAccess && (
                                    <g aria-hidden="true">
                                        <circle cx={NODE_WIDTH / 2 - 31} cy={-NODE_HEIGHT / 2 + 13} r="7" fill="#fef3c7" stroke="#b45309" strokeWidth="1.5" />
                                        <text x={NODE_WIDTH / 2 - 31} y={-NODE_HEIGHT / 2 + 17} textAnchor="middle" fill="#92400e" fontSize="11" fontWeight="700">!</text>
                                        <title>Acceso costoso: profundidad {costlyAccess.depth} mayor que L ({costlyAccess.limit})</title>
                                    </g>
                                )}
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
    const [comparison, setComparison] = useState<TreeComparisonResponse | null>(null);
    const [costlyAccessByEvent, setCostlyAccessByEvent] = useState<Map<number, CostlyAccessEventResponse>>(new Map());
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [isRecovering, setIsRecovering] = useState(false);
    const [isArchiving, setIsArchiving] = useState(false);
    const [rotationHistory, setRotationHistory] = useState<RotationLogEntry[]>([]);
    const navigate = useNavigate();

    const loadTrees = async () => {
        setLoading(true);
        setError(null);
        try {
            const [treesResult, costlyAccessResult, comparisonResult] = await Promise.allSettled([
                eventService.getTrees(),
                eventService.getCostlyAccess(),
                eventService.getTreeComparison(),
            ]);
            if (treesResult.status === "rejected") throw treesResult.reason;
            setTrees(treesResult.value);

            if (comparisonResult.status === "fulfilled") {
                setComparison(comparisonResult.value);
            } else {
                setComparison(null);
                setError(getApiErrorMessage(comparisonResult.reason, "No se pudo cargar la comparación AVL/BST"));
            }

            if (costlyAccessResult.status === "fulfilled") {
                setCostlyAccessByEvent(new Map<number, CostlyAccessEventResponse>(
                    costlyAccessResult.value.map((item) => [item.event.event_id, item] as const),
                ));
            } else {
                setCostlyAccessByEvent(new Map());
                setError(getApiErrorMessage(costlyAccessResult.reason, "No se pudo cargar la señal de acceso costoso"));
            }
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
            setRotationHistory((history) => [...history, {
                recordedAt: new Date(),
                title: "Recuperación global AVL",
                cases: result.cases,
                elementaryRotations: result.elementary_rotations,
                mode: result.mode,
                rotations: result.rotations,
            }]);
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

    const archiveEligibleBranch = async () => {
        setIsArchiving(true);
        setError(null);
        try {
            const preview = await eventService.previewBranchArchive();
            if (!preview.eligible || preview.root_id == null || preview.size == null || preview.depth == null) {
                await Swal.fire({
                    title: "No hay un subárbol elegible",
                    text: preview.reason ?? "No se encontró una rama que cumpla las condiciones de archivo.",
                    icon: "info",
                });
                return;
            }

            const eventIds = preview.event_ids.map((eventId) => `SIS-${eventId}`).join(", ");
            const confirmation = await Swal.fire({
                title: "Archivar subárbol",
                text: `Raíz SIS-${preview.root_id} · ${preview.size} eventos · profundidad ${preview.depth}. Eventos: ${eventIds}`,
                icon: "warning",
                showCancelButton: true,
                confirmButtonText: "Archivar",
                cancelButtonText: "Cancelar",
            });
            if (!confirmation.isConfirmed) return;

            const result = await eventService.archiveBranch(preview.root_id);
            if (!result.archived) {
                setError(result.reason ?? "El subárbol dejó de ser elegible después de la vista previa.");
                await loadTrees();
                return;
            }

            const elementaryRotations = result.rotations.reduce(
                (total, item) => total + item.rotations.length,
                0,
            );
            setRotationHistory((history) => [...history, {
                recordedAt: new Date(),
                title: `Archivo del subárbol SIS-${result.root_id ?? preview.root_id}`,
                cases: result.rotations.length,
                elementaryRotations,
                rotations: result.rotations,
            }]);
            await loadTrees();
            await Swal.fire({
                title: "Subárbol archivado",
                text: `${result.size} eventos movidos al archivo. ${elementaryRotations} giros AVL realizados.`,
                icon: "success",
            });
        } catch (archiveError) {
            setError(getApiErrorMessage(archiveError, "No se pudo archivar el subárbol"));
        } finally {
            setIsArchiving(false);
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
                        disabled={loading || isArchiving}
                        onClick={() => void archiveEligibleBranch()}
                        className="inline-flex items-center gap-2 border border-danger px-4 py-2.5 font-medium text-danger hover:bg-danger hover:text-white disabled:cursor-wait disabled:opacity-60"
                    >
                        <Archive size={17} aria-hidden="true" />
                        {isArchiving ? "Archivando..." : "Archivar subárbol"}
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
                <>
                    <p className="flex items-center gap-2 text-sm text-gray-600">
                        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-amber-700 bg-amber-100 text-xs font-bold text-amber-900" aria-hidden="true">!</span>
                        Acceso costoso en AVL: prioridad alta y profundidad mayor que L.
                    </p>
                    <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                        <TreePanel title="AVL · balanceado" rootNode={trees.avl} costlyAccessByEvent={costlyAccessByEvent} />
                        <TreePanel title="BST · sin balanceo" rootNode={trees.bst} />
                    </div>
                    {comparison && (
                        <section className="border border-stroke bg-white dark:border-strokedark dark:bg-boxdark">
                            <header className="border-b border-stroke px-5 py-4 dark:border-strokedark">
                                <h2 className="text-lg font-semibold text-black dark:text-white">Comparación AVL vs BST</h2>
                                <p className="mt-1 text-sm text-gray-500">Búsquedas de las mismas {comparison.n_searches} claves.</p>
                            </header>
                            <div className="overflow-x-auto">
                                <table className="w-full min-w-[480px] text-left text-sm">
                                    <thead className="bg-gray-2 text-xs uppercase text-gray-600 dark:bg-meta-4 dark:text-bodydark2">
                                        <tr>
                                            <th className="px-5 py-3">Métrica</th>
                                            <th className="px-5 py-3">AVL</th>
                                            <th className="px-5 py-3">BST</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Altura</th><td className="px-5 py-3">{comparison.avl.height}</td><td className="px-5 py-3">{comparison.bst.height}</td></tr>
                                        <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Hojas</th><td className="px-5 py-3">{comparison.avl.leaves}</td><td className="px-5 py-3">{comparison.bst.leaves}</td></tr>
                                        <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Comparaciones totales</th><td className="px-5 py-3">{comparison.avl.total_comparisons}</td><td className="px-5 py-3">{comparison.bst.total_comparisons}</td></tr>
                                        <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Máximo por búsqueda</th><td className="px-5 py-3">{comparison.avl.max_single_search}</td><td className="px-5 py-3">{comparison.bst.max_single_search}</td></tr>
                                        <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Promedio por búsqueda</th><td className="px-5 py-3">{comparison.avl.avg_comparisons.toFixed(2)}</td><td className="px-5 py-3">{comparison.bst.avg_comparisons.toFixed(2)}</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    )}
                </>
            ) : null}

            <section className="border border-stroke bg-white">
                <header className="flex items-center justify-between gap-3 border-b border-stroke px-5 py-4">
                    <h2 className="flex items-center gap-2 text-lg font-semibold text-black">
                        <MessageSquareText size={19} aria-hidden="true" />
                        Registro de rotaciones
                    </h2>
                    <span className="text-sm text-gray-500">
                        {rotationHistory.reduce((total, entry) => total + entry.elementaryRotations, 0)} giros
                    </span>
                </header>
                <div role="log" aria-label="Rotaciones realizadas durante la recuperación" aria-live="polite" className="max-h-96 space-y-4 overflow-y-auto bg-gray-2 p-4">
                    {rotationHistory.length === 0 ? (
                        <p className="py-6 text-center text-sm text-gray-500">Sin rotaciones registradas</p>
                    ) : rotationHistory.map((entry, recoveryIndex) => (
                        <article key={`${entry.recordedAt.getTime()}-${recoveryIndex}`} className="space-y-3">
                            <div className="ml-auto max-w-lg rounded-md bg-white p-3 shadow-sm">
                                <p className="text-xs font-medium uppercase text-meta-5">
                                    {entry.title} · {entry.recordedAt.toLocaleTimeString()}
                                </p>
                                <p className="mt-1 text-sm text-black">
                                    {entry.cases} casos · {entry.elementaryRotations} rotaciones elementales{entry.mode ? ` · modo ${entry.mode}` : ""}
                                </p>
                            </div>
                            {entry.rotations.length === 0 ? (
                                <div className="max-w-lg rounded-md border border-stroke bg-white p-3 text-sm text-gray-600">
                                    La operación no necesitó aplicar giros al AVL.
                                </div>
                            ) : entry.rotations.map((rotation, rotationIndex) => (
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