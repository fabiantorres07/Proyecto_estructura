from app.domain.event import Event
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from app.domain.zone import Zone
from app.domain.station import Station
from app.structures.avl_node import AVLNode

# El siguiente enum se usa para definir el modo del escenario
#Como en teoria se inicializa en modo normal pues aja por eso esta aqui metido
class Mode(Enum):
    NORMAL = "Normal"
    STRESS = "Stress"

class Scenario:

    def __init__(self, metrics : Optional[dict[str, int]] = None, event_index : Optional[dict[int, AVLNode]] = None, stations : Optional[dict[int, Station]] = None, zones: Optional[list[Zone]] = None, eliminated_IDs: Optional[set[int]] = None, archived_history: Optional[dict[int, Event]] = None, simulation_clock: Optional[datetime] = None,  L: int=3, W: float = 48.0, R: float = 40.0, T: float = 72.0, mode: Mode = Mode.NORMAL):

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






