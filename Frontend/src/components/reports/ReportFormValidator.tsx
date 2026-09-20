import { Formik, Form, Field, ErrorMessage } from "formik";
import * as Yup from "yup";
import { ReportFormValues } from "../../models/Report/ReportFormValues";
import { Station } from "../../models/Station";
import { useNavigate } from "react-router-dom";

interface MyFormProps {
    mode: number; // 1 (create) or 2 (update)
    handleAction: (values: ReportFormValues) => void;
    report?: ReportFormValues | null;
    stations: Station[];
}

const ReportFormValidator: React.FC<MyFormProps> = ({ mode, handleAction, report, stations }) => {
    const navigate = useNavigate();
    return (
        <Formik
            initialValues={ //Either the existing report values are filled out, or the boxes come empty, if said report does not exist
                report
                    ? {
                        event_id: report.event_id || "",
                        station: report.station || "",
                        magnitude: report.magnitude || "",
                        depth: report.depth || "",
                        x: report.x || "",
                        y: report.y || "",
                        ocurred_at: report.ocurred_at || "",
                    }
                    : {
                        event_id: "",
                        station: "",
                        magnitude: "",
                        depth: "",
                        x: "",
                        y: "",
                        ocurred_at: "",
                    }
            }
            validationSchema={Yup.object({
                event_id: Yup.string().required("El id del evento es obligatorio"),
                station: Yup.string().required("La estación de donde proviene el informe es obligatoria"),
                magnitude: Yup.number().required("La magnitud del evento es obligatoria"),
                depth: Yup.number().required("La profundidad del evento es obligatoria"),
                x: Yup.number().required("La coordenada en x del evento es obligatoria"),
                y: Yup.number().required("La coordenada en y del evento es obligatoria"),
                ocurred_at: Yup.date(),
                
            })}
            onSubmit={(values) => {
                handleAction(values as ReportFormValues);
            }}
        >
            {({ handleSubmit }) => (
            <Form
                onSubmit={handleSubmit}
                className="grid grid-cols-1 gap-4 p-6 bg-white rounded-md shadow-md"
            >
                <div>
                    <label
                        htmlFor="event_id"
                        className="block text-lg font-medium text-gray-700"
                    >
                        Id del evento
                    </label>

                    <Field
                        type="text"
                        name="event_id"
                        className="w-full border border-gray-300 rounded-md p-2"
                    />

                    <ErrorMessage
                        name="event_id"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>

                <div>
                    <label
                        htmlFor="station"
                        className="block text-lg font-medium text-gray-700"
                    >
                        Estación
                    </label>

                    <Field
                        as="select"
                        name="station"
                        className="w-full border border-gray-300 rounded-md p-2 bg-white"
                    >
                        <option value="">Seleccione una estación</option>

                        {stations.map((station) => (
                            <option
                                key={station.station_id}
                                value={station.station_id}
                            >
                                {`Estación ${station.station_id}`}
                            </option>
                        ))}
                    </Field>

                    <ErrorMessage
                        name="station"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>

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
                            className="w-full border border-gray-300 rounded-md p-2"
                        />

                        <ErrorMessage
                            name="depth"
                            component="p"
                            className="text-danger text-sm"
                        />
                    </div>
                </div>

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
                            className="w-full border border-gray-300 rounded-md p-2"
                        />

                        <ErrorMessage
                            name="y"
                            component="p"
                            className="text-danger text-sm"
                        />
                    </div>
                </div>

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

                <div className="flex justify-end gap-3 pt-2">
                    <button
                        type="button"
                        onClick={() => navigate(-1)}
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
                        className={`
                            inline-flex items-center justify-center
                            rounded-full
                            py-2 px-6
                            text-center font-medium text-white
                            hover:bg-opacity-90 transition
                            ${mode === 1 ? "bg-primary" : "bg-meta-3"}
                        `}
                    >
                        {mode === 1 ? "Crear" : "Actualizar"}
                    </button>
                </div>
            </Form>
            )}
        </Formik>
    );
};

export default ReportFormValidator;