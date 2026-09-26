from enum import Enum
from app.domain.station import Station

class Event:

    def __init__(self,event_id, magnitude, depth, x, y, occurred_at,  revision, stations : set["Station"], is_in_populated_zone):

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

    def apply_correction(self, magnitude = None, depth = None, x = None, y = None, is_in_populated_zone = None):
        if x is not None or y is not None:
            if is_in_populated_zone is not None:
                new_populated_zone = is_in_populated_zone
            else:
                raise Exception("Cambio de epicentro requiere recalcular zona poblada")
        if magnitude is not None:
            new_magnitude = magnitude
        else:
            new_magnitude = self.magnitude

        if depth is not None:
            new_depth = depth
        else:
            new_depth = self.depth

        if x is not None:
            new_x = x
        else:
            new_x = self.x

        if y is not None:
            new_y = y
        else:
            new_y = self.y

        if is_in_populated_zone is None:
            new_populated_zone = self.is_in_populated_zone
        else:
            new_populated_zone = is_in_populated_zone

        old_key = self.key

        self.magnitude = new_magnitude
        self.depth = new_depth
        self.x = new_x
        self.y = new_y
        self.is_in_populated_zone = new_populated_zone
        self.revision += 1
        self.attention_status = AttentionStatus.PENDING
        new_key = self.key

        return old_key, new_key
    
    def mark_as_reviwed(self):
        self.attention_status = AttentionStatus.REVIEWED

# El siguiente enum se usa para definir el estado de atencion del evento
class AttentionStatus(Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
