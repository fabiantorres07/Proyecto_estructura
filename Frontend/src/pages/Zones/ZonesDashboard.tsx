import React, { useEffect, useState } from "react";
import { Zone } from "../../models/Zone";
import ZoneFormValidator from "../../components/zones/ZoneFormValidator";
import GenericTable from "../../components/GenericTable";
import Swal from "sweetalert2";
import { useNavigate } from "react-router-dom";
import CartesianPlane from "../../components/map/Plane";

const ZonesDashboard: React.FC = () => {
    const navigate = useNavigate();
    const [zones, setZones] = useState<Zone[]>([]);
    let selectedZone: Zone | null = null;
    let currentMode: number = 1;

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
    };

    const handleAction = (action: string, item: Zone) => {
        if (action === "edit") {
            console.log("Edit post:", item);
        } else if (action === "delete") {
            console.log("Delete post:", item);
        }
    };

    const handleZoneForm = async (zone: Zone) => {

        if (currentMode === 1){

        }

        else {

        }
        try {
            const createdUser = await userService.createUser(user);
            if (createdUser) {
                Swal.fire({
                    title: "Completado",
                    text: "Se ha creado correctamente el registro",
                    icon: "success",
                    timer: 3000
                })
                console.log("Usuario creado con éxito:", createdUser);
                navigate("/Users/List");
            } else {
                Swal.fire({
                    title: "Error",
                    text: "Existe un problema al momento de crear el registro",
                    icon: "error",
                    timer: 3000
                })
            }
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: "Existe un problema al momento de crear el registro",
                icon: "error",
                timer: 3000
            })
        }
    };

    const deletePost = async (id: number) => {
        Swal.fire({
            title: "¿Estás seguro que quiere eliminar?",
            text: "¡No podrás revertir esto!",
            icon: "warning",
            showCancelButton: true,
            confirmButtonColor: "#3085d6",
            cancelButtonColor: "#d33",
        }).then(async (result) => {
            if (result.isConfirmed) {
                const success = await postService.deletePost(id);
                if (success) {
                    Swal.fire(
                        "¡Eliminado!",
                        "El post ha sido eliminado.",
                        "success"
                    );
                    fetchData();
                } else {
                    console.error("Error al eliminar el post con id:", id);
                    Swal.fire({
                        icon: "error",
                        title: "Error",
                        text: "No se pudo eliminar el post. Por favor, inténtalo de nuevo.",
                    });
                }
            }
        });
    };

    return (
        <div className="w-full space-y-6">

            {/* Arriba: Form 30% + Tabla 70% */}
            <div className="grid grid-cols-[30%_70%] gap-6">

                <div>
                    <ZoneFormValidator
                        zone={selectedZone ? selectedZone : null}
                        mode={currentMode}
                        handleAction={handleZoneForm}
                    />
                </div>

                <div className="min-w-0">
                    <GenericTable
                        data={zones}
                        columns={["name", "x_min", "y_min", "x_max", "y_max"]}
                        actions={[
                            { name: "select", label: "Seleccionar" },
                            { name: "delete", label: "Borrar" },
                        ]}
                        onAction={handleAction}
                    />
                </div>

            </div>

            <div className="w-full h-[50vh]">
                <CartesianPlane />
            </div>

        </div>
    );
};

export default ZonesDashboard;


