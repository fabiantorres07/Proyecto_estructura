from enum import Enum
from app.domain.station import Station

class Event:

    """CLASE EVENT"""
    """Representa un terremoto: sus datos físicos y nada más.
    Los datos: id, magnitud, profundidad, epicentro (x, y), fecha y hora.
    La revisión vigente y las estaciones que han reportado.
    Si está en zona poblada. Event no conoce las zonas, así que quien lo crea (Scenario) le dice el valor.
    El estado de atención. Siempre empieza en pendiente."""

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

        #SE NECESITA PARA CALCULAR EN SCENARIO LAS ASOCIACIONES (es un atributo de estado del sistema, solo se pone aqui)
        self.reference_id = None

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

    def apply_correction(self, magnitude=None, depth=None, x=None, y=None,
                        occurred_at=None, revision=None, is_in_populated_zone=None):
        """Aplica una corrección sobre el evento.

        - Cambia los campos que llegan (los que quedan en None no se tocan).
        - `occurred_at` NO está en la clave K = (P, M, I), pero SÍ afecta
        las asociaciones (sección 7): W horas, orden temporal de las
        referencias. Un cambio de fecha puede mover qué eventos son
        candidatos entre sí sin cambiar la clave.
        - `revision`: si llega, se usa ese valor (corrección desde un
        reporte, sección 6: "sustituir los datos vigentes" con la
        revisión del reporte). Si no llega, se incrementa en 1
        (corrección manual, sección 6: "r + 1").
        - Devuelve (old_key, new_key) para que Scenario sepa si hay que
        reubicar en los árboles.
        """
        if x is not None or y is not None:
            if is_in_populated_zone is None:
                raise Exception("Cambio de epicentro requiere recalcular zona poblada")

        new_magnitude = magnitude if magnitude is not None else self.magnitude
        new_depth = depth if depth is not None else self.depth
        new_x = x if x is not None else self.x
        new_y = y if y is not None else self.y
        new_occurred_at = occurred_at if occurred_at is not None else self.occurred_at
        new_populated_zone = (is_in_populated_zone if is_in_populated_zone is not None
                            else self.is_in_populated_zone)

        old_key = self.key

        self.magnitude = new_magnitude
        self.depth = new_depth
        self.x = new_x
        self.y = new_y
        self.occurred_at = new_occurred_at
        self.is_in_populated_zone = new_populated_zone

        if revision is not None:
            self.revision = revision
        else:
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
