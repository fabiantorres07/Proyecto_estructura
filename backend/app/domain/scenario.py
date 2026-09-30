from app.domain.event import Event
from enum import Enum
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Optional
from app.domain.zone import Zone
from app.domain.station import Station
from app.domain.report import Report
from app.domain.mode import Mode
from app.structures.avl_node import AVLNode
from app.structures.stack import Stack
from app.structures.queue import Queue 


class Scenario:

    def __init__(self, metrics : Optional[dict[str, int]] = None, event_index : Optional[dict[int, AVLNode]] = None, stations : Optional[dict[str, Station]] = None, zones: Optional[list[Zone]] = None, eliminated_IDs: Optional[set[int]] = None, archived_history: Optional[dict[int, Event]] = None, simulation_clock: Optional[datetime] = None,  L: int=3, W: float = 48.0, R: float = 40.0, T: float = 72.0, mode: Mode = Mode.NORMAL, undo_stack: Optional[Stack] = None, report_queue: Optional[Queue] = None):

        #Colecciones de eliminación e histórico
        self.eliminated_IDs = eliminated_IDs if eliminated_IDs is not None else set()
        self.archived_history = archived_history if archived_history is not None else dict()

        #Reloj de Simulación precisión en segundos, Si no se provee uno, toma la hora UTC actual del sistema
        self._simulation_clock: datetime = simulation_clock or datetime.now(timezone.utc).replace(microsecond=0)
        # Store a fixed baseline and measure elapsed time monotonically so wall-clock adjustments do not stop or reverse the simulation clock.
        self._clock_anchor_monotonic = monotonic()

        #Parámetros globales configurables
        self.L= L #Limite inicialmente 3

        self.W= W
        self.R= R
        self.T= T

        self.mode = mode 
        self.zones = zones if zones is not None else list()
        self.stations = stations if stations is not None else dict()
        self.event_index = event_index if event_index is not None else dict()
        self.metrics = metrics if metrics is not None else dict()
        self.undo_stack = undo_stack if undo_stack is not None else Stack()
        self.report_queue = report_queue if report_queue is not None else Queue()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Event and report timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    """==============================================="""
    """=================MODE METHODS=================="""
    """==============================================="""

    def set_mode(self, mode):
        if not isinstance(mode, Mode):
            raise ValueError("Mode must either be Stress or Normal")

        self.mode = mode
        return self.mode
    
    def get_mode(self):
        return self.mode


    """==============================================="""
    """=================CLOCK METHODS================="""
    """==============================================="""
    @property
    def simulation_clock(self) -> datetime:
        elapsed_seconds = monotonic() - self._clock_anchor_monotonic
        return self._simulation_clock + timedelta(seconds=elapsed_seconds)

    @simulation_clock.setter
    def simulation_clock(self, value: datetime) -> None:
        self._simulation_clock = value
        self._clock_anchor_monotonic = monotonic()

    def update_simulation_clock(self, new_clock: datetime) -> datetime:
        new_clock = self._as_utc(new_clock)

        for node in self.event_index.values():
            if self._as_utc(node.event.occurred_at) > new_clock:
                raise ValueError(
                    f"Cannot set the clock before event {node.event.event_id}"
                )

        for event in self.archived_history.values():
            if self._as_utc(event.occurred_at) > new_clock:
                raise ValueError(
                    f"Cannot set the clock before event {event.event_id}"
                )

        for report in self.report_queue.items():
            if self._as_utc(report.occurred_at) > new_clock:
                raise ValueError(
                    f"Cannot set the clock before report {report.event_id}"
                )

        self.simulation_clock = new_clock
        return self.simulation_clock

    """==============================================="""
    """================ZONE METHODS==================="""
    """==============================================="""

    def add_zone(self, zone: Zone):
        """This method is called to add a zone to the scenario. It checks if there is another existing zone with the same name, and if there isn't, then the new zone is added"""

        if any(existing.name == zone.name for existing in self.zones):
            raise ValueError("A zone with this name already exist")
        
        self.zones.append(zone)
        return zone

    def get_zone(self, zone_name: str) -> Zone:
        """This method returns the zone with the name that is being searched"""
        for zone in self.zones:
            if zone.name == zone_name:
                return zone

        raise KeyError(f"Zone '{zone_name}' was not found")

    def list_zones(self) -> list[Zone]:
        """This method returns the list of zones of the scenario"""
        return self.zones

    def update_zone(self, zone_name: str, changes: dict) -> Zone:
        """This method is called to update the data of a zone that already exists"""
        current_zone = self.get_zone(zone_name)
        #Either we put the new values, or if there isn't a new value, the old one remains
        updated_values = {
            "name": changes.get("name", current_zone.name),
            "x_min": changes.get("x_min", current_zone.x_min),
            "x_max": changes.get("x_max", current_zone.x_max),
            "y_min": changes.get("y_min", current_zone.y_min),
            "y_max": changes.get("y_max", current_zone.y_max),
            "is_populated": changes.get("is_populated", current_zone.is_populated),
        }

        if updated_values["name"] != zone_name and any(
            zone.name == updated_values["name"] for zone in self.zones
        ):
            raise ValueError("A zone with this name already exists")

        #The old instance gets replaced with the new one in the same index that the old one used to be

        updated_zone = Zone(**updated_values)
        zone_index = self.zones.index(current_zone)
        self.zones[zone_index] = updated_zone
        return updated_zone

    def delete_zone(self, zone_name: str) -> None:
        """This method deletes a zone"""
        zone = self.get_zone(zone_name)
        self.zones.remove(zone)

    """==============================================="""
    """================STATION METHODS================"""
    """==============================================="""

    def add_station(self, station: Station) -> Station:
        """Add a station, using its ID as the dictionary key."""
        if station.station_id in self.stations:
            raise ValueError("A station with this ID already exists")

        self.stations[station.station_id] = station
        return station

    def get_station(self, station_id: str) -> Station:
        """This method returns the station with the id that is being searched"""
        try:
            return self.stations[station_id]
        except KeyError:
            raise KeyError(f"Station '{station_id}' was not found") from None

    def list_stations(self) -> list[Station]:
        """This method returns the list of stations of the scenario"""
        return list(self.stations.values())

    def update_station(self, station_id: str, changes: dict) -> Station:
        """This method is called to update the data of a zone that already exists"""
        current_station = self.get_station(station_id)
        #Either we put the new values, or if there isn't a new value, the old one remains
        updated_values = {
            "station_id": changes.get("station_id", current_station.station_id),
            "x": changes.get("x", current_station.x),
            "y": changes.get("y", current_station.y),
        }

        if updated_values["station_id"] != station_id and any(
            existing_id == updated_values["station_id"] for existing_id in self.stations
        ):
            raise ValueError("A station with this id already exists")
        
        #The old instance gets replaced with the new one in the same index that the old one used to be

        updated_station = Station(**updated_values)
        if updated_station.station_id != station_id:
            del self.stations[station_id]
        self.stations[updated_station.station_id] = updated_station
        return updated_station

    def delete_station(self, station_id: str) -> None:
        """This method deletes a zone"""
        self.get_station(station_id)
        del self.stations[station_id]

    """==============================================="""
    """================REPORT METHODS================="""
    """==============================================="""

    # La cola solo guarda reportes PREPARADOS: encolar no toca eventos ni
    # árboles. La decisión de cada reporte (tabla de la sección 6) se toma
    # al procesarlo, en process_next_report(), que aún no existe porque
    # depende de la creación/corrección de eventos.
    #
    # Decisiones del equipo (29-sep):
    # - Los reportes con fecha posterior al reloj se rechazan AL ENCOLAR.
    # - Un reporte encolado no se puede quitar individualmente; solo se
    #   puede vaciar la cola completa.

    def _validate_report(self, report: Report) -> None:
        """Validaciones de un reporte que dependen del estado del escenario.
        Los rangos y formatos ya los validó el schema (ReportCreate).
        Lanza KeyError si la estación no está registrada y ValueError si la
        fecha de ocurrencia es posterior al reloj de simulación."""
        station_id = report.station.station_id
        if self.stations.get(station_id) is not report.station:
            raise KeyError(f"Station '{station_id}' was not found")

        if self._as_utc(report.occurred_at) > self.simulation_clock:
            raise ValueError(
                f"Report for event {report.event_id} occurred after the "
                f"simulation clock ({self.simulation_clock.replace(microsecond=0).isoformat()})"
            )

    def enqueue_report(self, report: Report) -> int:
        """Agrega un reporte al final de la cola FIFO y devuelve su posición
        (1 = el próximo en procesarse). Si no es válido, lanza la excepción
        de _validate_report y la cola no cambia. O(1)."""
        self._validate_report(report)
        self.report_queue.enqueue(report)
        return len(self.report_queue)

    def enqueue_reports(self, reports: list[Report]) -> int:
        """Encola una ráfaga de reportes en el orden recibido, de forma
        atómica: primero valida TODOS y solo si todos son válidos los
        encola. Así un error en el reporte 5 no deja encolados los 4
        primeros. Devuelve la posición del primero de la ráfaga. O(N)."""
        for report in reports:
            self._validate_report(report)

        first_position = len(self.report_queue) + 1
        for report in reports:
            self.report_queue.enqueue(report)
        return first_position

    def list_reports(self) -> list[Report]:
        """Copia de la cola en orden de recepción (el primero es el próximo
        que se procesará). Es una copia: modificar la lista no altera la
        cola. O(n)."""
        return self.report_queue.items()

    def clear_report_queue(self) -> int:
        """Descarta todos los reportes pendientes y devuelve cuántos había.
        No toca eventos, árboles ni reloj.

        PENDIENTE (decisión del equipo): por ahora NO se registra en la pila
        de deshacer. El enunciado no lista "vaciar la cola" entre las
        acciones de la sección 13, pero la cola sí forma parte del estado
        recuperable."""
        return self.report_queue.clear()
