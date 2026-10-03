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
from app.domain.action import CreationAction, CorrectionAction, AttentionChangeAction, DeletionAction,ParameterChangeAction, ClockAdvanceAction, QueueStepAction
from app.structures.avl_tree import AVLTree
from app.structures.avl_node import AVLNode
from app.structures.bst_node import BSTNode
from app.structures.bst_tree import BSTTree



class Scenario:

    def __init__(self, metrics : Optional[dict[str, int]] = None,avl_tree: Optional[AVLTree] = None, bst_tree: Optional[BSTTree] = None, 
                 event_index : Optional[dict[int, AVLNode]] = None, stations : Optional[dict[int, Station]] = None, zones: Optional[list[Zone]] = None, 
                 eliminated_IDs: Optional[set[int]] = None, archived_history: Optional[dict[int, Event]] = None, referenced_by=None, simulation_clock: Optional[datetime] = None, 
                L: int=3, W: float = 48.0, R: float = 40.0, T: float = 72.0, mode: Mode = Mode.NORMAL, undo_stack: Optional[Stack] = None, report_queue: Optional[Queue] = None):

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

        self.avl_tree = avl_tree if avl_tree is not None else AVLTree(metrics=self.metrics) #AVLTree necesita recibir self.metrics ya creado (para compartir el mismo diccionario)
        self.bst_tree = bst_tree if bst_tree is not None else BSTTree()

        self.undo_stack = undo_stack if undo_stack is not None else Stack()
        self.report_queue = report_queue if report_queue is not None else Queue()

        self.referenced_by = referenced_by if referenced_by is not None else dict()

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

        # No se puede retroceder el reloj.
        if new_clock < self.simulation_clock:
            raise ValueError("Cannot move the simulation clock backwards")

        if new_clock == self.simulation_clock: #para no apilar una acción que no cambió nada
            return self.simulation_clock
        
        # Validaciones existentes: ningún evento, archivado ni reporte
        # puede quedar con fecha posterior al nuevo reloj.
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

        # Guardar el reloj simulado actual (con el tiempo real transcurrido
        # incluido) antes de cambiarlo, para poder volver exactamente a este
        # instante al deshacer.
        old_clock = self.simulation_clock

        # Aplicar el nuevo reloj.
        self.simulation_clock = new_clock

        # Apilar la acción con el valor viejo.
        self.undo_stack.push(ClockAdvanceAction(old_clock))

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









































































    
    """EVENT STF"""

    def create_event(self, event_id: int, magnitude: float, depth: float, x: float, y: float,
                    occurred_at, stations: set, revision: int = 1) -> Event:
        """Operación que dispara la interfaz cuando el usuario hace clic en
        'crear evento'. Construye el evento desde cero.

        El parámetro `revision` tiene default 1, que es el caso del alta
        manual (sección 6: "asignar la revisión 1"). Se usa otro valor
        cuando el evento se crea a partir de un reporte procesado, porque
        la sección 6 dice: "la primera revisión recibida puede ser mayor
        que 1".

        Un evento A es candidato a referencia de B cuando tiene mayor magnitud, ocurrió estrictamente antes...
        A = el evento que va a ser referencia (el candidato).
        B = el evento que está siendo referenciado (el que "necesita" una referencia)."""

        if self._id_exists(event_id):
            raise ValueError(f"El identificador {event_id} ya existe")

        is_populated = self.epicenter_in_populated_zone(x, y)

        # Aquí nace el evento nuevo (lo llamamos B).
        event = Event(
            event_id=event_id, magnitude=magnitude, depth=depth,
            x=x, y=y, occurred_at=occurred_at, revision=revision,
            stations=stations, is_in_populated_zone=is_populated,
        )

        balance = (self.mode == Mode.NORMAL)

        node = self.avl_tree.insert(event, balance=balance)
        self.bst_tree.insert(event)
        self.event_index[event_id] = node

        """Buscar eventos ya existentes que ahora podrían tener a B como
        # candidato nuevo (sección 7). Un evento X solo puede tener a B como
        # candidato si B ocurrió ANTES que X y tiene MAYOR magnitud que X.
        # Esto pasa con reportes tardíos: B es nuevo en el sistema pero su
        # fecha de ocurrencia es anterior a la de eventos ya registrados."""
        affected_others = [other for other in self._all_active_and_archived_events()
            if other.event_id != event_id
            and other.occurred_at > event.occurred_at
            and other.magnitude < event.magnitude
        ]

        # Guardar la foto de las referencias ANTES de recalcular, para poder
        # deshacer. B entra con None porque antes no existía. Cada otro evento
        # afectado guarda su reference_id actual (el que va a cambiar).
        old_references = {event_id: None}
        for other in affected_others:
            old_references[other.event_id] = other.reference_id

        # Recalcular la referencia de B (busca sus candidatos entre los eventos
        # viejos) y la de cada evento afectado (ahora B aparece como candidato).
        self._recalculate_reference(event)
        for other in affected_others:
            self._recalculate_reference(other)

        # Apilar la acción con el id de B y la foto de referencias viejas, para
        # que undo() pueda restaurar todo lo que esta creación cambió.
        self.undo_stack.push(CreationAction(event_id, old_references))

        return event

    def get_event(self, event_id: int) -> dict:
        """Metodo para buscar un evento por el id, retorna todo el obj event si es activo, y el id con su estado (eliminado o archivado)
        si esta eliminado o archivado (archivado podria retornar el objeto completo pero por ser consistente con eliminado solo retorna el id)"""
        # Activo
        if event_id in self.event_index:
            node = self.event_index[event_id]
            event = node.event
            return {
                "status": "active",
                "event_id": event_id,
                "event": event,
                "revision": event.revision,
                "stations": event.stations,
                "is_in_populated_zone": event.is_in_populated_zone,
                "priority": event.priority,
                "key": event.key,
                "attention_status": event.attention_status,
                "depth": self.avl_tree.depth_of(node),
                "height": node.height,
                "balance_factor": node.balance_factor,
                "associations": self._build_associations(event_id),
            }
        # Archivado
        if event_id in self.archived_history:
            return {
                "status": "archived",
                "event_id": event_id,
                "event": None,
            }

        # Eliminado
        if event_id in self.eliminated_IDs:
            return {
                "status": "eliminated",
                "event_id": event_id,
                "event": None,
            }

        raise KeyError(f"No existe un evento con id {event_id}")

    """---AUXILIARES DE EVENTOS"""

    def epicenter_in_populated_zone(self, x: float, y: float) -> bool:
        """AUXILIAR: Metodo para saber si un epicentro esta en zona poblada (Un epicentro pertenece a una zona si está dentro o sobre el borde ya se cubre en zone)
        este metodo es el que se pasa al atributo de event: is_in_populated_zone
        """
        for zone in self.zones:
            if zone.contains(x, y) and zone.is_populated:
                return True
        return False

    def _id_exists(self, event_id: int) -> bool:
        """AUXILIAR: Un id existe si esta en alguno de estos 3: self.event_index,  self.archived_history, self.eliminated_IDs"""
        return (
            event_id in self.event_index
            or event_id in self.archived_history
            or event_id in self.eliminated_IDs
        )
    def _find_any_event(self, event_id: int) -> Event:
        """AUXILIAR: Busca un evento activo o archivado por id (no eliminados por que para el sistema no tiene sentido buscar eliminados y por que solo se retornan ids)"""

        if event_id in self.event_index:
            return self.event_index[event_id].event
        
        if event_id in self.archived_history:
            return self.archived_history[event_id]
        raise KeyError(f"No existe un evento activo o archivado con id {event_id}")

    def _all_active_and_archived_events(self) -> list[Event]:
        """AUX: Devuelve todos los eventos activos (recorrido inorden del AVL por que me dio la gana y pq devuelve ya el evento)
        seguidos de todos los archivados. No incluye eliminados."""

        events = list(self.avl_tree.inorder())
        events.extend(self.archived_history.values())
        return events


    def _event_status(self, event_id: int) -> Optional[str]:
        """Devuelve 'active', 'archived' o None si el id no está en ninguno.

        Se usa para etiquetar la referencia y los candidatos en el bloque de
        asociaciones de get_event (la sección 7 pide identificar si cada
        resultado está activo o archivado)."""

        if event_id in self.event_index:
            return "active"
        
        if event_id in self.archived_history:
            return "archived"
        
        return None
    
    """ASOCIACIONES"""
    
    """Los siguientes metodos corresponden a metodos auxiliares para calcular y retornar las asociaciones de un evento y poder mostrarlas cuando se haga get_event"""

    """Una asociación entre eventos tiene dos partes:

        La referencia elegida → "B tiene a A como posible réplica". Se guarda (Event.reference_id).

        Los candidatos → "estos son todos los A que podrían ser referencia de B". 
        Se calculan al vuelo (get_candidates)."""
    
    def get_candidates(self, event_id: int) -> list[Event]:
        """Candidatos a referencia del evento `event_id`: eventos activos o
        archivados con mayor magnitud, ocurridos estrictamente antes, dentro de
        W horas y R km. Ordenados por criterio determinista."""

        event = self._find_any_event(event_id)
        candidates = []

        for other in self._all_active_and_archived_events():
            if other.event_id == event.event_id:
                continue

            if other.magnitude <= event.magnitude:
                continue

            if other.occurred_at >= event.occurred_at:
                continue

            #vuelve el datatime a horas y hace la diferencia entre ambos para poder saber si se pasa de la hora o no
            horas = (event.occurred_at - other.occurred_at).total_seconds() / 3600
            if horas > self.W:
                continue

            #calcula la distancia entre epicentros con euclides
            distancia = ((event.x - other.x) ** 2 + (event.y - other.y) ** 2) ** 0.5
            if distancia > self.R:
                continue

            candidates.append(other)

        candidates.sort(key=lambda other: ((event.occurred_at - other.occurred_at).total_seconds() / 3600, ((event.x - other.x) ** 2 + (event.y - other.y) ** 2) ** 0.5, 
            -other.magnitude,other.event_id,) #esto se puede cambiar pero pueeees ni q necesitaramos tanta eficiencia
        )
        return candidates
    
    """PARA LAS REFERENCIAS:"""
    def get_reference(self, event_id: int) -> Optional[Event]:
        """Devuelve el evento que es referencia del evento `event_id`
        (puede estar activo o archivado), o None si no tiene referencia."""

        event = self._find_any_event(event_id)

        if event.reference_id is None:
            return None
        
        return self._find_any_event(event.reference_id)

    """INDICE INVERSO PARA REFERENCIAS Y ASOCIACIONES

Es un diccionario en Scenario que va al revés de la referencia normal.

Referencia normal (Event.reference_id):

B (id 5) → A (id 3)
Se lee: "el evento 5 tiene como referencia al evento 3".

Índice inverso (Scenario.referenced_by):

{3: {5, 8}}
Se lee: "el evento 3 es referencia de los eventos 5 y 8".

Es la misma información, pero al revés.


Porque hay operaciones que necesitan responder: "¿quiénes me tienen como referencia?"

Cuando eliminas el evento 3, tienes que encontrar rápido a todos los que dependían de él (5 y 8) para recalcularles la referencia. Dos opciones:

Sin índice inverso: recorres todos los eventos activos y archivados, y para cada uno preguntas "¿tu referencia es 3?". Costo O(n) cada vez.

Con índice inverso: haces self.referenced_by.get(3) y obtienes {5, 8} directo. Costo O(1). """

        
    def _assign_reference(self, event: Event, new_reference_id: Optional[int]) -> None:
            """AUXILIAR: Este es el que mantiene sincronizado Event.reference_id con referenced_by. 
            Cada vez que la referencia de un evento cambia, este helper hace los dos cambios juntos."""
            old_ref = event.reference_id

            # If the event already had a reference, remove it from the inverse index.
            if old_ref is not None:
                self.referenced_by[old_ref].discard(event.event_id)
                if not self.referenced_by[old_ref]:
                    del self.referenced_by[old_ref]

            # Apply the new reference on the event itself.
            event.reference_id = new_reference_id

            # If there is a new reference, add this event to its inverse index entry.
            if new_reference_id is not None:
                self.referenced_by.setdefault(new_reference_id, set()).add(event.event_id)

    def _recalculate_reference(self, event: Event) -> None:
        """AUXILIAR: Recalculate the reference of `event` from its current candidates.
        Picks the first candidate (already sorted) or None if there is none,
        and applies it through _assign_reference so the inverse index stays
        in sync. SOLO MODIFICA 
        No devuelve nada, solo modifica.
        candidates[0] es la mejor opción porque get_candidates ya ordenó.
        Si la lista está vacía → None. Esto cubre el caso de "el candidato anterior ya no existe" (porque se eliminó, por ejemplo).
        Usa _assign_reference para no desincronizar referenced_by."""

        candidates = self.get_candidates(event.event_id)
        new_ref_id = candidates[0].event_id if candidates else None
        self._assign_reference(event, new_ref_id)


    def _build_associations(self, event_id: int) -> dict:
        """Arma el bloque de asociaciones para get_event.

        Devuelve un dict con:
        - 'reference': el evento elegido como referencia (con su estado),
            o None si no tiene.
        - 'candidates': lista de candidatos (con su estado), sin incluir
            la referencia para no duplicarla.

        La referencia siempre es el primer candidato que devuelve
        get_candidates (ya viene ordenado por el criterio), así
        que aquí se filtra de la lista de candidatos."""

        reference = self.get_reference(event_id)
        reference_id = reference.event_id if reference is not None else None

        # Bloque de referencia: None cuando el evento no tiene referencia.
        reference_data = None

        if reference is not None:

            reference_data = {"event": reference,"status": self._event_status(reference_id),
            }

        # Bloque de candidatos: se salta la referencia para que no salga dos veces.
        candidates_data = [
            {"event": candidate, "status": self._event_status(candidate.event_id)}

            for candidate in self.get_candidates(event_id)

            if candidate.event_id != reference_id
        ]

        return {
            "reference": reference_data,
            "candidates": candidates_data,
        }
        
    def correct_event(self, event_id: int, changes: dict) -> Event:
        """Corrección manual de un evento activo (PUT /events/{id}).

        `changes` es un dict con los campos que se quieren tocar: magnitude,
        depth, x, y, occurred_at. Lo que no venga en el dict se queda igual.
        event_id no se puede corregir (es inmutable). occurred_at sí, aunque
        no esté en K, porque afecta las asociaciones.

        Pasos (mismo orden que create_event, pero sobre un evento existente):
        1. Validar que esté activo.
        2. Guardar foto de los valores viejos.
        3. Si cambia el epicentro, recalcular zona poblada.
        4. Aplicar la corrección sobre el mismo objeto Event.
        5-6. Reubicar en AVL/BST si cambió la clave.
        7-10. Recalcular asociaciones (propia + afectados).
        11. Apilar CorrectionAction para poder deshacer.
        12. Devolver el evento.
        """

        # 1. Validación: solo se puede corregir un evento ACTIVO.
        if event_id in self.archived_history:
            raise ValueError(f"El evento {event_id} está archivado, no se puede corregir")
        if event_id in self.eliminated_IDs:
            raise ValueError(f"El evento {event_id} está eliminado, no se puede corregir")
        if event_id not in self.event_index:
            raise KeyError(f"No existe un evento con id {event_id}")

        node = self.event_index[event_id]
        event = node.event

        # 2. Foto de los valores viejos, leídos del evento ANTES de tocarlo.
        old_magnitude = event.magnitude
        old_depth = event.depth
        old_x = event.x
        old_y = event.y
        old_occurred_at = event.occurred_at
        old_is_in_populated_zone = event.is_in_populated_zone
        old_revision = event.revision
        old_attention_status = event.attention_status

        # 3. Si cambia x o y, hay que recalcular zona con el epicentro COMPLETO:
        # si solo mandaron uno de los dos, el otro se completa con el valor
        # actual del evento (mismo patrón que update_zone con sus "changes").
        is_in_populated_zone = None
        if "x" in changes or "y" in changes:
            new_x = changes.get("x", event.x)
            new_y = changes.get("y", event.y)
            is_in_populated_zone = self.epicenter_in_populated_zone(new_x, new_y)

        # 4. Aplicar la corrección. Muta el mismo objeto event y devuelve
        # la clave de antes y la de después.
        old_key, new_key = event.apply_correction(
            magnitude=changes.get("magnitude"),
            depth=changes.get("depth"),
            x=changes.get("x"),
            y=changes.get("y"),
            occurred_at=changes.get("occurred_at"),
            is_in_populated_zone=is_in_populated_zone,
        )

        # 5-6. Si la clave cambió (subió/bajó de prioridad, o cambió M),
        # hay que sacarlo de los árboles con la clave vieja y reinsertarlo
        # con la nueva. event_index se actualiza con el nodo NUEVO.
        balance = (self.mode == Mode.NORMAL)

        if old_key != new_key:
            self.avl_tree.delete(old_key, balance=balance)
            self.bst_tree.delete(old_key)
            new_node = self.avl_tree.insert(event, balance=balance)
            self.bst_tree.insert(event)
            self.event_index[event_id] = new_node

        # 7. Grupo 1: otros eventos que podrían haber ganado o perdido a este
        # evento como candidato nuevo. Se usa el RANGO entre el valor viejo y
        # el nuevo, porque:
        #   - Si la fecha se movió a MÁS NUEVA, algunos eventos dejan de tenerlo
        #     como candidato (estaban entre la fecha nueva y la vieja).
        #   - Si la fecha se movió a MÁS ANTIGUA, algunos eventos lo ganan.
        #   - Lo mismo con la magnitud: si bajó, algunos dejan de tenerlo; si
        #     subió, algunos lo ganan.
        # Usar min/max cubre los dos sentidos. Se recalcula de más, pero no
        # se deja ninguna referencia desactualizada.
        min_occurred = min(old_occurred_at, event.occurred_at)
        max_magnitude = max(old_magnitude, event.magnitude)

        affected_group_1 = [
            other for other in self._all_active_and_archived_events()
            if other.event_id != event_id
            and other.occurred_at > min_occurred
            and other.magnitude < max_magnitude
        ]

        # 8. Grupo 2: eventos que YA tenían a este evento como referencia
        # antes de la corrección. Se sacan del índice inverso.
        group_2_ids = self.referenced_by.get(event_id, set())
        affected_group_2 = [self._find_any_event(other_id) for other_id in group_2_ids]

        # Unión sin duplicados (un evento podría estar en los dos grupos).
        affected_others = {other.event_id: other for other in affected_group_1 + affected_group_2}.values()

        # 9. Foto de referencias viejas: el evento mismo + todos los afectados,
        # ANTES de recalcular nada.
        old_references = {event_id: event.reference_id}
        for other in affected_others:
            old_references[other.event_id] = other.reference_id

        # 10. Recalcular: primero el evento mismo, luego cada afectado.
        self._recalculate_reference(event)
        for other in affected_others:
            self._recalculate_reference(other)

        # 11. Apilar la acción para poder deshacer todo esto de un solo golpe.
        self.undo_stack.push(CorrectionAction(
            event_id=event_id,
            old_magnitude=old_magnitude,
            old_depth=old_depth,
            old_x=old_x,
            old_y=old_y,
            old_occurred_at=old_occurred_at,
            old_is_in_populated_zone=old_is_in_populated_zone,
            old_revision=old_revision,
            old_attention_status=old_attention_status,
            old_references=old_references,
        ))

        # 12. Devolver el evento corregido.
        return event

    def mark_reviewed(self, event_id: int) -> Event:
        """Marca un evento activo como revisado (sección 'Estado de atención').

        No toca P, M ni I, así que no cambia la clave, no reinserta nada en
        los árboles, y no afecta asociaciones.
        """

        # 1. Validación: mismo criterio que correct_event, solo se puede
        # marcar como revisado un evento ACTIVO.
        if event_id in self.archived_history:
            raise ValueError(f"El evento {event_id} está archivado, no se puede marcar como revisado")
        if event_id in self.eliminated_IDs:
            raise ValueError(f"El evento {event_id} está eliminado, no se puede marcar como revisado")
        if event_id not in self.event_index:
            raise KeyError(f"No existe un evento con id {event_id}")

        event = self.event_index[event_id].event

        # 2. Foto del valor viejo, antes de cambiarlo. Es lo único que hace
        # falta guardar para poder deshacer.
        old_attention_status = event.attention_status

        # 3. Aplicar el cambio sobre el mismo objeto.
        event.mark_as_reviwed()

        # 4. No hay paso de árboles/event_index/asociaciones: la clave no
        # cambió, así que la posición del evento en el AVL y el BST sigue
        # siendo válida tal cual, y las asociaciones no dependen de este dato.

        # 5. Apilar la acción para poder deshacer.
        self.undo_stack.push(AttentionChangeAction(event_id, old_attention_status))

        # 6. Devolver el evento ya marcado.
        return event

    
    def delete_event(self, event_id: int) -> Event:
        """Eliminación individual de un evento activo (sección 'Eliminación
        individual'). Solo retira ESE evento; sus descendientes en el AVL
        quedan intactos (eso lo garantiza el propio delete() del árbol).

        No hay Grupo 1 aquí: un evento que se va del sistema no puede
        volverse candidato nuevo de nadie. Solo hay que avisarle a quienes
        YA lo tenían como referencia (Grupo 2).
        """

        # 1. Validación: mismo criterio que correct_event y mark_reviewed,
        # solo se puede eliminar un evento ACTIVO.
        if event_id in self.archived_history:
            raise ValueError(f"El evento {event_id} está archivado, no se puede eliminar así")
        if event_id in self.eliminated_IDs:
            raise ValueError(f"El evento {event_id} ya está eliminado")
        if event_id not in self.event_index:
            raise KeyError(f"No existe un evento con id {event_id}")

        node = self.event_index[event_id]
        event = node.event
        key = event.key  # se guarda ahora porque, una vez eliminado, ya no hay de dónde sacarla

        # 2-3. Guardar la referencia propia ANTES de limpiarla, y limpiarla con
        # _assign_reference (ya sabe actualizar referenced_by sin desincronizar).
        # Si no se guarda antes, el valor se pierde en cuanto se llama.
        old_references = {event_id: event.reference_id}
        self._assign_reference(event, None)

        # 4. Retirar el evento de las tres estructuras activas. El orden entre
        # estas tres no importa: ya tenemos `event` guardado en una variable,
        # no dependemos de que siga en ninguna de ellas.
        balance = (self.mode == Mode.NORMAL)
        self.avl_tree.delete(key, balance=balance)
        self.bst_tree.delete(key)
        del self.event_index[event_id]

        # Registrar el id como eliminado. Esto es lo que impide que un reporte
        # posterior lo reactive (sección "Eliminación individual").
        self.eliminated_IDs.add(event_id)

        # 5. Grupo 2: quienes YA tenían a este evento como referencia. Se
        # consigue la lista (es solo un dict.get, no depende de los árboles),
        # pero se RECALCULA después de que el evento ya salió del AVL/BST —
        # si se hiciera antes, get_candidates todavía lo vería como válido y
        # alguien terminaría apuntando a un evento que ya no existe.
        affected_ids = self.referenced_by.get(event_id, set())
        affected = [self._find_any_event(other_id) for other_id in affected_ids]

        for other in affected:
            old_references[other.event_id] = other.reference_id

        for other in affected:
            self._recalculate_reference(other)

        # 6. Apilar la acción: el evento completo (para poder reinsertarlo tal
        # cual al deshacer) y las referencias viejas de todos los afectados.
        self.undo_stack.push(DeletionAction(event, old_references))

        # 7. Devolver el evento ya eliminado (guardado, no el de la estructura).
        return event

    def change_parameters(self, changes: dict) -> dict:
        """Cambia uno o varios parámetros globales (L, W, R, T).

        Recibe un dict {nombre: nuevo_valor}. Valida TODOS los nombres y
        valores antes de aplicar nada (atómico: si uno falla, ninguno se
        cambia). Ignora los parámetros cuyo valor no cambia realmente.

        Devuelve un dict solo con los parámetros que sí cambiaron.

        Si cambia W o R, redefine qué eventos son candidatos entre sí, así
        que recalcula la referencia de todos los eventos activos y
        archivados. En ese caso, la acción guarda old_references para poder
        deshacer. Para L y T no hay recálculo ni old_references.

        W y R juntos. Si changes = {"W": 24, "R": 50} y ambos cambian:
        W se aplica primero, se recalculan referencias, se apila acción con old_refs (antes de W).
        Luego R, se recalculan otra vez, se apila acción con old_refs (que ya refleja el cambio de W).
        Al deshacer, se revierte R (volviendo R al viejo y restaurando refs de después de W), luego W. \
        Funciona, aunque recalcula dos veces.
        """
        valid_names = {"L", "W", "R", "T"}

        # 1. Validar nombres.
        for name in changes:
            if name not in valid_names:
                raise ValueError(f"Unknown parameter: {name}")

        # 2. Validar valores (por si alguien llama a Scenario directamente).
        if "L" in changes:
            new_L = changes["L"]
            if not isinstance(new_L, int) or isinstance(new_L, bool) or new_L < 0:
                raise ValueError("L must be a non-negative integer")
            
        for name in ("W", "R", "T"):
            if name in changes and changes[name] <= 0:
                raise ValueError(f"{name} must be a positive number")

        # 3. Aplicar solo los que cambian de verdad.
        changed = {}

        for name, new_value in changes.items():
            old_value = getattr(self, name)
            if old_value == new_value:
                continue

            # Foto de referencias antes de tocar el parámetro, solo si aplica.
            old_refs = None
            if name in ("W", "R"):
                old_refs = {
                    event.event_id: event.reference_id
                    for event in self._all_active_and_archived_events()
                }

            # Aplicar el cambio.
            setattr(self, name, new_value)

            # Recalcular todas las referencias si W o R cambió.
            if name in ("W", "R"):
                for event in self._all_active_and_archived_events():
                    self._recalculate_reference(event)

            # Apilar la acción con el valor viejo y (si aplica) la foto previa.
            self.undo_stack.push(
                ParameterChangeAction(name, old_value, old_refs)
            )
            changed[name] = new_value

        return changed

    def process_next_report(self) -> dict:
        """Procesa UN reporte de la cola (sección 8: "un reporte por paso").

        Saca el primero de la cola y decide qué caso es. Los casos posibles
        están en la tabla de la sección 6: id desconocido (crear), revisión
        mayor (corregir), igual revisión y mismos datos (confirmar), igual
        revisión y datos distintos (conflicto), revisión menor (antiguo), e
        id eliminado (rechazar).

        La igualdad de datos se refiere a magnitud, profundidad, epicentro
        (x, y) y tiempo de ocurrencia. NO cuenta la estación emisora.

        Aunque el reporte sea rechazado/antiguo/conflicto, se apila una
        QueueStepAction para poder devolverlo a su posición en la cola al
        deshacer. Si el caso fue crear o corregir, la QueueStepAction también
        guarda la acción interna que ese paso generó.
        """

        # 1. Cola vacía → no hay nada que procesar.
        if self.report_queue.is_empty():
            raise ValueError("No hay reportes pendientes en la cola")

        # 2. Peek: miramos el primero sin sacarlo.
        report = self.report_queue.peek()
        queue_position = 0   # siempre el primero (la cola es FIFO)
        event_id = report.event_id

        # 3. Decidir caso y ejecutar.
        case = None
        inner_action = None
        confirmed_station_id = None

        # Caso especial: id eliminado. Se rechaza sin tocar nada.
        if event_id in self.eliminated_IDs:
            case = "eliminated"

        # Caso: id desconocido → crear evento nuevo.
        # "Desconocido" = no está activo ni archivado ni eliminado.
        elif event_id not in self.event_index and event_id not in self.archived_history:
            case = "created"
            self.create_event(
                event_id=event_id,
                magnitude=report.magnitude,
                depth=report.depth,
                x=report.x,
                y=report.y,
                occurred_at=report.occurred_at,
                stations={report.station},       # el set con la única estación del reporte
                revision=report.revision_num,    # la primera revisión puede ser > 1
            )
            # create_event ya apiló una CreationAction. La sacamos para meterla
            # dentro del QueueStepAction: un solo paso de la cola = una sola
            # acción en la pila, no dos.
            inner_action = self.undo_stack.pop()

        # Caso: id archivado.
        elif event_id in self.archived_history:
            archived_event = self.archived_history[event_id]
            if report.revision_num > archived_event.revision:
                # Un reporte con revisión mayor REACTIVA el evento archivado:
                # sale de archived_history y vuelve al AVL con los datos
                # corregidos (sección 6). Esto es una operación completa por
                # sí sola, con reubicación en árboles y recálculo de referencias.
                # PENDIENTE de implementar como helper aparte.
                case = "archived_needs_reactivation"
            elif report.revision_num == archived_event.revision:
                # Confirmación o conflicto sobre un archivado: no lo reactiva.
                # Se rechaza igual que "antiguo".
                case = "archived_not_reactivated"
            else:
                case = "old"

        # Caso: id activo.
        else:
            event = self.event_index[event_id].event

            if report.revision_num > event.revision:
                # Revisión mayor → corregir.
                case = "corrected"
                changes = {
                    "magnitude": report.magnitude,
                    "depth": report.depth,
                    "x": report.x,
                    "y": report.y,
                    "occurred_at": report.occurred_at,
                }
                self.correct_event(event_id, changes)
                inner_action = self.undo_stack.pop()

                # Añadir la estación del reporte si aún no estaba.
                # Si añadirla "tuvo efecto", guardamos su id para poder quitarla
                # al deshacer el paso de la cola.
                if report.station not in event.stations:
                    event.stations.add(report.station)
                    confirmed_station_id = report.station.station_id

            elif report.revision_num == event.revision:
                # Igual revisión → ¿mismos datos?
                same_data = (
                    report.magnitude == event.magnitude
                    and report.depth == event.depth
                    and report.x == event.x
                    and report.y == event.y
                    and report.occurred_at == event.occurred_at
                )
                if same_data:
                    # Confirmación.
                    case = "confirmed"
                    if report.station not in event.stations:
                        event.stations.add(report.station)
                        confirmed_station_id = report.station.station_id
                else:
                    # Conflicto: no se toca el evento.
                    case = "conflict"

            else:
                # Revisión menor → antiguo.
                case = "old"

        # 4. Ahora sí, sacar el reporte de la cola.
        self.report_queue.dequeue()

        # 5. Apilar la acción del paso. Aunque el caso no haya modificado nada
        # (conflicto, antiguo, eliminado, archivado sin reactivar), la acción
        # guarda el reporte y su posición para poder devolverlo a la cola al
        # deshacer.
        self.undo_stack.push(QueueStepAction(
            report=report,
            queue_position=queue_position,
            inner_action=inner_action,
            confirmed_station_id=confirmed_station_id,
        ))

        # 6. Devolver info del paso, para que el frontend muestre qué pasó.
        return {
            "case": case,
            "event_id": event_id,
            "report": report,
        }





























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
