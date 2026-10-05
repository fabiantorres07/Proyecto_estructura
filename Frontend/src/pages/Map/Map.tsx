import { useEffect, useState } from "react";
import Swal from "sweetalert2";
import CartesianPlane from "../../components/map/Plane";
import { Station } from "../../models/Station";
import { Zone } from "../../models/Zone";
import { EventMapPoint } from "../../models/Event/EventMapPoint";
import { stationService } from "../../services/stationService";
import { zoneService } from "../../services/zoneService";
import { eventService } from "../../services/eventService";

const AppMap = () => {
  const [stations, setStations] = useState<Station[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [events, setEvents] = useState<EventMapPoint[]>([]);

  useEffect(() => {
    const fetchMapData = async () => {
      try {
        const [loadedStations, loadedZones, loadedEvents] = await Promise.all([
          stationService.getStations(),
          zoneService.getZones(),
          eventService.getActiveEvents(),
        ]);
        setStations(loadedStations);
        setZones(loadedZones);
        setEvents(loadedEvents.map(({ event_id, x, y }) => ({ event_id, x, y })));
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
        <CartesianPlane stations={stations} zones={zones} events={events} />
      </div>
    </div>
  );
};

export default AppMap;