import { Formik, Form, Field, ErrorMessage } from "formik";
import * as Yup from "yup";
import { User } from "../../models/User";

interface MyFormProps {
    mode: number; // 1 (crear) o 2 (actualizar), solo para texto/estilos
    handleAction: (values: User) => void;
    user?: User | null;
}

const UserFormValidator: React.FC<MyFormProps> = ({ mode, handleAction, user }) => {
    return (
        <Formik
            initialValues={
                user
                    ? {
                        name: user.name || "",
                        email: user.email || "",
                        phone: user.phone || "",
                    }
                    : {
                        name: "",
                        email: "",
                        phone: "",
                    }
            }
            validationSchema={Yup.object({
                name: Yup.string().required("El nombre es obligatorio"),
                email: Yup.string()
                    .email("Email inválido")
                    .required("El email es obligatorio"),
                phone: Yup.string()
                    .matches(/^\d{10}$/, "El teléfono debe tener 10 dígitos")
                    .required("El teléfono es obligatorio"),
            })}
            onSubmit={(values) => {
                handleAction(values as User);
            }}
        >
            {({ handleSubmit }) => (
                <Form
                    onSubmit={handleSubmit}
                    className="grid grid-cols-1 gap-4 p-6 bg-white rounded-md shadow-md"
                >
                    <div>
                        <label
                            htmlFor="name"
                            className="block text-lg font-medium text-gray-700"
                        >
                            Name
                        </label>
                        <Field
                            type="text"
                            name="name"
                            className="w-full border rounded-md p-2"
                        />
                        <ErrorMessage
                            name="name"
                            component="p"
                            className="text-red-500 text-sm"
                        />
                    </div>

                    <div>
                        <label
                            htmlFor="email"
                            className="block text-lg font-medium text-gray-700"
                        >
                            Email
                        </label>
                        <Field
                            type="email"
                            name="email"
                            className="w-full border rounded-md p-2"
                        />
                        <ErrorMessage
                            name="email"
                            component="p"
                            className="text-red-500 text-sm"
                        />
                    </div>

                    <div>
                        <label
                            htmlFor="phone"
                            className="block text-lg font-medium text-gray-700"
                        >
                            Phone
                        </label>
                        <Field
                            type="text"
                            name="phone"
                            className="w-full border rounded-md p-2"
                        />
                        <ErrorMessage
                            name="phone"
                            component="p"
                            className="text-red-500 text-sm"
                        />
                    </div>

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
                </Form>
            )}
        </Formik>
    );
};

export default UserFormValidator;