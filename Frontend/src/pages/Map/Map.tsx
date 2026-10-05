import { useEffect, useState } from "react";
import Swal from "sweetalert2";
import CartesianPlane from "../../components/map/Plane";
import { Station } from "../../models/Station";
import { Zone } from "../../models/Zone";
import { EventMapPoint } from "../../models/Event/EventMapPoint";
import { stationService } from "../../services/stationService";
import { zoneService } from "../../services/zoneService";
import { eventService } from "../../services/eventService";
import { SCENARIO_STATE_CHANGED_EVENT } from "../../services/undoService";

const AppMap = () => {
  const [stations, setStations] = useState<Station[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [events, setEvents] = useState<EventMapPoint[]>([]);

  useEffect(() => {
    let active = true;
    const fetchMapData = async () => {
      try {
        const [loadedStations, loadedZones, loadedEvents] = await Promise.all([
          stationService.getStations(),
          zoneService.getZones(),
          eventService.getActiveEvents(),
        ]);
        if (!active) return;
        setStations(loadedStations);
        setZones(loadedZones);
        setEvents(loadedEvents.map(({ event_id, x, y }) => ({ event_id, x, y })));
      } catch (error) {
        if (!active) return;
        Swal.fire({
          title: "Error",
          text: error instanceof Error ? error.message : "No se pudieron cargar los datos del mapa",
          icon: "error",
        });
      }
    };

    const refreshMapData = () => void fetchMapData();
    void fetchMapData();
    window.addEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshMapData);
    return () => {
      active = false;
      window.removeEventListener(SCENARIO_STATE_CHANGED_EVENT, refreshMapData);
    };
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