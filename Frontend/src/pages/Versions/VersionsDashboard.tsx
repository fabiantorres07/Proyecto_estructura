import { FormEvent, useCallback, useEffect, useState } from "react";
import { RefreshCw, RotateCcw, Save, Trash2 } from "lucide-react";
import Swal from "sweetalert2";
import { VersionSummary } from "../../models/Version/VersionSummary";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";
import { versionService } from "../../services/versionService";
import { getApiErrorMessage } from "../../utils/utils";

const VersionsDashboard = () => {
    const [versions, setVersions] = useState<VersionSummary[]>([]);
    const [name, setName] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [busyVersion, setBusyVersion] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const loadVersions = useCallback(async () => {
        setError(null);
        try {
            setVersions(await versionService.getVersions());
        } catch (loadError) {
            setError(getApiErrorMessage(loadError, "No se pudieron cargar las versiones."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadVersions();
        window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, loadVersions);
        return () => window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, loadVersions);
    }, [loadVersions]);

    const saveCurrentVersion = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const versionName = name.trim();
        if (!versionName || versionName.length > 80 || /[\\/]/.test(versionName)) {
            setError("Usa un nombre de 1 a 80 caracteres, sin / ni \\");
            return;
        }

        setSaving(true);
        setError(null);
        try {
            const result = await versionService.saveVersion(versionName);
            setName("");
            await loadVersions();
            await Swal.fire({
                title: "Versión guardada",
                text: `Se guardó "${result.saved}". Total: ${result.total_versions}.`,
                icon: "success",
            });
        } catch (saveError) {
            setError(getApiErrorMessage(saveError, "No se pudo guardar la versión."));
        } finally {
            setSaving(false);
        }
    };

    const restoreVersion = async (version: VersionSummary) => {
        const confirmation = await Swal.fire({
            title: "Restaurar versión",
            text: `Se reemplazará el escenario actual por "${version.name}". Podrás deshacer la restauración.`,
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Restaurar",
            cancelButtonText: "Cancelar",
        });
        if (!confirmation.isConfirmed) return;

        setBusyVersion(version.name);
        try {
            const result = await versionService.restoreVersion(version.name);
            await Swal.fire({
                title: "Versión restaurada",
                text: `${result.active_events} activos, ${result.archived_events} archivados y ${result.queued_reports} reportes en cola. Usa Deshacer para volver al escenario anterior.`,
                icon: "success",
            });
            window.location.reload();
        } catch (restoreError) {
            await Swal.fire({
                title: "No se pudo restaurar",
                text: getApiErrorMessage(restoreError, "La versión no se pudo restaurar."),
                icon: "error",
            });
        } finally {
            setBusyVersion(null);
        }
    };

    const deleteVersion = async (version: VersionSummary) => {
        const confirmation = await Swal.fire({
            title: "Borrar versión",
            text: `Se eliminará permanentemente "${version.name}".`,
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Borrar",
            cancelButtonText: "Cancelar",
            confirmButtonColor: "#dc2626",
        });
        if (!confirmation.isConfirmed) return;

        setBusyVersion(version.name);
        try {
            await versionService.deleteVersion(version.name);
            await loadVersions();
        } catch (deleteError) {
            setError(getApiErrorMessage(deleteError, "No se pudo borrar la versión."));
        } finally {
            setBusyVersion(null);
        }
    };

    return (
        <main className="mx-auto max-w-screen-2xl space-y-6 p-4 md:p-6 2xl:p-8">
            <header className="flex flex-wrap items-end justify-between gap-4 border-b border-stroke pb-5">
                <div>
                    <p className="text-sm font-medium uppercase text-meta-5">Escenarios persistentes</p>
                    <h1 className="mt-1 text-2xl font-semibold text-black dark:text-white">Versiones guardadas</h1>
                </div>
                <button type="button" disabled={loading} onClick={() => void loadVersions()} aria-label="Actualizar versiones" className="inline-flex h-10 w-10 items-center justify-center border border-stroke text-gray-600 hover:bg-gray-2 disabled:opacity-60">
                    <RefreshCw size={17} aria-hidden="true" className={loading ? "animate-spin" : ""} />
                </button>
            </header>

            {error && <p role="alert" className="border-l-4 border-danger bg-danger/5 px-4 py-3 text-danger">{error}</p>}

            <form onSubmit={(event) => void saveCurrentVersion(event)} className="flex flex-wrap items-end gap-3 border-b border-stroke pb-6 dark:border-strokedark">
                <label className="min-w-60 flex-1 text-sm font-medium text-black dark:text-white" htmlFor="version-name">
                    Nombre de la versión
                    <input id="version-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={80} required className="mt-2 block w-full border border-stroke bg-white px-3 py-2.5 text-black outline-none focus:border-primary dark:border-strokedark dark:bg-boxdark dark:text-white" placeholder="antes de la ráfaga" />
                </label>
                <button type="submit" disabled={saving || !name.trim()} className="inline-flex items-center gap-2 bg-primary px-4 py-2.5 font-medium text-white disabled:cursor-not-allowed disabled:opacity-60">
                    <Save size={17} aria-hidden="true" />
                    {saving ? "Guardando..." : "Guardar versión actual"}
                </button>
            </form>

            {loading ? (
                <p className="py-12 text-center text-gray-500">Cargando versiones...</p>
            ) : versions.length === 0 ? (
                <p className="py-12 text-center text-gray-500">No hay versiones guardadas.</p>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full min-w-[760px] text-left text-sm">
                        <thead className="bg-gray-2 text-xs uppercase text-gray-600 dark:bg-meta-4 dark:text-bodydark2">
                            <tr>
                                <th className="px-4 py-3">Nombre</th>
                                <th className="px-4 py-3">Reloj de simulación</th>
                                <th className="px-4 py-3">Modo</th>
                                <th className="px-4 py-3">Activos</th>
                                <th className="px-4 py-3">Archivados</th>
                                <th className="px-4 py-3">En cola</th>
                                <th className="px-4 py-3">Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {versions.map((version) => (
                                <tr key={version.name} className="border-b border-stroke dark:border-strokedark">
                                    <th className="px-4 py-3 font-semibold text-black dark:text-white">{version.name}</th>
                                    <td className="px-4 py-3">{version.simulation_clock ? new Date(version.simulation_clock).toLocaleString() : "-"}</td>
                                    <td className="px-4 py-3">{version.mode ?? "-"}</td>
                                    <td className="px-4 py-3">{version.active_events}</td>
                                    <td className="px-4 py-3">{version.archived_events}</td>
                                    <td className="px-4 py-3">{version.queued_reports}</td>
                                    <td className="px-4 py-3">
                                        <div className="flex gap-2">
                                            <button type="button" disabled={busyVersion !== null} onClick={() => void restoreVersion(version)} title="Restaurar versión" aria-label={`Restaurar ${version.name}`} className="inline-flex h-9 w-9 items-center justify-center border border-primary text-primary hover:bg-primary hover:text-white disabled:opacity-50">
                                                <RotateCcw size={16} aria-hidden="true" />
                                            </button>
                                            <button type="button" disabled={busyVersion !== null} onClick={() => void deleteVersion(version)} title="Borrar versión" aria-label={`Borrar ${version.name}`} className="inline-flex h-9 w-9 items-center justify-center border border-danger text-danger hover:bg-danger hover:text-white disabled:opacity-50">
                                                <Trash2 size={16} aria-hidden="true" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </main>
    );
};

export default VersionsDashboard;