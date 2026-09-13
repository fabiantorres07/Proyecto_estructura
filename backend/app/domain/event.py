from datetime import datetime
from enum import Enum
from app.domain.station import Station

class Event:

    def __init__(self, event_id, magnitude, depth, x, y, occurred_at,  revision, stations : set["Station"], is_in_populated_zone):

        self.event_id = event_id
        self.magnitude = magnitude
        self.depth = depth

        # Con estos datos se representa el epicentro
        self.x = x
        self.y = y

        self.occurred_at = occurred_at

        # Revision vigente
        self.revision = revision

        # Estaciones con reportes acpetados
        self.stations = stations

        self.attention_status = AttentionStatus.PENDING

        self.is_in_populated_zone = is_in_populated_zone

    @property
    def priority(self):
        m = self.magnitude
        h = self.depth
        populated_zone = self.is_in_populated_zone

        if m >= 6.0:
            return 3

        elif m >= 4.5 and h <= 30.0 and populated_zone:
            return 3

        elif m >= 4.5:
            return 2
        else:
            return 1

    @property
    def key(self):
        return (self.priority, self.magnitude, self.event_id)

# El siguiente enum se usa para definir el estado de atencion del evento
class AttentionStatus(Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
