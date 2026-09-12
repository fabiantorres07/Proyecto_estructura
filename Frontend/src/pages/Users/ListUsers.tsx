import React, { useEffect, useState } from "react";
import { User } from "../../models/User";
import GenericTable from "../../components/GenericTable";
import { userService } from "../../services/userService";
import Swal from "sweetalert2";
import { Link, useNavigate } from "react-router-dom";

const Users: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<User[]>([]);

    // 🔹 Llamar `fetchData` cuando el componente se monta
    useEffect(() => {
        fetchData();
    }, []);

    // 🔹 Obtiene los datos de los usuarios
    const fetchData = async () => {
        const users = await userService.getUsers();
        setData(users);
    };

    const handleAction = (action: string, item: User) => {
        if (action === "edit") {
            console.log("Edit user:", item);
            navigate(`/users-edit/${item.id}`);
        } else if (action === "delete") {
            console.log("Delete user:", item);
            deleteUser(item.id ? item.id : 0);
        }
    };

    const deleteUser = async (id: number) => {
        Swal.fire({
            title: '¿Estás seguro que quiere eliminar?',
            text: "¡No podrás revertir esto!",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',

        }).then(async (result) => {
            if (result.isConfirmed) {
                const success = await userService.deleteUser(id);
                if (success) {
                    // Refrescar la lista de usuarios después de eliminar
                    Swal.fire(
                        '¡Eliminado!',
                        'El usuario ha sido eliminado.',
                        'success'
                    );
                    fetchData();
                } else {
                    console.error("Error al eliminar el usuario con id:", id);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'No se pudo eliminar el usuario. Por favor, inténtalo de nuevo.',
                    });
                }
            }
        });

    }

    const handleCreate = () => {
        console.log("Create user");
        navigate("/users-create");
    };


    return (
        <div>
            <h2>User List</h2>
            <button
                onClick={handleCreate}
                className="inline-flex items-center justify-center bg-primary py-2 px-4 text-sm font-medium text-white rounded-md hover:bg-opacity-90 transition"
            >
                Crear
            </button>

            <GenericTable
                data={data}
                columns={["id", "name", "email"]}
                actions={[
                    { name: "edit", label: "Edit" },
                    { name: "delete", label: "Delete" },
                ]}
                onAction={handleAction}
            />
        </div>
    );
};

export default Users;
