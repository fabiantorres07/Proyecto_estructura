import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { IndicatorsResponse } from "../../models/Indicators/IndicatorsResponse";
import { StructureAudit } from "../../models/Mode/StructureAudit";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";
import { indicatorsService } from "../../services/indicatorsService";
import { modeService } from "../../services/modeService";
import { getApiErrorMessage } from "../../utils/utils";

type MetricRow = {
    label: string;
    value: string | number;
};

interface MetricTableProps {
    title: string;
    rows: MetricRow[];
}

const MetricTable: React.FC<MetricTableProps> = ({ title, rows }) => (
    <section className="border border-stroke bg-white px-5 dark:border-strokedark dark:bg-boxdark">
        <h2 className="border-b border-stroke py-4 text-lg font-semibold text-black dark:border-strokedark dark:text-white">{title}</h2>
        <dl>
            {rows.map(({ label, value }) => (
                <div key={label} className="flex items-baseline justify-between gap-4 border-b border-stroke py-3 last:border-b-0 dark:border-strokedark">
                    <dt className="text-sm text-gray-600 dark:text-bodydark2">{label}</dt>
                    <dd className="text-right font-semibold text-black dark:text-white">{value}</dd>
                </div>
            ))}
        </dl>
    </section>
);

interface StructureAuditTableProps {
    audit: StructureAudit;
}

const StructureAuditTable: React.FC<StructureAuditTableProps> = ({ audit }) => (
    <section className="border border-stroke bg-white dark:border-strokedark dark:bg-boxdark">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-stroke px-5 py-4 dark:border-strokedark">
            <div>
                <h2 className="text-lg font-semibold text-black dark:text-white">Reporte de estructura</h2>
                <p className="mt-1 text-sm text-gray-600 dark:text-bodydark2">
                    Modo {audit.mode} · {audit.checked_nodes} nodos revisados · {audit.error_count} errores · {audit.expected_count} desbalances esperados
                </p>
            </div>
            <span className={`px-3 py-1 text-sm font-semibold ${audit.is_valid ? "bg-meta-3/10 text-meta-3" : "bg-danger/10 text-danger"}`}>
                {audit.is_valid ? "Estructura válida" : "Estructura inválida"}
            </span>
        </header>
        {audit.issues.length ? (
            <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                    <thead className="bg-gray-2 text-xs uppercase text-gray-600 dark:bg-meta-4 dark:text-bodydark2">
                        <tr>
                            <th className="px-5 py-3">Evento</th>
                            <th className="px-5 py-3">Tipo</th>
                            <th className="px-5 py-3">Severidad</th>
                            <th className="px-5 py-3">Detalle</th>
                        </tr>
                    </thead>
                    <tbody>
                        {audit.issues.map((issue, index) => (
                            <tr key={`${issue.event_id ?? "tree"}-${issue.type}-${index}`} className="border-t border-stroke dark:border-strokedark">
                                <td className="px-5 py-3 font-medium text-black dark:text-white">{issue.event_id == null ? "Árbol" : `SIS-${issue.event_id}`}</td>
                                <td className="px-5 py-3">{issue.type}</td>
                                <td className="px-5 py-3">
                                    <span className={`inline-block px-2 py-1 text-xs font-semibold ${issue.severity === "expected" ? "bg-warning/15 text-warning" : "bg-danger/10 text-danger"}`}>
                                        {issue.severity === "expected" ? "Esperado" : "Error"}
                                    </span>
                                </td>
                                <td className="px-5 py-3 text-gray-600 dark:text-bodydark2">{issue.detail}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        ) : (
            <p className="px-5 py-4 text-sm text-gray-600 dark:text-bodydark2">Sin inconsistencias.</p>
        )}
    </section>
);

const traversal = (ids: number[]) => ids.length ? ids.join(" → ") : "Sin eventos";

const IndicatorsTables = () => {
    const [indicators, setIndicators] = useState<IndicatorsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [audit, setAudit] = useState<StructureAudit | null>(null);
    const [auditLoading, setAuditLoading] = useState(false);
    const [auditError, setAuditError] = useState<string | null>(null);

    const loadIndicators = useCallback(async () => {
        setError(null);
        setLoading(true);
        try {
            setIndicators(await indicatorsService.getIndicators());
        } catch (loadError) {
            setError(getApiErrorMessage(loadError, "No se pudieron cargar los indicadores."));
        } finally {
            setLoading(false);
        }
    }, []);

    const verifyStructure = useCallback(async () => {
        setAuditError(null);
        setAuditLoading(true);
        try {
            setAudit(await modeService.getStructureAudit());
        } catch (auditLoadError) {
            setAuditError(getApiErrorMessage(auditLoadError, "No se pudo verificar la estructura."));
        } finally {
            setAuditLoading(false);
        }
    }, []);

    useEffect(() => {
        const refresh = () => {
            void loadIndicators();
            if (audit) void verifyStructure();
        };
        void loadIndicators();
        window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, refresh);
        return () => window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, refresh);
    }, [audit, loadIndicators, verifyStructure]);

    return (
        <section className="space-y-6">
            <header className="flex flex-wrap items-end justify-between gap-4 border-b border-stroke pb-5">
                <div>
                    <p className="text-sm font-medium uppercase text-meta-5">Indicadores</p>
                    <h2 className="mt-1 text-xl font-semibold text-black dark:text-white">Estado de los árboles</h2>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button
                        type="button"
                        disabled={loading}
                        onClick={() => void loadIndicators()}
                        className="inline-flex items-center gap-2 border border-stroke px-4 py-2.5 font-medium text-black hover:bg-gray-2 disabled:cursor-wait disabled:opacity-60 dark:text-white"
                    >
                        <RefreshCw size={17} aria-hidden="true" className={loading ? "animate-spin" : ""} />
                        Actualizar
                    </button>
                    <button
                        type="button"
                        disabled={auditLoading}
                        onClick={() => void verifyStructure()}
                        className="inline-flex items-center gap-2 border border-primary px-4 py-2.5 font-medium text-primary hover:bg-primary hover:text-white disabled:cursor-wait disabled:opacity-60"
                    >
                        <ShieldCheck size={17} aria-hidden="true" />
                        {auditLoading ? "Verificando..." : "Verificar estructura"}
                    </button>
                </div>
            </header>
            {error && <p role="alert" className="border-l-4 border-danger bg-danger/5 px-4 py-3 text-danger">{error}</p>}
            {loading && !indicators ? (
                <p className="py-12 text-center text-gray-500">Cargando indicadores...</p>
            ) : indicators ? (
                <>
                    <p className="text-sm text-gray-600 dark:text-bodydark2">Modo {indicators.mode} · límite de acceso costoso L={indicators.L}</p>
                    <div className="grid gap-5 xl:grid-cols-2">
                        <MetricTable
                            title="Cantidades y forma"
                            rows={[
                                { label: "Eventos activos", value: indicators.active_events },
                                { label: "Eventos históricos (archivados)", value: indicators.archived_events },
                                { label: "Eventos eliminados", value: indicators.eliminated_events },
                                { label: "Altura del AVL", value: indicators.height },
                                { label: "Hojas", value: indicators.leaves },
                                { label: "Inorden", value: traversal(indicators.traversals.inorder) },
                                { label: "Preorden", value: traversal(indicators.traversals.preorder) },
                                { label: "Postorden", value: traversal(indicators.traversals.postorder) },
                                { label: "Por niveles", value: traversal(indicators.traversals.level_order) },
                            ]}
                        />
                        <MetricTable
                            title="Contadores"
                            rows={[
                                { label: "Correcciones aceptadas", value: indicators.counters.corrections_accepted },
                                { label: "Reportes descartados", value: indicators.counters.reports_discarded },
                                { label: "Conflictos", value: indicators.counters.conflicts },
                                { label: "Archivos masivos", value: indicators.counters.mass_archives },
                                { label: "Eventos archivados", value: indicators.counters.archived_events },
                            ]}
                        />
                        <MetricTable
                            title="Rotaciones AVL"
                            rows={[
                                { label: "Caso LL", value: indicators.rotations.LL },
                                { label: "Caso RR", value: indicators.rotations.RR },
                                { label: "Caso LR", value: indicators.rotations.LR },
                                { label: "Caso RL", value: indicators.rotations.RL },
                                { label: "Giros simples a la izquierda", value: indicators.rotations.simple_left },
                                { label: "Giros simples a la derecha", value: indicators.rotations.simple_right },
                            ]}
                        />
                        <MetricTable
                            title="Eventos"
                            rows={[
                                { label: "Prioridad P1", value: indicators.events_by_priority.P1 },
                                { label: "Prioridad P2", value: indicators.events_by_priority.P2 },
                                { label: "Prioridad P3", value: indicators.events_by_priority.P3 },
                                { label: "Pendientes de atención", value: indicators.pending_attention },
                                { label: "Accesos costosos", value: indicators.costly_access },
                            ]}
                        />
                    </div>
                    {auditError && <p role="alert" className="border-l-4 border-danger bg-danger/5 px-4 py-3 text-danger">{auditError}</p>}
                    {audit && <StructureAuditTable audit={audit} />}
                </>
            ) : !error ? (
                <p className="py-12 text-center text-gray-500">No hay indicadores disponibles.</p>
            ) : null}
        </section>
    );
};

export default IndicatorsTables;
