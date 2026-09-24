import { Formik, Form, Field, ErrorMessage } from "formik";
import * as Yup from "yup";
import { Zone } from "../../models/Zone";

interface MyFormProps {
    mode: number; // 1 (create) or 2 (update)
    handleAction: (values: Zone) => void;
    zone?: Zone | null;
}

const ZoneFormValidator: React.FC<MyFormProps> = ({ mode, handleAction, zone }) => {
    return (
        <Formik
            initialValues={ //Either the existing zone values are filled out, or the boxes come empty if said zone does not exist
                zone
                    ? {
                        name: zone.name || "",
                        is_populated: zone.is_populated ?? false,
                        x_min: zone.x_min || "",
                        y_min: zone.y_min || "",
                        x_max: zone.x_max || "",
                        y_max: zone.y_max || "",
                    }
                    : {
                        name: "",
                        is_populated: false,
                        x_min: "",
                        y_min: "",
                        x_max: "",
                        y_max: "",
                    }
            }
            validationSchema={Yup.object({
                name: Yup.string().required("El nombre de la zona es obligatorio").max(50, "El nombre de la zona no puede tener más de 50 caracteres"),
                x_min: Yup.number().required("Las coordenadas son obligatorias").min(0, "Las coordenadas deben estar entre 0.0 y 1000.0").max(1000, "Las coordenadas deben estar entre 0.0 y 1000.0").test("max-decimals", "Máximo un decimal",value => value == null || Number.isInteger(value * 10)),
                y_min: Yup.number().required("Las coordenadas son obligatorias").min(0, "Las coordenadas deben estar entre 0.0 y 1000.0").max(1000, "Las coordenadas deben estar entre 0.0 y 1000.0").test("max-decimals", "Máximo un decimal",value => value == null || Number.isInteger(value * 10)),
                x_max: Yup.number().required("Las coordenadas son obligatorias").min(0, "Las coordenadas deben estar entre 0.0 y 1000.0").max(1000, "Las coordenadas deben estar entre 0.0 y 1000.0").test("max-decimals", "Máximo un decimal",value => value == null || Number.isInteger(value * 10)),
                y_max: Yup.number().required("Las coordenadas son obligatorias").min(0, "Las coordenadas deben estar entre 0.0 y 1000.0").max(1000, "Las coordenadas deben estar entre 0.0 y 1000.0").test("max-decimals", "Máximo un decimal",value => value == null || Number.isInteger(value * 10)),   
            })}
            onSubmit={(values) => {
                handleAction(values as Zone);
            }}
        >
            {({ handleSubmit }) => (
            <Form
                onSubmit={handleSubmit}
                className="grid grid-cols-1 gap-4 p-6 bg-white rounded-md shadow-md"
            >
                <div>
                    <label
                        htmlFor="Name"
                        className="block text-lg font-medium text-gray-700"
                    >
                        Nombre de zona
                    </label>

                    <Field
                        type="text"
                        name="Name"
                        className="w-full border border-gray-300 rounded-md p-2"
                    />

                    <ErrorMessage
                        name="Name"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>

                <div className="mt-2 flex items-center gap-2">
                    <Field
                        type="checkbox"
                        name="is_populated"
                        className="h-4 w-4"
                    />

                    <label
                        htmlFor="is_populated"
                        className="text-sm font-medium text-gray-700"
                    >
                        ¿Es zona poblada?
                    </label>
                </div>

                <div>
                    <label className="block text-lg font-medium text-gray-700">
                        Coordenadas vértice inferior izquierdo
                    </label>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label
                                htmlFor="x_min"
                                className="block text-sm font-medium text-gray-700"
                            >
                                x
                            </label>

                            <Field
                                type="number"
                                name="x_min"
                                className="w-full border border-gray-300 rounded-md p-2"
                            />

                            <ErrorMessage
                                name="x_min"
                                component="p"
                                className="text-danger text-sm"
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="y_min"
                                className="block text-sm font-medium text-gray-700"
                            >
                                y
                            </label>

                            <Field
                                type="number"
                                name="y_min"
                                className="w-full border border-gray-300 rounded-md p-2"
                            />

                            <ErrorMessage
                                name="y_min"
                                component="p"
                                className="text-danger text-sm"
                            />
                        </div>
                    </div>
                </div>

                <div>
                    <label className="block text-lg font-medium text-gray-700">
                        Coordenadas vértice superior derecho
                    </label>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label
                                htmlFor="x_max"
                                className="block text-sm font-medium text-gray-700"
                            >
                                x
                            </label>

                            <Field
                                type="number"
                                name="x_max"
                                className="w-full border border-gray-300 rounded-md p-2"
                            />

                            <ErrorMessage
                                name="x_max"
                                component="p"
                                className="text-danger text-sm"
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="y_max"
                                className="block text-sm font-medium text-gray-700"
                            >
                                y
                            </label>

                            <Field
                                type="number"
                                name="y_max"
                                className="w-full border border-gray-300 rounded-md p-2"
                            />

                            <ErrorMessage
                                name="y_max"
                                component="p"
                                className="text-danger text-sm"
                            />
                        </div>
                    </div>
                </div>

                <div className="flex justify-end gap-3 pt-2">
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

export default ZoneFormValidator;