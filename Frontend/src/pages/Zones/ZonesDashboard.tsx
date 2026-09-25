import React, { useEffect, useState } from "react";
import { Zone } from "../../models/Zone";
import ZoneFormValidator from "../../components/zones/ZoneFormValidator";
import { zoneService } from "../../services/zoneService";
import GenericTable from "../../components/GenericTable";
import Swal from "sweetalert2";
import CartesianPlane from "../../components/map/Plane";

const ZonesDashboard: React.FC = () => {
    const [zones, setZones] = useState<Zone[]>([]);
    let selectedZone: Zone | null = null;
    let currentMode: number = 1; //1 = create, 2 = edit

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        const zones = await zoneService.getZones();
        setZones(zones)
    };

    const handleAction = async (action: string, item: Zone) => {
        if (action === "select") {
            currentMode = 2;
            selectedZone = item;
        } else if (action === "delete") {
            if (!item.name) {
                return;
            }
            try{
                const deletedZone = await zoneService.deleteZone(item.name)
                if (deletedZone){
                    Swal.fire({
                        toast: true,
                        position: "top-end",
                        icon: "success",
                        title: "Zona eliminada",
                        text: `Se ha eliminado la zona ${item.name}`,
                        timer: 3000
                    })

                    await fetchData();
                    selectedZone = null;

                }
                else {
                    Swal.fire({
                        title: "Error",
                        text: "La zona no se ha podido eliminar",
                        icon: "error",
                        timer: 3000
                    })
                }
            }
            catch (error) {
                Swal.fire({
                    title: "Error",
                    text: `Ha habido un error eliminando la zona: ${error}`,
                    icon: "error",
                    timer: 3000
                })
            }

        }
    };

    const handleZoneForm = async (zone: Zone) => {

        if (currentMode === 1){
            try{
                const createdZone = await zoneService.createZone(zone)
                if (createdZone){
                    Swal.fire({
                        toast: true,
                        position: "top-end",
                        icon: "success",
                        title: "Zona creada",
                        text: `Se ha creado la zona ${zone.name}`,
                        timer: 3000
                    })

                    await fetchData();
                    selectedZone = zones.find(SearchedZone => zone.name === SearchedZone.name) ?? null;

                }
                else {
                    Swal.fire({
                        title: "Error",
                        text: "La zona no se ha podido crear",
                        icon: "error",
                        timer: 3000
                    })
                }
            }
            catch (error) {
                Swal.fire({
                    title: "Error",
                    text: `Ha habido un error creando la zona: ${error}`,
                    icon: "error",
                    timer: 3000
                })
            }

        }

        else if (currentMode === 2){
            if (!selectedZone?.name) {
                return;
            }
            try{
                const updatedZone = await zoneService.updateZone(selectedZone.name,zone)
                if (updatedZone){
                    Swal.fire({
                        toast: true,
                        position: "top-end",
                        icon: "success",
                        title: "Zona actualizada",
                        text: `Se ha actualizado la zona ${zone.name}`,
                        timer: 3000
                    })

                    await fetchData();
                    selectedZone = zones.find(SearchedZone => zone.name === SearchedZone.name) ?? null;

                }
                else {
                    Swal.fire({
                        title: "Error",
                        text: "La zona no se ha podido actualizar",
                        icon: "error",
                        timer: 3000
                    })
                }
            }
            catch (error) {
                Swal.fire({
                    title: "Error",
                    text: `Ha habido un error creando la actualizando: ${error}`,
                    icon: "error",
                    timer: 3000
                })
            }

        }
    };

    function handleDeselect(){
        currentMode = 1;
        selectedZone = null;
    }

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
                {selectedZone && (
                    <button
                        type="button"
                        onClick={handleDeselect}
                        className="mt-4 w-full rounded-md bg-gray-500 px-4 py-2 text-white hover:bg-gray-600"
                    >
                        Deseleccionar
                    </button>
                )}

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


