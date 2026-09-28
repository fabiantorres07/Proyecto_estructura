import { useEffect, useState } from "react";
import Swal from "sweetalert2";
import CartesianPlane from "../../components/map/Plane";
import { Station } from "../../models/Station";
import { Zone } from "../../models/Zone";
import { stationService } from "../../services/stationService";
import { zoneService } from "../../services/zoneService";

const AppMap = () => {
  const [stations, setStations] = useState<Station[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);

  useEffect(() => {
    const fetchMapData = async () => {
      try {
        const [loadedStations, loadedZones] = await Promise.all([
          stationService.getStations(),
          zoneService.getZones(),
        ]);
        setStations(loadedStations);
        setZones(loadedZones);
      } catch (error) {
        Swal.fire({
          title: "Error",
          text: error instanceof Error ? error.message : "No se pudieron cargar los datos del mapa",
          icon: "error",
        });
      }
    };

    void fetchMapData();
  }, []);

  return (
    <div className="min-h-screen w-full">
      <h2>Mapa de sismos</h2>

      <div className="h-[80vh] w-full">
        <CartesianPlane stations={stations} zones={zones} />
      </div>
    </div>
  );
};

export default AppMap;