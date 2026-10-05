import { Formik, Form, Field, ErrorMessage } from "formik";
import * as Yup from "yup";
import { Event } from "../../models/Event/Event";
import { EventApiResponse } from "../../models/Event/EventApiResponse";
import { Station } from "../../models/Station";
import { useNavigate } from "react-router-dom";
import { clockService } from "../../services/clockService";
import { formatLocalDateTime } from "../../utils/utils";
import { parseLocalDateTime } from "../../utils/utils";

interface MyFormProps {
    mode: number; // 1 (create), 2 (update), or 3 (view/review)
    handleAction: (values: Event | EventApiResponse) => void;
    event?: Event | EventApiResponse | null;
    stations: Station[];
    archived?: boolean;
    saving?: boolean;
    onCancel?: () => void;
}

const EventFormValidator: React.FC<MyFormProps> = ({ mode, handleAction, event, stations, archived = false, saving = false, onCancel }) => {
    const navigate = useNavigate();
    const eventOccurredAt = event
        ? ("occurred_at" in event ? event.occurred_at : event.ocurred_at)
        : undefined;

    if (mode === 3 && event) {
        const details = event as EventApiResponse;
        return (
            <section className="rounded-md border border-stroke bg-white p-6 shadow-sm">
                <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-stroke pb-5">
                    <div>
                        <p className="text-sm font-medium uppercase text-meta-5">Evento</p>
                        <h2 className="mt-1 text-2xl font-semibold text-black">SIS-{details.event_id}</h2>
                    </div>
                    <span className={`rounded-sm px-3 py-1 text-sm font-medium ${details.attention_status === "reviewed" ? "bg-meta-3/10 text-meta-3" : "bg-warning/10 text-warning"}`}>
                        {details.attention_status === "reviewed" ? "Revisado" : "Pendiente"}
                    </span>
                </div>

                <dl className="grid grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">
                    <div><dt className="text-sm text-gray-500">Magnitud</dt><dd className="mt-1 font-medium text-black">{details.magnitude.toFixed(1)}</dd></div>
                    <div><dt className="text-sm text-gray-500">Profundidad</dt><dd className="mt-1 font-medium text-black">{details.depth.toFixed(1)} km</dd></div>
                    <div><dt className="text-sm text-gray-500">Prioridad</dt><dd className="mt-1 font-medium text-black">{details.priority}</dd></div>
                    <div><dt className="text-sm text-gray-500">Epicentro</dt><dd className="mt-1 font-medium text-black">({details.x.toFixed(1)}, {details.y.toFixed(1)})</dd></div>
                    <div><dt className="text-sm text-gray-500">Fecha</dt><dd className="mt-1 font-medium text-black">{new Date(details.occurred_at).toLocaleString()}</dd></div>
                    <div><dt className="text-sm text-gray-500">Revisión</dt><dd className="mt-1 font-medium text-black">{details.revision}</dd></div>
                    <div><dt className="text-sm text-gray-500">Estaciones</dt><dd className="mt-1 font-medium text-black">{details.stations.map((station) => `Estación ${station}`).join(", ")}</dd></div>
                    <div><dt className="text-sm text-gray-500">Zona poblada</dt><dd className="mt-1 font-medium text-black">{details.is_in_populated_zone ? "Sí" : "No"}</dd></div>
                </dl>

                <div className="mt-8 flex justify-end gap-3 border-t border-stroke pt-5">
                    <button type="button" onClick={() => navigate(-1)} className="rounded-sm border border-stroke px-4 py-2 font-medium text-black hover:bg-gray-2">
                        Volver
                    </button>
                    {!archived && (
                        <button
                            type="button"
                            disabled={details.attention_status === "reviewed"}
                            onClick={() => handleAction(details)}
                            className="rounded-sm bg-meta-3 px-4 py-2 font-medium text-white hover:bg-opacity-90 disabled:cursor-not-allowed disabled:bg-gray-400"
                        >
                            {details.attention_status === "reviewed" ? "Ya revisado" : "Marcar revisado"}
                        </button>
                    )}
                </div>
            </section>
        );
    }

    return (

    <Formik
        initialValues={
            event
                ? {
                    event_id: event.event_id || "",
                    stations: event.stations || [],
                    magnitude: event.magnitude || "",
                    depth: event.depth || "",
                    x: event.x || "",
                    y: event.y || "",
                    ocurred_at: eventOccurredAt
                        ? formatLocalDateTime(new Date(eventOccurredAt))
                        : "",
                    revision: event.revision || "",
                    attention_status: event.attention_status || "pending",
                    is_in_populated_zone:
                        event.is_in_populated_zone ?? false,
                    priority: event.priority || "",
                }
                : {
                    event_id: "",
                    stations: [],
                    magnitude: "",
                    depth: "",
                    x: "",
                    y: "",
                    ocurred_at: "",
                    revision: "",
                    attention_status: "pending",
                    is_in_populated_zone: false,
                    priority: "",
                }
        }
        validationSchema={Yup.object({
            event_id: Yup.number()
                .required("El número del evento es obligatorio")
                .integer("El número del id debe ser un entero")
                .min(1, "El id del evento debe estar entre 1 y 999999")
                .max(999999, "El id del evento debe estar entre 1 y 999999"),

            stations: Yup.array()
                .of(Yup.string())
                .min(1, "Debe seleccionar al menos una estación")
                .required("Debe seleccionar al menos una estación"),

            magnitude: Yup.number()
                .required("La magnitud del evento es obligatoria")
                .min(-2, "La magnitud del evento debe estar entre -2 y 10")
                .max(10, "La magnitud del evento debe estar entre -2 y 10")
                .test(
                    "max-decimals",
                    "Máximo un decimal",
                    (value) =>
                        value == null || Number.isInteger(value * 10)
                ),

            depth: Yup.number()
                .required("La profundidad del evento es obligatoria")
                .min(0, "La profundidad debe estar entre 0 y 700")
                .max(700, "La profundidad debe estar entre 0 y 700")
                .test(
                    "max-decimals",
                    "Máximo un decimal",
                    (value) =>
                        value == null || Number.isInteger(value * 10)
                ),

            x: Yup.number()
                .required("La coordenada en x del evento es obligatoria")
                .min(0, "La coordenada debe estar entre 0 y 1000")
                .max(1000, "La coordenada debe estar entre 0 y 1000")
                .test(
                    "max-decimals",
                    "Máximo un decimal",
                    (value) =>
                        value == null || Number.isInteger(value * 10)
                ),

            y: Yup.number()
                .required("La coordenada en y del evento es obligatoria")
                .min(0, "La coordenada debe estar entre 0 y 1000")
                .max(1000, "La coordenada debe estar entre 0 y 1000")
                .test(
                    "max-decimals",
                    "Máximo un decimal",
                    (value) =>
                        value == null || Number.isInteger(value * 10)
                ),

            ocurred_at: Yup.string().test(
                "valid-local-date-time",
                "La fecha debe ser válida y tener precisión de segundos",
                (value) =>
                    !value || parseLocalDateTime(value) !== null
            ),
        })}
        onSubmit={async (values, { setFieldError }) => {
            const dateValue = String(values.ocurred_at ?? "").trim();
            let occurredAt: Date | undefined;

            if (dateValue) {
                const parsedDate = parseLocalDateTime(dateValue);

                if (!parsedDate) {
                    setFieldError(
                        "ocurred_at",
                        "La fecha debe ser válida y tener precisión de segundos"
                    );
                    return;
                }

                try {
                    const latestSimulationClock =
                        await clockService.getClock();

                    if (parsedDate > latestSimulationClock) {
                        setFieldError(
                            "ocurred_at",
                            "La fecha del sismo no puede ser posterior al reloj de simulación"
                        );
                        return;
                    }
                } catch {
                    setFieldError(
                        "ocurred_at",
                        "No se pudo validar la fecha con el reloj de simulación"
                    );
                    return;
                }

                occurredAt = parsedDate;
            }

            const {
                ocurred_at: _dateValue,
                ...event
            } = values;

            handleAction({
                ...event,
                ...(occurredAt
                    ? { ocurred_at: occurredAt }
                    : {}),
            } as Event);
        }}
    >
        {({ handleSubmit }) => (
        <Form
            onSubmit={handleSubmit}
            className="grid grid-cols-1 gap-4 p-6 bg-white rounded-md shadow-md"
        >
            {/* ID DEL EVENTO */}
            <div>
                <label
                    htmlFor="event_id"
                    className="block text-lg font-medium text-gray-700"
                >
                    Id del evento
                </label>

                <div className="flex">
                    <span className="inline-flex items-center rounded-l-md border border-r-0 border-gray-300 bg-gray-2 px-3 text-gray-700">
                        SIS-
                    </span>

                    <Field
                        type="number"
                        inputMode="numeric"
                        name="event_id"
                        className="w-full rounded-r-md border border-gray-300 p-2"
                    />
                </div>

                <ErrorMessage
                    name="event_id"
                    component="p"
                    className="text-danger text-sm"
                />
            </div>


            {/* ESTACIONES */}
            {mode !== 2 && <div>
                <label className="block text-lg font-medium text-gray-700">
                    Estaciones que reportaron el sismo
                </label>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
                    {stations.map((station) => (
                        <label
                            key={station.station_id}
                            className="flex items-center gap-2"
                        >
                            <Field
                                type="checkbox"
                                name="stations"
                                value={String(station.station_id)}
                                className="w-4 h-4"
                            />

                            <span>
                                {`Estación ${station.station_id}`}
                            </span>
                        </label>
                    ))}
                </div>

                <ErrorMessage
                    name="stations"
                    component="p"
                    className="text-danger text-sm"
                />
            </div>}


            {/* MAGNITUD Y PROFUNDIDAD */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label
                        htmlFor="magnitude"
                        className="block text-lg font-medium text-gray-700"
                    >
                        Magnitud del sismo
                    </label>

                    <Field
                        type="number"
                        name="magnitude"
                        step="0.1"
                        className="w-full border border-gray-300 rounded-md p-2"
                    />

                    <ErrorMessage
                        name="magnitude"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>

                <div>
                    <label
                        htmlFor="depth"
                        className="block text-lg font-medium text-gray-700"
                    >
                        Profundidad del sismo
                    </label>

                    <Field
                        type="number"
                        name="depth"
                        step="0.1"
                        className="w-full border border-gray-300 rounded-md p-2"
                    />

                    <ErrorMessage
                        name="depth"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>
            </div>


            {/* X Y */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label
                        htmlFor="x"
                        className="block text-lg font-medium text-gray-700"
                    >
                        Coordenada en x del sismo
                    </label>

                    <Field
                        type="number"
                        name="x"
                        step="0.1"
                        className="w-full border border-gray-300 rounded-md p-2"
                    />

                    <ErrorMessage
                        name="x"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>

                <div>
                    <label
                        htmlFor="y"
                        className="block text-lg font-medium text-gray-700"
                    >
                        Coordenada en y del sismo
                    </label>

                    <Field
                        type="number"
                        name="y"
                        step="0.1"
                        className="w-full border border-gray-300 rounded-md p-2"
                    />

                    <ErrorMessage
                        name="y"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>
            </div>


            {/* FECHA */}
            <div>
                <label
                    htmlFor="ocurred_at"
                    className="block text-lg font-medium text-gray-700"
                >
                    Fecha del sismo
                </label>

                <Field
                    type="datetime-local"
                    name="ocurred_at"
                    className="w-full border border-gray-300 rounded-md p-2"
                    step="1"
                />

                <ErrorMessage
                    name="ocurred_at"
                    component="p"
                    className="text-danger text-sm"
                />
            </div>


            {/* ESTADO DE ATENCIÓN */}
            {mode !== 2 && <div>
                <label
                    htmlFor="attention_status"
                    className="block text-lg font-medium text-gray-700"
                >
                    Estado de atención
                </label>

                <Field
                    as="select"
                    name="attention_status"
                    disabled={mode === 1}
                    className="w-full border border-gray-300 rounded-md p-2 bg-white disabled:bg-gray-100 disabled:text-gray-500"
                >
                    <option value="pending">Pendiente</option>
                    <option value="in_progress">En progreso</option>
                    <option value="attended">Atendido</option>
                </Field>
            </div>}


            {/* SOLO SE MUESTRAN EN EDICIÓN */}
            {mode !== 1 && (
                <>
                    {/* PRIORIDAD */}
                    <div>
                        <label
                            htmlFor="priority"
                            className="block text-lg font-medium text-gray-700"
                        >
                            Prioridad
                        </label>

                        <Field
                            type="text"
                            name="priority"
                            disabled
                            className="w-full border border-gray-300 rounded-md p-2 bg-gray-100 text-gray-500"
                        />
                    </div>


                    {/* ZONA POBLADA */}
                    <div>
                        <label
                            htmlFor="is_in_populated_zone"
                            className="block text-lg font-medium text-gray-700"
                        >
                            ¿Está en zona poblada?
                        </label>

                        <Field
                            type="checkbox"
                            name="is_in_populated_zone"
                            disabled
                            className="w-5 h-5"
                        />
                    </div>
                </>
            )}


            {/* BOTONES */}
            <div className="flex justify-end gap-3 pt-2">
                <button
                    type="button"
                    disabled={saving}
                    onClick={() => onCancel ? onCancel() : navigate(-1)}
                    className="
                        inline-flex items-center justify-center
                        rounded-full
                        py-2 px-6
                        text-center font-medium
                        text-gray-700
                        bg-gray-200
                        hover:bg-gray-300
                        transition
                    "
                >
                    Volver
                </button>

                <button
                    type="submit"
                    disabled={saving}
                    className={`
                        inline-flex items-center justify-center
                        rounded-full
                        py-2 px-6
                        text-center font-medium text-white
                        hover:bg-opacity-90 transition
                        ${mode === 1 ? "bg-primary" : "bg-meta-3"}
                    `}
                >
                    {mode === 1 ? "Crear" : saving ? "Guardando..." : mode === 2 ? "Guardar cambios" : "Actualizar"}
                </button>
            </div>
        </Form>

        )}
    </Formik>
    );
};

export default EventFormValidator;