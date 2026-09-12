//src/components/Auth/PotectedRoute.tsx


import { Navigate, Outlet } from "react-router-dom";
import { LocalStorageProvider } from "../../storage/LocalStorageProvider";
import { User } from "../../models/User";


const storage = new LocalStorageProvider();

// Función para verificar si el usuario está autenticado
const isAuthenticated = () => {
    const user = storage.getItem("user");

    if (!user) return false;

    try {
        const parsedUser : User= JSON.parse(user);
        return !!parsedUser; // puedes validar más campos aquí si quieres
    } catch (error) {
        return false;
    }
};

// Componente de Ruta Protegida
const ProtectedRoute = () => {
    return isAuthenticated() ? <Outlet /> : <Navigate to="/auth/signin" replace />;
};

export default ProtectedRoute;


