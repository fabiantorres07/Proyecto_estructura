import { Formik, Form, Field, ErrorMessage } from "formik";
import * as Yup from "yup";
import { Station } from "../../models/Station";

interface MyFormProps {
    mode: number; // 1 (create) or 2 (update)
    handleAction: (values: Station) => void;
    station?: Station | null;
}

const StationFormValidator: React.FC<MyFormProps> = ({ mode, handleAction, station }) => {
    return (
        <Formik
            enableReinitialize
            initialValues={ //Either the existing station values are filled out, or the boxes come empty, if said station does not exist
                station
                    ? {
                        station_id: station.station_id || "",
                        x: station.x ?? "",
                        y: station.y ?? "",
                    }
                    : {
                        station_id: "",
                        x: "",
                        y: "",
                    }
            }
            validationSchema={Yup.object({
                station_id: Yup.string()
                    .required("El ID de la estación es obligatorio")
                    .matches(/^\S+$/, "El ID de la estación no puede contener espacios"),
                x: Yup.number()
                    .required("La coordenada en x de la estación es obligatoria")
                    .min(0, "La coordenada debe estar entre 0 y 1000")
                    .max(1000, "La coordenada debe estar entre 0 y 1000")
                    .test("max-decimals", "Máximo un decimal", value => value == null || Number.isInteger(value * 10)),
                y: Yup.number()
                    .required("La coordenada en y de la estación es obligatoria")
                    .min(0, "La coordenada debe estar entre 0 y 1000")
                    .max(1000, "La coordenada debe estar entre 0 y 1000")
                    .test("max-decimals", "Máximo un decimal", value => value == null || Number.isInteger(value * 10)),
                
            })}
            onSubmit={(values) => {
                handleAction(values as Station);
            }}
        >
            {({ handleSubmit }) => (
            <Form
                onSubmit={handleSubmit}
                className="grid grid-cols-1 gap-4 p-6 bg-white rounded-md shadow-md"
            >
                <div>
                    <label
                        htmlFor="station_id"
                        className="block text-lg font-medium text-gray-700"
                    >
                        ID estación
                    </label>

                    
                    <Field
                        type="text"
                        name="station_id"
                        className="w-full border border-gray-300 rounded-md p-2"
                    />

                    <ErrorMessage
                        name="station_id"
                        component="p"
                        className="text-danger text-sm"
                    />
                </div>


                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label
                            htmlFor="x"
                            className="block text-lg font-medium text-gray-700"
                        >
                            Coordenada en x de la estación
                        </label>

                        <Field
                            type="number"
                            name="x"
                            min="0"
                            max="1000"
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
                            Coordenada en y de la estación
                        </label>

                        <Field
                            type="number"
                            name="y"
                            min="0"
                            max="1000"
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

export default StationFormValidator;