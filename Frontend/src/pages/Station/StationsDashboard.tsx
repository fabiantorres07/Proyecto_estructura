import React, { useEffect, useState } from "react";
import { Station } from "../../models/Station";
import GenericTable from "../../components/GenericTable";
import Swal from "sweetalert2";
import StationFormValidator from "../../components/stations/StationFormValidator";
import { getApiErrorMessage } from "../../utils/utils";
import CartesianPlane from "../../components/map/Plane";
import { stationService } from "../../services/stationService";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";

const StationsDashboard: React.FC = () => {
    const [stations, setStations] = useState<Station[]>([]);
    const [selectedStation, setSelectedStation] = useState<Station | null>(null);
    const [currentMode, setCurrentMode] = useState(1); //1 = create, 2 = edit

    useEffect(() => {
        const refreshStations = () => {
            void fetchData();
            setSelectedStation(null);
            setCurrentMode(1);
        };
        void fetchData();
        window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshStations);
        return () => window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshStations);
    }, []);

    const fetchData = async () => {
        try {
            const stations = await stationService.getStations();
            setStations(stations);
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: getApiErrorMessage(error, "No se pudieron cargar las estaciones"),
                icon: "error",
            });
        }
    };

    const handleAction = async (action: string, item: Station) => {
        if (action === "select") {
            setCurrentMode(2);
            setSelectedStation(item);
        } else if (action === "delete") {
            if (!item.station_id) {
                return;
            }
            try{
                const deletedStation = await stationService.deleteStation(item.station_id)
                if (deletedStation){
                    Swal.fire({
                        toast: true,
                        position: "top-end",
                        icon: "success",
                        title: "Zona eliminada",
                        text: `Se ha eliminado la estación ${item.station_id}`,
                        timer: 3000
                    })

                    await fetchData();
                    setSelectedStation(null);
                    setCurrentMode(1);

                }
                else {
                    Swal.fire({
                        title: "Error",
                        text: "La estación no se ha podido eliminar",
                        icon: "error",
                        timer: 3000
                    })
                }
            }
            catch (error) {
                Swal.fire({
                    title: "Error",
                    text: getApiErrorMessage(error, "No se pudo eliminar la estación"),
                    icon: "error",
                    timer: 3000
                })
            }

        }
    };

    const handleStationForm = async (station: Station) => {

        if (currentMode === 1){
            try{
                const createdStation = await stationService.createStation(station);
                if (createdStation){
                    Swal.fire({
                        toast: true,
                        position: "top-end",
                        icon: "success",
                        title: "Zona creada",
                        text: `Se ha creado la estación ${station.station_id}`,
                        timer: 3000
                    })

                    await fetchData();
                    setSelectedStation(createdStation);
                    setCurrentMode(2);

                }
                else {
                    Swal.fire({
                        title: "Error",
                        text: "La estación no se ha podido crear",
                        icon: "error",
                        timer: 3000
                    })
                }
            }
            catch (error) {
                Swal.fire({
                    title: "Error",
                    text: getApiErrorMessage(error, "No se pudo crear la estación"),
                    icon: "error",
                    timer: 3000
                })
            }

        }

        else if (currentMode === 2){
            if (!selectedStation?.station_id) {
                return;
            }
            try{
                const updatedStation = await stationService.updateStation(selectedStation.station_id,station)
                if (updatedStation){
                    Swal.fire({
                        toast: true,
                        position: "top-end",
                        icon: "success",
                        title: "Estación actualizada",
                        text: `Se ha actualizado la estación ${station.station_id}`,
                        timer: 3000
                    })

                    await fetchData();
                    setSelectedStation(updatedStation);

                }
                else {
                    Swal.fire({
                        title: "Error",
                        text: "La estación no se ha podido actualizar",
                        icon: "error",
                        timer: 3000
                    })
                }
            }
            catch (error) {
                Swal.fire({
                    title: "Error",
                    text: getApiErrorMessage(error, "No se pudo actualizar la estación"),
                    icon: "error",
                    timer: 3000
                })
            }

        }
    };

    function handleDeselect(){
        setCurrentMode(1);
        setSelectedStation(null);
    }

    return (
        <div className="w-full space-y-6">

            {/* Arriba: Form 30% + Tabla 70% */}
            <div className="grid grid-cols-[30%_70%] gap-6">

                <div>
                    <StationFormValidator
                        station={selectedStation ? selectedStation : null}
                        mode={currentMode}
                        handleAction={handleStationForm}
                    />
                    {selectedStation && (
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
                        data={stations}
                        columnLabels={{station_id: "estación"}}
                        columns={["station_id", "x", "y"]}
                        actions={[
                            { name: "select", label: "Seleccionar" },
                            { name: "delete", label: "Borrar" },
                        ]}
                        onAction={handleAction}
                    />
                </div>

            </div>

            <div className="w-full h-[50vh]">
                <CartesianPlane stations={stations} selectedStation={selectedStation} />
            </div>

        </div>
    );
};

export default StationsDashboard;


