import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { IndicatorsResponse } from "../../models/Indicators/IndicatorsResponse";
import { StructureAudit } from "../../models/Mode/StructureAudit";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";
import { indicatorsService } from "../../services/indicatorsService";
import { modeService } from "../../services/modeService";
import { getApiErrorMessage } from "../../utils/utils";

const metricClass = "flex items-baseline justify-between gap-4 border-b border-stroke py-3 last:border-b-0 dark:border-strokedark";

const IndicatorsDashboard = () => {
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

    const metric = (label: string, value: string | number) => (
        <div key={label} className={metricClass}>
            <dt className="text-sm text-gray-600 dark:text-bodydark2">{label}</dt>
            <dd className="text-right font-semibold text-black dark:text-white">{value}</dd>
        </div>
    );

    const traversal = (ids: number[]) => ids.length ? ids.join(" → ") : "Sin eventos";

    return (
        <main className="mx-auto max-w-screen-2xl space-y-6 p-4 md:p-6 2xl:p-8">
            <header className="flex flex-wrap items-end justify-between gap-4 border-b border-stroke pb-5">
                <div>
                    <p className="text-sm font-medium uppercase text-meta-5">Sección 14</p>
                    <h1 className="mt-1 text-2xl font-semibold text-black dark:text-white">Panel de indicadores</h1>
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
                        <section className="border border-stroke bg-white px-5 dark:border-strokedark dark:bg-boxdark">
                            <h2 className="border-b border-stroke py-4 text-lg font-semibold text-black dark:border-strokedark dark:text-white">Cantidades y forma</h2>
                            <dl>
                                {metric("Eventos activos", indicators.active_events)}
                                {metric("Eventos históricos (archivados)", indicators.archived_events)}
                                {metric("Eventos eliminados", indicators.eliminated_events)}
                                {metric("Altura del AVL", indicators.height)}
                                {metric("Hojas", indicators.leaves)}
                                {metric("Inorden", traversal(indicators.traversals.inorder))}
                                {metric("Preorden", traversal(indicators.traversals.preorder))}
                                {metric("Postorden", traversal(indicators.traversals.postorder))}
                                {metric("Por niveles", traversal(indicators.traversals.level_order))}
                            </dl>
                        </section>

                        <section className="border border-stroke bg-white px-5 dark:border-strokedark dark:bg-boxdark">
                            <h2 className="border-b border-stroke py-4 text-lg font-semibold text-black dark:border-strokedark dark:text-white">Contadores</h2>
                            <dl>
                                {metric("Correcciones aceptadas", indicators.counters.corrections_accepted)}
                                {metric("Reportes descartados", indicators.counters.reports_discarded)}
                                {metric("Conflictos", indicators.counters.conflicts)}
                                {metric("Archivos masivos", indicators.counters.mass_archives)}
                                {metric("Eventos archivados", indicators.counters.archived_events)}
                            </dl>
                        </section>

                        <section className="border border-stroke bg-white px-5 dark:border-strokedark dark:bg-boxdark">
                            <h2 className="border-b border-stroke py-4 text-lg font-semibold text-black dark:border-strokedark dark:text-white">Rotaciones AVL</h2>
                            <dl>
                                {metric("Caso LL", indicators.rotations.LL)}
                                {metric("Caso RR", indicators.rotations.RR)}
                                {metric("Caso LR", indicators.rotations.LR)}
                                {metric("Caso RL", indicators.rotations.RL)}
                                {metric("Giros simples a la izquierda", indicators.rotations.simple_left)}
                                {metric("Giros simples a la derecha", indicators.rotations.simple_right)}
                            </dl>
                        </section>

                        <section className="border border-stroke bg-white px-5 dark:border-strokedark dark:bg-boxdark">
                            <h2 className="border-b border-stroke py-4 text-lg font-semibold text-black dark:border-strokedark dark:text-white">Eventos</h2>
                            <dl>
                                {metric("Prioridad P1", indicators.events_by_priority.P1)}
                                {metric("Prioridad P2", indicators.events_by_priority.P2)}
                                {metric("Prioridad P3", indicators.events_by_priority.P3)}
                                {metric("Pendientes de atención", indicators.pending_attention)}
                                {metric("Accesos costosos", indicators.costly_access)}
                            </dl>
                        </section>
                    </div>
                    {auditError && <p role="alert" className="border-l-4 border-danger bg-danger/5 px-4 py-3 text-danger">{auditError}</p>}
                    {audit && (
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
                    )}
                </>
            ) : !error ? (
                <p className="py-12 text-center text-gray-500">No hay indicadores disponibles.</p>
            ) : null}
        </main>
    );
};

export default IndicatorsDashboard;