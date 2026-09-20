from domain.event import Event
from enum import Enum
from datetime import datetime, timezone
from typing import Optional

# El siguiente enum se usa para definir el modo del escenario
#Como en teoria se inicializa en modo normal pues aja por eso esta aqui metido
class Mode(Enum):
    NORMAL = "Normal"
    STRESS = "Stress"

class scenario:

    def __init__(self, eliminated_IDs: Optional[set[int]] = None, archived_history: Optional[dict[int, Event]] = None, simulationClock: Optional[datetime] = None,  L: int=3, W: float = 48.0, R: float = 40.0, T: float = 72.0, Mode: Mode = Mode.Normal):

        #Colecciones de eliminación e histórico
        self.eliminated_IDs: set[int] = eliminated_IDs
        self.archived_history: dict[int, Event]= archived_history

        #Reloj de Simulación precisión en segundos, Si no se provee uno, toma la hora UTC actual del sistema
        self.simulationClock: datetime = ( simulationClock or datetime.now(timezone.utc).replace(microsecond=0) )

        #Parámetros globales configurables
        self.L= L #Limite inicialmente 3

        self.W= W
        self.R= R
        self.T= T

        #







