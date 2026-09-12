import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { userService } from "../../services/userService";
import Swal from "sweetalert2";

import { User } from "../../models/User";
import Breadcrumb from "../../components/Breadcrumb";
import UserFormValidator from "../../components/users/UserFormValidator";

const UpdateUserPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [user, setUser] = useState<User | null>(null);

    useEffect(() => {
        const fetchUser = async () => {
            if (!id) return;

            const userData = await userService.getUserById(parseInt(id));
            setUser(userData);
        };

        fetchUser();
    }, [id]);

    const handleUpdateUser = async (theUser: User) => {
        try {
            const updatedUser = await userService.updateUser(user?.id || 0, {
                ...user,
                ...theUser,
            });

            if (updatedUser) {
                Swal.fire({
                    title: "Completado",
                    text: "Se ha actualizado correctamente el registro",
                    icon: "success",
                    timer: 3000,
                });
                navigate("/users-list");
            } else {
                Swal.fire({
                    title: "Error",
                    text: "Existe un problema al momento de actualizar el registro",
                    icon: "error",
                    timer: 3000,
                });
            }
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: "Existe un problema al momento de actualizar el registro",
                icon: "error",
                timer: 3000,
            });
        }
    };

    if (!user) {
        return <div>Cargando...</div>;
    }

    return (
        <>
            <Breadcrumb pageName="Actualizar Usuario" />
            <UserFormValidator
                handleAction={handleUpdateUser}
                mode={2}
                user={user}
            />
        </>
    );
};

export default UpdateUserPage;