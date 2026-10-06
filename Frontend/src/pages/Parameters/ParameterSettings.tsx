import { FormEvent, useEffect, useState } from "react";
import Swal from "sweetalert2";
import { GlobalParameters } from "../../models/Parameters/GlobalParameters";
import { parametersService } from "../../services/parametersService";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";

const descriptions = {
    L: "Máxima profundidad del árbol para definir un acceso como costoso.",
    W: "Máxima diferencia de tiempo en horas entre eventos para ser considerados réplicas.",
    R: "Máxima distancia en kilómetros entre dos eventos para ser considerados réplicas.",
    T: "Mínima edad en horas de un evento para ser considerado como candidato a ser archivado.",
};

const fieldClassName = "w-full rounded border border-stroke bg-transparent px-4 py-3 text-black outline-none focus:border-primary dark:border-strokedark dark:bg-meta-4 dark:text-white";

const ParameterSettings = () => {
    const [parameters, setParameters] = useState<GlobalParameters | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        let active = true;
        const loadParameters = () => {
            setLoading(true);
            parametersService.getParameters()
            .then((data) => {
                if (active) setParameters(data);
            })
            .catch(() => {
                if (active) {
                    void Swal.fire({
                        title: "Error",
                        text: "Could not load parameters from the backend.",
                        icon: "error",
                    });
                }
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        };
        loadParameters();
        window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, loadParameters);
        return () => {
            active = false;
            window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, loadParameters);
        };
    }, []);

    const updateValue = (name: keyof GlobalParameters, value: number) => {
        setParameters((current) => current ? { ...current, [name]: value } : current);
    };

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!parameters) return;
        if (!Number.isInteger(parameters.L)) {
            await Swal.fire({
                title: "Invalid value",
                text: "L must be a whole number.",
                icon: "warning",
            });
            return;
        }

        setSaving(true);
        try {
            const updated = await parametersService.updateParameters(parameters);
            setParameters(updated);
            await Swal.fire({
                title: "Saved",
                text: "Parameters updated.",
                icon: "success",
            });
        } catch {
            await Swal.fire({
                title: "Error",
                text: "Could not update parameters. Check the values and backend connection.",
                icon: "error",
            });
        } finally {
            setSaving(false);
        }
    };

    return (
        <main className="mx-auto max-w-4xl">
            <section className="border border-stroke bg-white dark:border-strokedark dark:bg-boxdark">
                <div className="border-b border-stroke px-6 py-5 dark:border-strokedark">
                    <h3 className="text-lg font-semibold text-black dark:text-white">Configuración global</h3>
                    <p className="mt-1 text-sm text-bodydark2">Estos valores controlan las asociasiones entre eventos y el comportamiento de los archivos.</p>
                </div>
                {loading ? (
                    <p className="px-6 py-8 text-sm">Cargando parámetros…</p>
                ) : parameters ? (
                    <form onSubmit={handleSubmit} className="space-y-6 p-6">
                        {(["L", "W", "R", "T"] as const).map((name) => (
                            <div key={name} className="grid gap-2 sm:grid-cols-[5rem_minmax(0,1fr)_12rem] sm:items-center sm:gap-6">
                                <label htmlFor={`parameter-${name}`} className="font-semibold text-black dark:text-white">{name}</label>
                                <p className="text-sm text-bodydark2">{descriptions[name]}</p>
                                <input
                                    id={`parameter-${name}`}
                                    className={fieldClassName}
                                    type="number"
                                    min={name === "L" ? 0 : 1}
                                    step={name === "L" ? 1 : "any"}
                                    required
                                    value={parameters[name]}
                                    onChange={(event) => updateValue(name, event.target.valueAsNumber)}
                                />
                            </div>
                        ))}
                        <div className="flex justify-end border-t border-stroke pt-5 dark:border-strokedark">
                            <button type="submit" disabled={saving} className="rounded bg-primary px-5 py-2.5 font-medium text-white disabled:cursor-not-allowed disabled:opacity-60">
                                {saving ? "Guardando" : "Guardar"}
                            </button>
                        </div>
                    </form>
                ) : (
                    <p role="alert" className="px-6 py-8 text-sm text-danger">Los parámetros no están disponibles actualmente</p>
                )}
            </section>
        </main>
    );
};

export default ParameterSettings;