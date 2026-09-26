import React, { useEffect, useState } from "react";
import { Zone } from "../../models/Zone";
import ZoneFormValidator from "../../components/zones/ZoneFormValidator";
import { zoneService } from "../../services/zoneService";
import GenericTable from "../../components/GenericTable";
import Swal from "sweetalert2";
import CartesianPlane from "../../components/map/Plane";

const ZonesDashboard: React.FC = () => {
    const [zones, setZones] = useState<Zone[]>([]);
    const [selectedZone, setSelectedZone] = useState<Zone | null>(null);
    const [currentMode, setCurrentMode] = useState(1); //1 = create, 2 = edit

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        const zones = await zoneService.getZones();
        setZones(zones)
    };

    const handleAction = async (action: string, item: Zone) => {
        if (action === "select") {
            setCurrentMode(2);
            setSelectedZone(item);
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
                    setSelectedZone(null);
                    setCurrentMode(1);

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
                    setSelectedZone(createdZone);
                    setCurrentMode(2);

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
                    setSelectedZone(updatedZone);

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
        setCurrentMode(1);
        setSelectedZone(null);
    }

    return (
        <div className="w-full space-y-6">

            {/* Arriba: Form 30% + Tabla 70% */}
            <div className="grid min-w-0 grid-cols-[minmax(0,3fr)_minmax(0,7fr)] gap-6">

                <div className="min-w-0">
                    <ZoneFormValidator
                        zone={selectedZone ? selectedZone : null}
                        mode={currentMode}
                        handleAction={handleZoneForm}
                    />
                    {selectedZone && (
                        <button
                            type="button"
                            onClick={handleDeselect}
                            className="mt-4 w-full rounded-md bg-meta-1 px-4 py-2 font-medium text-white hover:bg-opacity-90"
                        >
                            Deseleccionar
                        </button>
                    )}
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
                <CartesianPlane zones={zones} selectedZone={selectedZone} />
            </div>

        </div>
    );
};

export default ZonesDashboard;


