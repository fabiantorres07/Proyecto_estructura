from app.domain.event import Event
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from app.domain.zone import Zone
from app.domain.station import Station
from app.structures.avl_node import AVLNode
from app.structures.stack import Stack
from app.structures.queue import Queue 

# El siguiente enum se usa para definir el modo del escenario
#Como en teoria se inicializa en modo normal pues aja por eso esta aqui metido
class Mode(Enum):
    NORMAL = "Normal"
    STRESS = "Stress"

class Scenario:

    def __init__(self, metrics : Optional[dict[str, int]] = None, event_index : Optional[dict[int, AVLNode]] = None, stations : Optional[dict[int, Station]] = None, zones: Optional[list[Zone]] = None, eliminated_IDs: Optional[set[int]] = None, archived_history: Optional[dict[int, Event]] = None, simulation_clock: Optional[datetime] = None,  L: int=3, W: float = 48.0, R: float = 40.0, T: float = 72.0, mode: Mode = Mode.NORMAL, undo_stack: Optional[Stack] = None, report_queue: Optional[Queue] = None):

        #Colecciones de eliminación e histórico
        self.eliminated_IDs = eliminated_IDs if eliminated_IDs is not None else set()
        self.archived_history = archived_history if archived_history is not None else dict()

        #Reloj de Simulación precisión en segundos, Si no se provee uno, toma la hora UTC actual del sistema
        self.simulation_clock: datetime = simulation_clock or datetime.now(timezone.utc).replace(microsecond=0)

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

        updated_zone = Zone(**updated_values)
        zone_index = self.zones.index(current_zone)
        self.zones[zone_index] = updated_zone
        return updated_zone

    def delete_zone(self, zone_name: str) -> None:
        """This method deletes a zone"""
        zone = self.get_zone(zone_name)
        self.zones.remove(zone)






