from app.domain.event import Event
from enum import Enum
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Optional
import math
from app.domain.zone import Zone
from app.domain.station import Station
from app.domain.report import Report
from app.domain.mode import Mode

from app.domain.event import Event, AttentionStatus

from app.structures.stack import Stack
from app.structures.queue import Queue 
from app.domain.action import (
    CreationAction, CorrectionAction, AttentionChangeAction, DeletionAction,
    ParameterChangeAction, ClockAdvanceAction, QueueStepAction, MassArchiveAction,
    GlobalRecoveryAction, LoadAction, ReactivationAction,
)
from app.structures.avl_tree import AVLTree, ROTATION_METRIC_KEYS, AVLTopologySnapshot
from app.structures.avl_node import AVLNode
from app.structures.bst_node import BSTNode
from app.structures.bst_tree import BSTTree



class Scenario:

    def __init__(self, metrics : Optional[dict[str, int]] = None,avl_tree: Optional[AVLTree] = None, bst_tree: Optional[BSTTree] = None, 
                 event_index : Optional[dict[int, AVLNode]] = None, stations : Optional[dict[int, Station]] = None, zones: Optional[list[Zone]] = None, 
                 eliminated_IDs: Optional[set[int]] = None, archived_history: Optional[dict[int, Event]] = None, referenced_by=None, simulation_clock: Optional[datetime] = None, 
                L: int=3, W: float = 48.0, R: float = 40.0, T: float = 72.0, mode: Mode = Mode.NORMAL, undo_stack: Optional[Stack] = None, report_queue: Optional[Queue] = None):

        # Collections for elimination and history.
        self.eliminated_IDs = eliminated_IDs if eliminated_IDs is not None else set()
        self.archived_history = archived_history if archived_history is not None else dict()

        # Simulation clock, second precision. If none is provided, use the
        # current system UTC time.
        self._simulation_clock: datetime = simulation_clock or datetime.now(timezone.utc).replace(microsecond=0)
        # Store a fixed baseline and measure elapsed time monotonically so wall-clock adjustments do not stop or reverse the simulation clock.
        self._clock_anchor_monotonic = monotonic()

        # Configurable global parameters.
        self.L = L  # Depth limit, initially 3

        self.W= W
        self.R= R
        self.T= T

        self.mode = mode 
        self.zones = zones if zones is not None else list()
        self.stations = stations if stations is not None else dict()
        self.event_index = event_index if event_index is not None else dict()
        self.metrics = metrics if metrics is not None else dict()

        # AVLTree must receive self.metrics after it is created, so both
        # share the same metrics dictionary (single source of truth).
        self.avl_tree = avl_tree if avl_tree is not None else AVLTree(metrics=self.metrics)
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

        # The clock cannot move backwards.
        if new_clock < self.simulation_clock:
            raise ValueError("Cannot move the simulation clock backwards")

        # If nothing changed, do not push an action that would do nothing.
        if new_clock == self.simulation_clock:
            return self.simulation_clock

        # Validations: no event, archived event, or report may end up
        # with a timestamp later than the new clock.
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

        # Save the current simulation clock (including the elapsed real
        # time) BEFORE changing it, so undo can return to this exact instant.
        old_clock = self.simulation_clock

        # Apply the new clock.
        self.simulation_clock = new_clock

        # Push the action with the old value.
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
        deshacer.

        ──────────────────────────────────────────────────────────────
        El problema de las DOS acciones por un solo paso
        ──────────────────────────────────────────────────────────────

        Un paso de la cola es UNA sola acción para el usuario, pero por
        dentro puede disparar otra operación (crear, corregir o reactivar un
        evento). create_event, correct_event y archived_reactivation apilan
        su propia acción al terminar. Si process_next_report además apila
        una QueueStepAction, quedan DOS acciones en la pila por un solo
        paso, y el usuario tendría que pulsar "deshacer" dos veces.

        La solución es sacar con pop la acción interna que acaban de apilar,
        y meterla DENTRO de la QueueStepAction. Así la pila solo ve una
        acción por paso, pero esa acción lleva adentro todo lo necesario
        para revertir la operación interna.
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
        # "Desconocido" = no está activo, ni archivado, ni eliminado.
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
                # corregidos (sección 6).
                case = "reactivated"
                event = self.archived_reactivation(report)

                # archived_reactivation ya apiló su propia ReactivationAction.
                # La sacamos para meterla dentro del QueueStepAction, mismo
                # patrón que "created" y "corrected": un paso de la cola = una
                # sola acción en la pila.
                inner_action = self.undo_stack.pop()

                # Añadir la estación del reporte si aún no estaba. Va AQUÍ y no
                # dentro de archived_reactivation, por la misma razón que en
                # "corrected": así podemos comparar antes/después y saber si la
                # estación era nueva, para poder quitarla al deshacer.
                if report.station not in event.stations:
                    event.stations.add(report.station)
                    confirmed_station_id = report.station.station_id
            elif report.revision_num == archived_event.revision:
                # Confirmación o conflicto sobre un archivado: no lo reactiva.
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

    def preview_branch_archive(self) -> dict:
        """Vista previa del archivo masivo: dice QUÉ subárbol se archivaría
        si el usuario confirma. NO modifica nada.

        Corresponde al paso de la sección 10:
        "Antes de ejecutar, se muestran los identificadores afectados, su
        cantidad y la justificación de la selección."

        El frontend llama a este método para mostrar un diálogo de confirmación.
        Si el usuario acepta, llama a branch_archive(winner_root_id) para
        ejecutar de verdad.

        Devuelve un dict:
        - Si no hay ramas elegibles:
            {"eligible": False, "reason": "..."}
        - Si hay una ganadora:
            {
                "eligible": True,
                "root_id": id de la raíz del subárbol ganador,
                "size": cantidad de nodos del ganador,
                "depth": profundidad de la raíz del ganador,
                "event_ids": lista con los ids de todos los eventos
                            que se archivarían,
            }

        Qué NO hace (importante)
        No desprende nada del árbol. El subárbol sigue donde está.

        No mueve eventos a archived_history. Todos siguen activos.

        No saca nada de event_index.

        No toca reference_id ni referenced_by.

        No apila acciones. No hay nada que deshacer porque no se cambió nada.
        """
        # 1. Pedirle al AVL todos los subárboles elegibles.
        # Un subárbol es elegible si todos sus eventos tienen prioridad baja
        # y antigüedad mayor a T horas (sección 10).
        eligible = self.avl_tree.eligible_archive_subtrees(self.simulation_clock, self.T)

        # 2. Sin elegibles: informar y no tocar nada.
        if not eligible:
            return {"eligible": False, "reason": "No eligible branch found"}

        # 3. Elegir el ganador según los criterios de la sección 10:
        #    - mayor cantidad de nodos
        #    - si empatan, mayor profundidad de la raíz
        #    - si siguen empatados, mayor id de la raíz
        # max() con una tupla compara primero por el primer elemento, luego por
        # el segundo, luego por el tercero. Es exactamente el orden del criterio.
        winner = max(
            eligible,
            key=lambda e: (e["size"], e["depth"], e["root_id"]),
        )

        # 4. Fijar la lista de ids del subárbol ganador. Es lo que se mostrará
        # al usuario y lo que se usará al ejecutar (el conjunto se fija antes
        # de tocar el árbol, para que rotaciones no cambien la lista).
        event_ids = self.avl_tree.subtree_event_ids(winner["root"])

        # 5. Devolver info para el frontend.
        return {
            "eligible": True,
            "root_id": winner["root_id"],
            "size": winner["size"],
            "depth": winner["depth"],
            "event_ids": event_ids,
        }

    def branch_archive(self, winner_root_id: int) -> dict:
        """Ejecuta el archivo masivo del subárbol elegible cuya raíz tiene
        id `winner_root_id` (sección 10).

        Revalida el ganador: entre el preview y este llamado el árbol pudo
        cambiar, así que recalcula elegibles y confirma que el id sigue
        siendo elegible. Si ya no lo es, informa y conserva el estado.

        Pasos:
        1. Revalidar: recalcular elegibles y buscar el ganador con ese id.
        2. Fijar event_ids ANTES de tocar el árbol (sección 10: 'el conjunto
            corresponde a la topología existente al iniciar la operación y
            se mantiene fijo durante su ejecución').
        3. Desprender el subárbol con detach_subtree.
        4. Capturar rotation_delta de las rotaciones que produjo detach.
        5. Mover los eventos al histórico y sacarlos de event_index.
            NO se tocan reference_id ni referenced_by: los archivados siguen
            contando para asociaciones (secciones 7 y 10).
        6. Apilar MassArchiveAction para deshacer todo como una sola acción.
        """
        # 1. Revalidar.
        eligible = self.avl_tree.eligible_archive_subtrees(self.simulation_clock, self.T)
        matches = [e for e in eligible if e["root_id"] == winner_root_id]

        if not matches:
            return {
                "archived": False,
                "reason": f"Subtree with root id {winner_root_id} is not eligible anymore",
            }

        winner = matches[0]
        node = winner["root"]

        # 2. Fijar ids ANTES de tocar el árbol.
        event_ids = self.avl_tree.subtree_event_ids(node)

        # 3. Desprender. En modo normal se rota; en estrés, no.
        balance = (self.mode == Mode.NORMAL)
        archived_root, former_parent, was_left_child = self.avl_tree.detach_subtree(
            node, balance=balance
        )

        # 4. Capturar el delta de métricas de rotación que dejó el detach.
        rotation_delta = self.avl_tree.last_rotation_delta()

        # 5. Mover los eventos al histórico y sacarlos del índice activo.
        events = self.avl_tree.subtree_events(archived_root)
        for event in events:
            self.archived_history[event.event_id] = event
            del self.event_index[event.event_id]
        # OJO: no se toca reference_id ni referenced_by (asociaciones).

        # 6. Apilar la acción (una sola para todo el archivo).
        self.undo_stack.push(MassArchiveAction(
            archived_root=archived_root,
            former_parent=former_parent,
            was_left_child=was_left_child,
            event_ids=event_ids,
            rotation_delta=rotation_delta,
        ))

        return {
            "archived": True,
            "root_id": winner_root_id,
            "size": winner["size"],
            "depth": winner["depth"],
            "event_ids": event_ids,
        }

    def archived_reactivation(self, report: Report) -> Event:
        """Reactiva un evento archivado cuando llega un reporte con revisión
        mayor que la vigente (sección 6: "Un evento archivado conserva su
        identidad. Una revisión mayor y válida lo reactiva como pendiente en
        el AVL con sus datos corregidos").

        Es como un correct_event, pero partiendo de un evento que ya no está
        en el árbol: hay que insertarlo desde cero, no reubicarlo. Por eso usa
        apply_correction() igual que correct_event, pero el "antes" de este
        evento es estar en archived_history, no en el AVL.

        Pasos:
        1. Guardar foto de los valores viejos (para poder deshacer).
        2. Sacar el evento de archived_history.
        3. Recalcular zona poblada con el epicentro del reporte.
        4. Aplicar corrección con los datos del reporte y la revisión del reporte.
        5. Insertar en AVL y BST, agregar a event_index.
        6. Recalcular referencias (propia + afectados).
        7. Apilar ReactivationAction para poder deshacer esta reactivación.
        8. Devolver el evento reactivado.

        OJO: a propósito NO se añade aquí la estación del reporte. Esa parte
        se dejó para que la haga process_next_report, igual que ya hace con
        el caso "corrected": así quien llama puede comparar antes/después y
        saber si la estación era nueva, para registrar confirmed_station_id
        en el QueueStepAction y poder quitarla al deshacer el paso completo.

        A diferencia de la versión anterior, esta función SÍ apila su propia
        acción (ReactivationAction): process_next_report la saca de la pila
        con pop(), igual que ya hace con CreationAction y CorrectionAction,
        para meterla dentro del QueueStepAction del paso.
        """
        event_id = report.event_id
        event = self.archived_history[event_id]

        # 1. Foto de valores viejos.
        old_magnitude = event.magnitude
        old_depth = event.depth
        old_x = event.x
        old_y = event.y
        old_occurred_at = event.occurred_at
        old_is_in_populated_zone = event.is_in_populated_zone
        old_revision = event.revision
        old_attention_status = event.attention_status

        # 2. Sacar del histórico (ya no está archivado).
        del self.archived_history[event_id]

        # 3. Recalcular zona poblada con el epicentro del reporte.
        is_populated = self.epicenter_in_populated_zone(report.x, report.y)

        # 4. Aplicar la corrección. El evento NO estaba en el árbol, así que
        # el (old_key, new_key) que devuelve apply_correction no se necesita
        # aquí (eso es para reubicar, y la inserción de abajo es desde cero).
        event.apply_correction(
            magnitude=report.magnitude,
            depth=report.depth,
            x=report.x,
            y=report.y,
            occurred_at=report.occurred_at,
            revision=report.revision_num,
            is_in_populated_zone=is_populated,
        )

        # 5. Insertar en AVL y BST (alta, no reubicación).
        balance = (self.mode == Mode.NORMAL)
        node = self.avl_tree.insert(event, balance=balance)
        self.bst_tree.insert(event)
        self.event_index[event_id] = node

        # 6. Recalcular referencias. Mismo esquema que correct_event:
        # Grupo 1 (podrían tenerlo como candidato nuevo, con rango viejo-nuevo)
        # + Grupo 2 (ya lo tenían como referencia).
        min_occurred = min(old_occurred_at, event.occurred_at)
        max_magnitude = max(old_magnitude, event.magnitude)

        affected_group_1 = [
            other for other in self._all_active_and_archived_events()
            if other.event_id != event_id
            and other.occurred_at > min_occurred
            and other.magnitude < max_magnitude
        ]

        group_2_ids = self.referenced_by.get(event_id, set())
        affected_group_2 = [self._find_any_event(other_id) for other_id in group_2_ids]

        affected_others = {
            other.event_id: other
            for other in affected_group_1 + affected_group_2
        }.values()

        # Foto de referencias viejas, ANTES de recalcular (mismo patrón que
        # correct_event/delete_event: el propio evento + todos los afectados).
        old_references = {event_id: event.reference_id}
        for other in affected_others:
            old_references[other.event_id] = other.reference_id

        self._recalculate_reference(event)
        for other in affected_others:
            self._recalculate_reference(other)

        # 7. Apilar la acción. Es lo que faltaba: antes estos datos morían aquí.
        self.undo_stack.push(ReactivationAction(
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

        # 8. Devolver el evento reactivado.
        return event

    def _undo_creation(self, action: CreationAction) -> dict:
        """Deshace una creación: saca el evento de las estructuras activas
        y restaura las referencias que la creación había cambiado.

        En old_references puede venir una entrada para el propio evento
        creado (con None). Se ignora, porque el evento ya no existe y
        _find_any_event fallaría. Solo se restauran los OTROS.
        """
        event_id = action.event_id
        node = self.event_index[event_id]
        event = node.event

        balance = (self.mode == Mode.NORMAL)
        self.avl_tree.delete(event.key, balance=balance)
        self.bst_tree.delete(event.key)
        del self.event_index[event_id]

        for other_id, old_ref in action.old_references.items():
            if other_id == event_id:
                continue
            self._assign_reference(self._find_any_event(other_id), old_ref)

        return {"undone": "creation", "event_id": event_id}

    def _undo_correction(self, action: CorrectionAction) -> dict:
        """Deshace una corrección:
        1. Guarda la clave ACTUAL del evento (con los datos corregidos).
        2. Restaura los valores viejos uno por uno.
        3. Si la clave cambió, reubica el nodo en AVL/BST.
        4. Restaura las referencias de todos los afectados.
        """
        event_id = action.event_id
        node = self.event_index[event_id]
        event = node.event

        current_key = event.key

        event.magnitude = action.old_magnitude
        event.depth = action.old_depth
        event.x = action.old_x
        event.y = action.old_y
        event.occurred_at = action.old_occurred_at
        event.is_in_populated_zone = action.old_is_in_populated_zone
        event.revision = action.old_revision
        event.attention_status = action.old_attention_status

        # priority y key son @property: al restaurar los valores, la clave
        # vieja se recalcula sola.
        new_key = event.key

        if current_key != new_key:
            balance = (self.mode == Mode.NORMAL)
            self.avl_tree.delete(current_key, balance=balance)
            self.bst_tree.delete(current_key)
            new_node = self.avl_tree.insert(event, balance=balance)
            self.bst_tree.insert(event)
            self.event_index[event_id] = new_node

        for other_id, old_ref in action.old_references.items():
            self._assign_reference(self._find_any_event(other_id), old_ref)

        return {"undone": "correction", "event_id": event_id}
    
    def _undo_reactivation(self, action: ReactivationAction) -> dict:
        """Deshace una reactivación.

        A diferencia de _undo_correction, el evento NO se reubica dentro del
        árbol — sale del AVL por completo y vuelve a archived_history, porque
        antes de la reactivación no estaba en el AVL para nada.

        Orden importante: hay que localizar y retirar el evento usando su
        clave ACTUAL (la que tiene ahora mismo, con los datos de la
        reactivación) ANTES de restaurar los valores viejos — si se restauran
        primero, event.key cambia (es un @property) y ya no coincide con la
        posición donde está insertado en el árbol.

        1. Sacar el evento del AVL/BST/event_index con su clave actual.
        2. Restaurar los 7 valores viejos sobre el mismo objeto.
        3. Devolverlo a archived_history.
        4. Restaurar las referencias de todos los afectados (incluido el
        propio evento).
        """
        event_id = action.event_id
        node = self.event_index[event_id]
        event = node.event

        balance = (self.mode == Mode.NORMAL)
        self.avl_tree.delete(event.key, balance=balance)
        self.bst_tree.delete(event.key)
        del self.event_index[event_id]

        event.magnitude = action.old_magnitude
        event.depth = action.old_depth
        event.x = action.old_x
        event.y = action.old_y
        event.occurred_at = action.old_occurred_at
        event.is_in_populated_zone = action.old_is_in_populated_zone
        event.revision = action.old_revision
        event.attention_status = action.old_attention_status

        self.archived_history[event_id] = event

        for other_id, old_ref in action.old_references.items():
            self._assign_reference(self._find_any_event(other_id), old_ref)

        return {"undone": "reactivation", "event_id": event_id}

    def _undo_deletion(self, action: DeletionAction) -> dict:
        """Deshace una eliminación:
        1. Quita el id de eliminated_IDs (vuelve a estar disponible).
        2. Reinserta el evento en AVL y BST.
        3. Actualiza event_index con el nodo nuevo.
        4. Restaura las referencias viejas.
        """
        event = action.event
        event_id = event.event_id

        self.eliminated_IDs.discard(event_id)

        balance = (self.mode == Mode.NORMAL)
        node = self.avl_tree.insert(event, balance=balance)
        self.bst_tree.insert(event)
        self.event_index[event_id] = node

        for other_id, old_ref in action.old_references.items():
            self._assign_reference(self._find_any_event(other_id), old_ref)

        return {"undone": "deletion", "event_id": event_id}

    def _undo_attention_change(self, action: AttentionChangeAction) -> dict:
        """Restaura solo el estado de atención viejo."""
        event = self._find_any_event(action.event_id)
        event.attention_status = action.old_attention_status
        return {"undone": "attention_change", "event_id": action.event_id}

    def _undo_parameter_change(self, action: ParameterChangeAction) -> dict:
        """Restaura el valor viejo del parámetro. Si era W o R, también
        restaura las referencias que el cambio había recalculado."""
        setattr(self, action.parameter_name, action.old_value)

        if action.old_references is not None:
            for event_id, old_ref in action.old_references.items():
                self._assign_reference(self._find_any_event(event_id), old_ref)

        return {"undone": "parameter_change", "parameter": action.parameter_name}

    def _undo_clock_advance(self, action: ClockAdvanceAction) -> dict:
        """Restaura el reloj de simulación al instante exacto previo."""
        self.simulation_clock = action.old_clock
        return {"undone": "clock_advance"}

    def _undo_queue_step(self, action: QueueStepAction) -> dict:
        """Deshace un paso de la cola.

        Orden:
        1. Quitar la estación confirmada (si aplica), ANTES de revertir
           inner_action: si inner_action fue una creación, el evento
           desaparece y ya no podríamos quitarle la estación.
        2. Revertir inner_action (si existe) llamando al helper
           correspondiente.
        3. Devolver el reporte a la cola en su posición original.
        """
        # 1. Estación confirmada.
        if action.confirmed_station_id is not None:
            station = self.stations.get(action.confirmed_station_id)
            if station is not None:
                try:
                    event = self._find_any_event(action.report.event_id)
                    event.stations.discard(station)
                except KeyError:
                    # El evento ya no existe (por ejemplo, era una creación
                    # y aún no se revirtió). No hay estación que quitar.
                    pass

        # 2. Revertir inner_action si la hubo.
        if action.inner_action is not None:
            inner = action.inner_action

            if isinstance(inner, CreationAction):
                self._undo_creation(inner)

            elif isinstance(inner, CorrectionAction):
                self._undo_correction(inner)
                
            elif isinstance(inner, ReactivationAction):
                self._undo_reactivation(inner)
            else:
                self.undo_stack.push(action)
                raise NotImplementedError(
                    f"QueueStepAction con inner_action de tipo {type(inner).__name__}"
                )

        # 3. Devolver el reporte a la cola.
        self.report_queue.insert_at(action.queue_position, action.report)

        return {"undone": "queue_step", "event_id": action.report.event_id}

    def _undo_mass_archive(self, action: MassArchiveAction) -> dict:
        """Deshace un archivo masivo.

        Pasos:
        1. Re-enganchar el subárbol desprendido en su posición original,
           subiendo por el camino para rebalancear.
        2. Recorrer los nodos del subárbol y devolverlos a event_index y
           sacarlos de archived_history.
        3. Restar rotation_delta de las métricas.

        Las asociaciones no se tocan: el archivo no las cambió.
        """
        balance = (self.mode == Mode.NORMAL)

        self.avl_tree.attach_subtree(
            action.archived_root,
            action.former_parent,
            action.was_left_child,
            balance=balance,
        )

        for node in self.avl_tree.subtree_nodes(action.archived_root):
            event_id = node.event.event_id
            self.event_index[event_id] = node
            if event_id in self.archived_history:
                del self.archived_history[event_id]

        self.avl_tree.revert_rotation_metrics(action.rotation_delta)

        root_id = action.event_ids[0] if action.event_ids else None
        return {"undone": "mass_archive", "root_id": root_id}

    def _undo_global_recovery(self, action: GlobalRecoveryAction) -> dict:
        """Deshace una recuperación global: restaura la topología del AVL
        y las métricas de rotación, y vuelve al modo anterior."""
        self.avl_tree.restore_topology(action.topology_snapshot)
        self.avl_tree.revert_rotation_metrics(action.rotation_delta)
        self.mode = action.previous_mode
        return {"undone": "global_recovery"}

    def _undo_load(self, action: LoadAction) -> dict:
        """Deshace la carga de un escenario restaurando el estado anterior.

        action.previous_state es el dict que armó _snapshot_full_state()
        justo antes de cargar (ver "ESTADO COMPLETO DEL ESCENARIO"): los
        objetos originales del escenario anterior, intactos, con la
        topología real del AVL y del BST. Se vuelven a poner en self.
        """
        self._restore_full_state(action.previous_state)
        return {"undone": "load"}

    def first_k_pending(self, k: int) -> tuple[list[Event], int]:
        """Primeros k eventos pendientes de atención, en orden descendente
        de K = (P, M, I).

        Sección 11, primera consulta: "Los primeros k eventos pendientes de
        atención en orden descendente de K. k es entero positivo; si hay
        menos pendientes, se muestran todos los disponibles."

        Decisiones:
        - k <= 0 → ValueError. El enunciado exige "entero positivo", así
            que no se admite 0 ni negativos.
        - Se usa reverse-inorden (derecha, nodo, izquierda) con corte
            temprano: en cuanto se juntan k pendientes, se detiene sin
            visitar más nodos.
        - Devuelve tupla (lista_de_eventos, nodos_examinados). El enunciado
            exige reportar la cantidad de nodos del AVL examinados.
        """
        if k <= 0:
            raise ValueError("k must be a positive integer")

        result = []
        counter = [0]
        self._collect_k_pending(self.avl_tree.root, k, result, counter)
        return result, counter[0]

    def _collect_k_pending(self, node, k, result, counter):
        """AUXILIAR: reverse-inorden con corte. Primero derecha (K alto),
        luego el nodo, luego izquierda (K bajo). Corta en cuanto result
        tiene k elementos."""
        if node is None or len(result) >= k:
            return

        self._collect_k_pending(node.right_son, k, result, counter)
        if len(result) >= k:
            return

        counter[0] += 1
        if node.event.attention_status == AttentionStatus.PENDING:
            result.append(node.event)

        self._collect_k_pending(node.left_son, k, result, counter)

    def events_in_magnitude_range(self, min_mag: float, max_mag: float) -> tuple[list[Event], int]:
        """Eventos activos con min_mag <= M <= max_mag (inclusivo), en orden
        ascendente de K.

        Sección 11, segunda consulta: "Eventos dentro de un intervalo
        inclusivo de magnitud."

        Decisiones:
        - min_mag > max_mag → ValueError. Rango inválido.
        - No se puede podar el árbol: K ordena por PRIORIDAD antes que por
            magnitud, así que una rama con prioridad baja puede contener
            cualquier magnitud. Se recorre el árbol completo (inorden).
        - Devuelve tupla (lista_de_eventos, nodos_examinados). El enunciado
            exige reportar la cantidad de nodos del AVL examinados.
        """
        if min_mag > max_mag:
            raise ValueError("min_mag cannot be greater than max_mag")

        result = []
        counter = [0]
        self._collect_by_magnitude(self.avl_tree.root, min_mag, max_mag, result, counter)
        return result, counter[0]

    def _collect_by_magnitude(self, node, min_mag, max_mag, result, counter):
        """AUXILIAR: inorden completo (izquierda, nodo, derecha). Cada nodo
        no vacío cuenta como examinado."""
        if node is None:
            return
        counter[0] += 1
        self._collect_by_magnitude(node.left_son, min_mag, max_mag, result, counter)
        if min_mag <= node.event.magnitude <= max_mag:
            result.append(node.event)
        self._collect_by_magnitude(node.right_son, min_mag, max_mag, result, counter)

    def events_by_depth_and_date(self, max_depth: float, min_date: datetime, max_date: datetime) -> tuple[list[Event], int]:
        """Eventos activos con depth <= max_depth Y min_date <= occurred_at <=
        max_date (ambos límites inclusivos), en orden ascendente de K.

        Sección 11, segunda consulta (segunda mitad): "eventos con profundidad
        del hipocentro menor o igual a un límite dentro de un intervalo
        inclusivo de fechas."

        Decisiones:
        - min_date > max_date → ValueError. Mismo criterio que
        events_in_magnitude_range con min_mag > max_mag.
        - max_depth no se valida aquí (podría venir negativo): los rangos de
        los datos ya los valida el schema de pydantic, igual que el resto
        de Scenario.
        - No se puede podar el árbol: ni depth ni occurred_at forman parte de
        K = (P, M, I), ni siquiera en segundo lugar (a diferencia de la
        magnitud, que sí es parte de K aunque no mande el orden). No hay
        ninguna relación entre la posición de un nodo y estos dos datos.
        Se recorre el árbol completo (inorden).
        - min_date/max_date se normalizan con _as_utc antes de comparar,
        igual que ya hace update_simulation_clock y _validate_report con
        fechas que entran desde afuera: así no falla si llegan sin zona
        horaria o en otra zona distinta a la del evento guardado.
        - Devuelve tupla (lista_de_eventos, nodos_examinados), igual que las
        otras consultas de esta sección (el enunciado lo exige para todas).
        """
        min_date = self._as_utc(min_date)
        max_date = self._as_utc(max_date)

        if min_date > max_date:
            raise ValueError("min_date cannot be greater than max_date")

        result = []
        counter = [0]
        self._collect_by_depth_and_date(self.avl_tree.root, max_depth, min_date, max_date, result, counter)
        return result, counter[0]

    def _collect_by_depth_and_date(self, node, max_depth, min_date, max_date, result, counter):
        """AUXILIAR: inorden completo (izquierda, nodo, derecha). Cada nodo
        no vacío cuenta como examinado."""
        if node is None:
            return
        counter[0] += 1
        self._collect_by_depth_and_date(node.left_son, max_depth, min_date, max_date, result, counter)
        event = node.event
        if event.depth <= max_depth and min_date <= event.occurred_at <= max_date:
            result.append(event)
        self._collect_by_depth_and_date(node.right_son, max_depth, min_date, max_date, result, counter)

    def costly_access_events(self) -> list[dict]:
        """Eventos activos de prioridad alta con acceso costoso.

        Sección 11, última consulta: "Eventos de prioridad alta con acceso
        costoso, indicando profundidad del nodo, límite y número de nodos
        visitados en su búsqueda por clave."
        Sección 9: un evento de prioridad alta (P = 3) tiene acceso costoso
        cuando su profundidad en el AVL es ESTRICTAMENTE mayor que L.

        Es un wrapper de avl_tree.costly_access(L): el árbol hace el
        recorrido, pero no conoce L (solo recibe un número), así que no
        puede decir con qué límite comparó. Scenario sí lo conoce y lo
        agrega a cada resultado.

        Devuelve una lista de dicts, uno por evento con acceso costoso:
            {"event": Event, "depth": int, "visited": int, "limit": int}
        - depth: profundidad del nodo (raíz = 0).
        - visited: nodos visitados al buscarlo por clave = depth + 1.
        - limit: el L vigente con el que se comparó.
        Lista vacía = ningún evento de prioridad alta supera L.

        Se lee self.L en el momento de la consulta, así que si el usuario
        cambia L (change_parameters) la siguiente consulta ya usa el nuevo.
        Costo: O(n), recorre todo el árbol."""
        limit = self.L
        result = self.avl_tree.costly_access(limit)
        for item in result:
            item["limit"] = limit
        return result

    def verify_structure(self) -> dict:
        """Opción "Verificar estructura" (sección 14), disponible en ambos
        modos.

        Es un wrapper de avl_tree.audit(): el árbol revisa TODO (orden
        global por K contra los límites de todos los ancestros, unicidad
        de ids, ciclos o nodos compartidos, punteros parent, alturas y
        factores de balance recalculados contra los guardados). Lo que
        agrega Scenario es el modo actual:
        - Modo NORMAL → require_balance=True: un factor fuera de {-1, 0, 1}
          es un error.
        - Modo STRESS → require_balance=False: el desbalance se informa
          como "expected" (esperado), distinto de los errores de orden o
          de metadatos, como pide la sección 14.

        Devuelve un dict pensado para que la interfaz lo muestre directo:
            {
              "mode": "Normal" | "Stress",
              "checked_nodes": int,          # eventos activos revisados
              "is_valid": bool,              # True si no hay ningún "error"
              "is_avl": bool,                # True si no hay ningún desbalance
              "error_count": int,            # problemas con severity "error"
              "expected_count": int,         # desbalances esperados (estrés)
              "inconsistent_event_ids": [int],  # un id por evento con error
              "issues": [ {event_id, type, severity, detail}, ... ],
            }
        `issues` es la lista tal cual la devuelve audit(); todos sus
        valores son datos simples (listos para JSON). Un mismo evento puede
        tener varios problemas (por ejemplo altura y factor), por eso
        inconsistent_event_ids los agrupa sin repetir.

        `is_valid` es lo que debe consultar la recuperación global antes
        de volver a modo normal (sección 8: "El retorno al modo normal solo
        se completa cuando la auditoría confirma el equilibrio"): en ese
        momento se exige is_valid e is_avl.
        Costo: O(n)."""
        require_balance = (self.mode == Mode.NORMAL)
        issues = self.avl_tree.audit(require_balance=require_balance)

        errors = [issue for issue in issues if issue["severity"] == "error"]
        expected = [issue for issue in issues if issue["severity"] == "expected"]

        # Ids de eventos con errores reales, sin repetir y en orden de
        # aparición (None = problema global, por ejemplo el tamaño).
        inconsistent_ids = []
        for issue in errors:
            event_id = issue["event_id"]
            if event_id is not None and event_id not in inconsistent_ids:
                inconsistent_ids.append(event_id)

        return {
            "mode": self.mode.value,
            "checked_nodes": len(self.avl_tree),
            "is_valid": len(errors) == 0,
            "is_avl": not any(issue["type"] == "imbalance" for issue in issues),
            "error_count": len(errors),
            "expected_count": len(expected),
            "inconsistent_event_ids": inconsistent_ids,
            "issues": issues,
        }

    """==============================================="""
    """========RECUPERACIÓN GLOBAL (SECCIÓN 8)========"""
    """==============================================="""

    def recover_balance(self) -> dict:
        """Recuperación global del AVL (sección 8) como UNA acción que se
        puede deshacer (sección 13).

        Pasos:
        1. Foto de la forma del árbol ANTES de rotar
           (avl_tree.snapshot_topology). Guardar solo la raíz no basta:
           las rotaciones cambian los enlaces de esos mismos nodos.
        2. Reparar SOLO con rotaciones (avl_tree.recover_balance), sin
           vaciar ni reconstruir el árbol. Funciona con desbalances > 2.
        3. Capturar lo que sumó a las métricas (avl_tree.last_rotation_delta)
           para restarlo al deshacer.
        4. Auditar (verify_structure). La sección 8 dice: "El retorno al
           modo normal solo se completa cuando la auditoría confirma el
           equilibrio". Por eso el modo pasa a NORMAL solo si la auditoría
           no encontró errores ni desbalances.
        5. Apilar GlobalRecoveryAction(snapshot, delta, modo_anterior), solo
           si algo cambió (hubo rotaciones o cambió el modo), igual que
           update_simulation_clock no apila un cambio que no cambió nada.

        El BST no se toca: es el árbol de comparación, nunca rota.
        La sección 8 también pide pausar el procesamiento de reportes: aquí
        no hay procesamiento continuo en el backend (cada paso es una
        petición), así que la interfaz debe detener su ciclo antes de
        llamar a esta operación.

        _undo_global_recovery (ya existía) la deshace: restore_topology +
        revert_rotation_metrics + modo anterior.

        Devuelve un dict para mostrar en la interfaz:
            {"previous_mode", "mode", "cases", "elementary_rotations",
             "rotations": [{"case", "event_id", "balance_factor",
                            "rotations"}, ...],
             "rotation_delta", "audit" (lo de verify_structure),
             "recorded" (True si se apiló la acción)}
        Costo: O(n) + rotaciones."""
        previous_mode = self.mode

        # 1. Foto ANTES de tocar el árbol.
        snapshot = self.avl_tree.snapshot_topology()

        # 2. Reparar con rotaciones.
        rotations = self.avl_tree.recover_balance()

        # 3. Delta de métricas de esta operación.
        rotation_delta = self.avl_tree.last_rotation_delta()

        # 4. Solo se vuelve a modo normal si la auditoría lo confirma.
        audit = self.verify_structure()
        if audit["is_valid"] and audit["is_avl"] and self.mode != Mode.NORMAL:
            self.mode = Mode.NORMAL
            audit = self.verify_structure()  # el reporte final ya en modo normal

        # 5. Apilar solo si hubo cambios.
        recorded = bool(rotations) or self.mode != previous_mode
        if recorded:
            self.undo_stack.push(GlobalRecoveryAction(snapshot, rotation_delta, previous_mode))

        return {
            "previous_mode": previous_mode.value,
            "mode": self.mode.value,
            "cases": len(rotations),
            "elementary_rotations": sum(len(entry["rotations"]) for entry in rotations),
            "rotations": rotations,
            "rotation_delta": rotation_delta,
            "audit": audit,
            "recorded": recorded,
        }

    """==============================================="""
    """====ESTADO COMPLETO Y CARGA (SECCIONES 12-13)==="""
    """==============================================="""

    # ESTADO COMPLETO DEL ESCENARIO
    #
    # Es todo lo que reemplaza una carga y lo que guarda LoadAction para
    # poder deshacerla: AVL (estructura real), BST (estructura real),
    # event_index, archived_history, eliminated_IDs, referenced_by, zones,
    # stations, report_queue, reloj, L, W, R, T, mode y metrics.
    #
    # Decisión: se guardan los OBJETOS ORIGINALES, no copias profundas.
    # - Es seguro porque una carga NUNCA modifica el estado viejo: construye
    #   objetos nuevos y los asigna a self (_restore_full_state). El estado
    #   viejo queda intacto dentro de LoadAction, con su topología exacta
    #   (son los mismos nodos, con los mismos enlaces y alturas).
    # - Es NECESARIO conservar la identidad: las acciones apiladas ANTES de
    #   la carga guardan referencias a nodos y eventos reales (por ejemplo
    #   MassArchiveAction guarda archived_root y former_parent, que son
    #   AVLNode del árbol). Si se restaurara una copia profunda, esos nodos
    #   ya no estarían en el árbol restaurado y deshacer el archivo lo
    #   rompería.
    # - Memoria: O(1) por la foto (solo referencias), en vez de O(n).
    #
    # El reloj se guarda como VALOR (self.simulation_clock en ese instante)
    # y se restaura con el setter, igual que ClockAdvanceAction. Guardar el
    # ancla monotónica vieja haría que, al deshacer, el reloj "saltara" lo
    # que duró el escenario cargado.
    #
    # La pila de deshacer NO es parte del estado: es la historia. La
    # LoadAction se apila encima de las acciones anteriores, y al deshacer
    # la carga esas acciones vuelven a aplicar sobre el estado restaurado.

    def _snapshot_full_state(self) -> dict:
        """AUXILIAR: foto del estado operativo completo (ver arriba)."""
        return {
            "avl_tree": self.avl_tree,
            "bst_tree": self.bst_tree,
            "event_index": self.event_index,
            "archived_history": self.archived_history,
            "eliminated_IDs": self.eliminated_IDs,
            "referenced_by": self.referenced_by,
            "zones": self.zones,
            "stations": self.stations,
            "report_queue": self.report_queue,
            "simulation_clock": self.simulation_clock,
            "L": self.L,
            "W": self.W,
            "R": self.R,
            "T": self.T,
            "mode": self.mode,
            "metrics": self.metrics,
        }

    def _restore_full_state(self, state: dict) -> None:
        """AUXILIAR: reemplaza el estado operativo por el de `state` (un
        dict con la forma de _snapshot_full_state). La usan load_scenario
        (para poner el estado nuevo) y _undo_load (para volver al viejo).
        No toca undo_stack. Mantiene que self.metrics sea el MISMO dict que
        usa self.avl_tree (una sola fuente de verdad para las rotaciones)."""
        self.avl_tree = state["avl_tree"]
        self.bst_tree = state["bst_tree"]
        self.event_index = state["event_index"]
        self.archived_history = state["archived_history"]
        self.eliminated_IDs = state["eliminated_IDs"]
        self.referenced_by = state["referenced_by"]
        self.zones = state["zones"]
        self.stations = state["stations"]
        self.report_queue = state["report_queue"]
        self.simulation_clock = state["simulation_clock"]  # setter: reinicia el ancla
        self.L = state["L"]
        self.W = state["W"]
        self.R = state["R"]
        self.T = state["T"]
        self.mode = state["mode"]
        self.metrics = state["metrics"]
        self.avl_tree.metrics = self.metrics

    def load_scenario(self, data: dict) -> dict:
        """Carga un escenario desde un archivo JSON (sección 12) como UNA
        acción que se puede deshacer (sección 13).

        Recibe el JSON YA PARSEADO (dict). Leer el archivo que el usuario
        elige en el explorador y hacer json.loads le toca al router/front.

        Regla general: validar TODO primero y aplicar después. El estado
        nuevo se construye en objetos nuevos; self no se toca hasta que
        todo valida. Si algo falla se lanza ValueError con el primer error
        (dónde está y por qué) y el escenario actual queda igual.

        Si todo valida:
        1. previous_state = self._snapshot_full_state()
        2. self._restore_full_state(estado_nuevo)
        3. self.undo_stack.push(LoadAction(previous_state))

        ESQUEMA DEL ARCHIVO (decisión del equipo, sección 12):
        {
          "load_mode": "insertions" | "topology",        (obligatorio)
          "simulation_clock": "2026-09-07T12:00:00Z",    (opcional)
          "parameters": {"L": 3, "W": 48, "R": 40, "T": 72},  (opcional)
          "zones": [{"name", "x_min", "x_max", "y_min", "y_max",
                     "is_populated"}],                   (opcional)
          "stations": [{"station_id", "x", "y"}],        (opcional)
          ... y lo propio de cada modo (ver abajo).
        }
        Lo opcional que no venga se HEREDA del escenario actual (la sección
        9 permite configurar L "antes de cargar los datos"). Lo heredado se
        informa en "inherited".

        Modo "insertions":
          "events": [{"event_id", "magnitude", "depth", "x", "y",
                      "occurred_at", "station_id"}, ...]
          Se insertan en ese orden, con balanceo activo, en un AVL y un BST
          (create_event: revisión 1, pendiente, asociaciones). Queda en modo
          NORMAL. Sin histórico, eliminados ni cola. Las métricas empiezan
          en cero más las rotaciones de la propia carga.

        Modo "topology" (el guardado estructural completo):
          "avl": {"root_id": int | null,
                  "nodes": [{"event_id", "magnitude", "depth", "x", "y",
                             "occurred_at", "revision", "stations": [ids],
                             "attention_status": "pending" | "reviewed",
                             "priority", "height", "balance_factor",
                             "left_id": int | null, "right_id": int | null,
                             "reference_id" (opcional, se verifica)}]},
          "archived": [{mismos datos del evento, sin enlaces}],  (opcional)
          "eliminated_ids": [int],                                (opcional)
          "report_queue": [{"event_id", "revision_num", "station_id",
                            "magnitude", "depth", "x", "y",
                            "occurred_at"}],                      (opcional)
          "mode": "Normal" | "Stress",                            (opcional)
          "metrics": {"LL": 0, ...}                               (opcional)
          La topología se recupera TAL CUAL (sin reinsertar). Las
          asociaciones se reconstruyen con la misma política determinista
          (si el archivo trae reference_id, debe coincidir). El BST se
          reconstruye insertando en preorden del AVL, así queda con la
          misma forma que el AVL cargado.

        Fechas: texto ISO 8601 con zona horaria ("...Z") o datetime.

        Devuelve un resumen: load_mode, mode, cantidades, warnings,
        inherited, y raíz/altura/profundidad máxima/hojas de ambos árboles
        (lo que la sección 12 pide mostrar al terminar la carga)."""
        if not isinstance(data, dict):
            raise self._load_error("archivo", "el contenido debe ser un objeto JSON")

        load_mode = data.get("load_mode")
        if load_mode not in ("insertions", "topology"):
            raise self._load_error(
                "load_mode", f"debe ser 'insertions' o 'topology' (llegó {load_mode!r})"
            )

        general = self._load_general_sections(data)
        if load_mode == "insertions":
            new_state, warnings = self._build_state_from_insertions(data, general)
        else:
            new_state, warnings = self._build_state_from_topology(data, general)

        # Todo validó: ahora sí se aplica.
        previous_state = self._snapshot_full_state()
        self._restore_full_state(new_state)
        self.undo_stack.push(LoadAction(previous_state))

        return {
            "load_mode": load_mode,
            "mode": self.mode.value,
            "active_events": len(self.avl_tree),
            "archived_events": len(self.archived_history),
            "eliminated_ids": len(self.eliminated_IDs),
            "queued_reports": len(self.report_queue),
            "warnings": warnings,
            "inherited": general["inherited"],
            "avl": self._load_tree_summary(self.avl_tree),
            "bst": self._load_tree_summary(self.bst_tree),
        }

    # ---------------- AUXILIARES DE LA CARGA ----------------

    _INSERTION_EVENT_FIELDS = ("event_id", "magnitude", "depth", "x", "y", "occurred_at", "station_id")
    _STORED_EVENT_FIELDS = ("event_id", "magnitude", "depth", "x", "y", "occurred_at",
                            "revision", "stations", "attention_status")
    _TOPOLOGY_NODE_FIELDS = _STORED_EVENT_FIELDS + ("priority", "height", "balance_factor", "left_id", "right_id")
    _REPORT_FIELDS = ("event_id", "revision_num", "station_id", "magnitude", "depth", "x", "y", "occurred_at")
    # Orden en que se informan los errores de la auditoría al cargar
    # (primero referencias y unicidad, luego orden, luego metadatos).
    _AUDIT_ERROR_ORDER = ("reference", "uniqueness", "size", "order", "height", "balance_factor")

    @staticmethod
    def _load_error(where: str, message: str) -> ValueError:
        """AUXILIAR: error de carga con el lugar exacto del problema."""
        return ValueError(f"Carga rechazada. {where}: {message}")

    @staticmethod
    def _load_tree_summary(tree) -> dict:
        """AUXILIAR: raíz, altura, profundidad máxima y hojas (sección 12).
        La profundidad máxima de un árbol es su altura (raíz = 0)."""
        height = tree.height()
        return {
            "root_id": tree.root.event.event_id if tree.root is not None else None,
            "height": height,
            "max_depth": height if height >= 0 else None,
            "leaves": tree.count_leaves(),
        }

    def _load_require(self, raw, fields, where: str) -> None:
        """AUXILIAR: `raw` debe ser un objeto con todos los `fields`."""
        if not isinstance(raw, dict):
            raise self._load_error(where, "debe ser un objeto")
        missing = [field for field in fields if field not in raw]
        if missing:
            raise self._load_error(where, f"faltan campos obligatorios: {', '.join(missing)}")

    def _load_list(self, data: dict, key: str, required: bool = False) -> list:
        """AUXILIAR: lee una lista del archivo ([] si es opcional y no viene)."""
        if key not in data:
            if required:
                raise self._load_error(key, "falta esta sección")
            return []
        value = data[key]
        if not isinstance(value, list):
            raise self._load_error(key, "debe ser una lista")
        return value

    def _load_number(self, value, where: str, field: str, low: float, high: float, one_decimal: bool = True) -> float:
        """AUXILIAR: número finito en [low, high], con máximo un decimal
        (mismo criterio que _check_one_decimal en schemas/report.py)."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise self._load_error(where, f"{field} debe ser un número (llegó {value!r})")
        if not math.isfinite(value):
            raise self._load_error(where, f"{field} debe ser un número finito")
        if not (low <= value <= high):
            raise self._load_error(where, f"{field} = {value} fuera del rango [{low}, {high}]")
        if one_decimal and abs(value * 10 - round(value * 10)) > 1e-9:
            raise self._load_error(where, f"{field} = {value} tiene más de un decimal")
        return round(float(value), 1) if one_decimal else float(value)

    def _load_int(self, value, where: str, field: str, low: int, high: Optional[int] = None) -> int:
        """AUXILIAR: entero (no booleano) en [low, high]."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise self._load_error(where, f"{field} debe ser un entero (llegó {value!r})")
        if value < low or (high is not None and value > high):
            limit = f"[{low}, {high}]" if high is not None else f">= {low}"
            raise self._load_error(where, f"{field} = {value} fuera del rango {limit}")
        return value

    def _load_datetime(self, value, where: str, field: str) -> datetime:
        """AUXILIAR: fecha ISO 8601 con zona horaria y precisión de
        segundos, normalizada a UTC (mismo criterio que ReportCreate)."""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                raise self._load_error(where, f"{field} no es una fecha ISO 8601 válida ({value!r})") from None
        if not isinstance(value, datetime):
            raise self._load_error(where, f"{field} debe ser una fecha ISO 8601")
        if value.tzinfo is None or value.utcoffset() is None:
            raise self._load_error(where, f"{field} debe incluir zona horaria (por ejemplo ...Z)")
        if value.microsecond != 0:
            raise self._load_error(where, f"{field} debe tener precisión de segundos")
        return value.astimezone(timezone.utc)

    def _load_station_id(self, value, where: str, field: str) -> str:
        """AUXILIAR: id de estación, texto no vacío (como StationCreate)."""
        if not isinstance(value, str) or not value:
            raise self._load_error(where, f"{field} debe ser un texto no vacío")
        return value

    def _load_event_values(self, raw: dict, where: str, clock: datetime) -> dict:
        """AUXILIAR: datos físicos de un evento (secciones 3 y 12): id,
        magnitud, profundidad, epicentro y fecha (no posterior al reloj)."""
        values = {
            "event_id": self._load_int(raw["event_id"], where, "event_id", 1, 999999),
            "magnitude": self._load_number(raw["magnitude"], where, "magnitude", -2.0, 10.0),
            "depth": self._load_number(raw["depth"], where, "depth", 0.0, 700.0),
            "x": self._load_number(raw["x"], where, "x", 0.0, 1000.0),
            "y": self._load_number(raw["y"], where, "y", 0.0, 1000.0),
            "occurred_at": self._load_datetime(raw["occurred_at"], where, "occurred_at"),
        }
        if values["occurred_at"] > clock:
            raise self._load_error(
                where, f"occurred_at {values['occurred_at'].isoformat()} es posterior al reloj "
                    f"de simulación {clock.replace(microsecond=0).isoformat()}"
            )
        return values

    def _load_stored_event(self, raw: dict, where: str, clock: datetime) -> dict:
        """AUXILIAR: evento guardado (activo o archivado): datos físicos +
        revisión, estaciones aceptadas y estado de atención."""
        values = self._load_event_values(raw, where, clock)
        values["revision"] = self._load_int(raw["revision"], where, "revision", 1)
        if not isinstance(raw["stations"], list):
            raise self._load_error(where, "stations debe ser una lista de ids de estación")
        values["station_ids"] = [self._load_station_id(s, where, "stations[]") for s in raw["stations"]]
        try:
            values["attention_status"] = AttentionStatus(raw["attention_status"])
        except (ValueError, TypeError):
            raise self._load_error(
                where, f"attention_status debe ser 'pending' o 'reviewed' (llegó {raw['attention_status']!r})"
            ) from None
        return values

    def _load_general_sections(self, data: dict) -> dict:
        """AUXILIAR: reloj, parámetros, zonas y estaciones del archivo. Lo
        que no venga se hereda del escenario actual (en contenedores
        NUEVOS, para no compartir listas/dicts con el estado viejo, que
        queda guardado en LoadAction)."""
        inherited = []

        if "simulation_clock" in data:
            clock = self._load_datetime(data["simulation_clock"], "simulation_clock", "simulation_clock")
        else:
            clock = self.simulation_clock
            inherited.append("simulation_clock")

        params = data.get("parameters", {})
        if not isinstance(params, dict):
            raise self._load_error("parameters", "debe ser un objeto")
        values = {}
        for name in ("L", "W", "R", "T"):
            if name not in params:
                values[name] = getattr(self, name)
                inherited.append(name)
            elif name == "L":
                values["L"] = self._load_int(params["L"], "parameters", "L", 0)
            else:
                value = params[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)) \
                        or not math.isfinite(value) or value <= 0:
                    raise self._load_error("parameters", f"{name} debe ser un número positivo (llegó {value!r})")
                values[name] = value

        if "zones" in data:
            zones = []
            for i, raw in enumerate(self._load_list(data, "zones")):
                where = f"zones[{i}]"
                self._load_require(raw, ("name", "x_min", "x_max", "y_min", "y_max", "is_populated"), where)
                if not isinstance(raw["name"], str):
                    raise self._load_error(where, "name debe ser texto")
                if not isinstance(raw["is_populated"], bool):
                    raise self._load_error(where, "is_populated debe ser true o false")
                for coord in ("x_min", "x_max", "y_min", "y_max"):
                    self._load_number(raw[coord], where, coord, 0.0, 1000.0)
                try:
                    zone = Zone(raw["name"], raw["x_min"], raw["x_max"], raw["y_min"], raw["y_max"], raw["is_populated"])
                except (ValueError, TypeError) as error:
                    raise self._load_error(where, str(error)) from None
                if any(existing.name == zone.name for existing in zones):
                    raise self._load_error(where, f"nombre de zona repetido: {zone.name!r}")
                zones.append(zone)
        else:
            zones = list(self.zones)
            inherited.append("zones")

        if "stations" in data:
            stations = {}
            for i, raw in enumerate(self._load_list(data, "stations")):
                where = f"stations[{i}]"
                self._load_require(raw, ("station_id", "x", "y"), where)
                station_id = self._load_station_id(raw["station_id"], where, "station_id")
                x = self._load_number(raw["x"], where, "x", 0.0, 1000.0)
                y = self._load_number(raw["y"], where, "y", 0.0, 1000.0)
                if station_id in stations:
                    raise self._load_error(where, f"station_id repetido: {station_id!r}")
                stations[station_id] = Station(station_id, x, y)
        else:
            stations = dict(self.stations)
            inherited.append("stations")

        return {"clock": clock, "params": values, "zones": zones,
                "stations": stations, "inherited": inherited}

    @staticmethod
    def _populated(zones: list, x: float, y: float) -> bool:
        """AUXILIAR: misma regla que epicenter_in_populated_zone, pero con
        las zonas del ARCHIVO (no las del escenario actual)."""
        return any(zone.contains(x, y) and zone.is_populated for zone in zones)

    def _build_state_from_insertions(self, data: dict, general: dict) -> tuple[dict, list]:
        """AUXILIAR: modo 1, carga por inserciones. Valida en el orden
        acordado (campos, rangos y fechas, ids únicos, estaciones) y
        construye el estado nuevo en un Scenario TEMPORAL usando
        create_event, para reutilizar exactamente la misma lógica de alta
        (zona poblada, prioridad, AVL con balanceo, BST, event_index y
        asociaciones). self no se toca."""
        events = self._load_list(data, "events", required=True)

        # 1. Campos obligatorios de todos los eventos.
        for i, raw in enumerate(events):
            self._load_require(raw, self._INSERTION_EVENT_FIELDS, f"events[{i}]")

        # 2. Rangos y fechas (no posteriores al reloj).
        parsed = []
        for i, raw in enumerate(events):
            where = f"events[{i}]"
            values = self._load_event_values(raw, where, general["clock"])
            values["station_id"] = self._load_station_id(raw["station_id"], where, "station_id")
            parsed.append(values)

        # 3. Ids únicos (un id duplicado invalida el archivo, sección 12).
        first_position = {}
        for i, values in enumerate(parsed):
            event_id = values["event_id"]
            if event_id in first_position:
                raise self._load_error(
                    f"events[{i}]", f"event_id {event_id} repetido (ya aparece en events[{first_position[event_id]}])"
                )
            first_position[event_id] = i

        # 4. La estación de cada evento debe existir.
        for i, values in enumerate(parsed):
            if values["station_id"] not in general["stations"]:
                raise self._load_error(f"events[{i}]", f"la estación {values['station_id']!r} no existe")

        # Construcción: mismo comparador y mismo orden en AVL (con balanceo)
        # y BST (sin balanceo). Queda en modo NORMAL (sección 12).
        params = general["params"]
        temp = Scenario(zones=general["zones"], stations=general["stations"],
                        simulation_clock=general["clock"], L=params["L"], W=params["W"],
                        R=params["R"], T=params["T"], mode=Mode.NORMAL)
        for values in parsed:
            temp.create_event(
                event_id=values["event_id"], magnitude=values["magnitude"], depth=values["depth"],
                x=values["x"], y=values["y"], occurred_at=values["occurred_at"],
                stations={general["stations"][values["station_id"]]},
            )
        return temp._snapshot_full_state(), []

    def _build_state_from_topology(self, data: dict, general: dict) -> tuple[dict, list]:
        """AUXILIAR: modo 2, carga por topología. Además de lo del modo 1,
        valida la consistencia de la topología. Corta en el primer error.
        Construye todo en objetos nuevos; self no se toca."""
        clock = general["clock"]
        stations = general["stations"]
        zones = general["zones"]
        warnings = []

        avl = data.get("avl")
        if not isinstance(avl, dict) or "root_id" not in avl or "nodes" not in avl:
            raise self._load_error("avl", "debe ser un objeto con 'root_id' y 'nodes'")
        nodes_raw = avl["nodes"]
        if not isinstance(nodes_raw, list):
            raise self._load_error("avl.nodes", "debe ser una lista")
        archived_raw = self._load_list(data, "archived")
        eliminated_raw = self._load_list(data, "eliminated_ids")
        queue_raw = self._load_list(data, "report_queue")

        # 1. Campos obligatorios.
        for i, raw in enumerate(nodes_raw):
            self._load_require(raw, self._TOPOLOGY_NODE_FIELDS, f"avl.nodes[{i}]")
        for i, raw in enumerate(archived_raw):
            self._load_require(raw, self._STORED_EVENT_FIELDS, f"archived[{i}]")
        for i, raw in enumerate(queue_raw):
            self._load_require(raw, self._REPORT_FIELDS, f"report_queue[{i}]")

        # 2. Rangos, fechas y datos guardados de cada evento.
        nodes = []
        for i, raw in enumerate(nodes_raw):
            where = f"avl.nodes[{i}]"
            values = self._load_stored_event(raw, where, clock)
            values["priority"] = self._load_int(raw["priority"], where, "priority", 1, 3)
            values["height"] = self._load_int(raw["height"], where, "height", 0)
            values["balance_factor"] = self._load_int(raw["balance_factor"], where, "balance_factor", -len(nodes_raw), len(nodes_raw))
            for side in ("left_id", "right_id"):
                if raw[side] is not None:
                    self._load_int(raw[side], where, side, 1, 999999)
                values[side] = raw[side]
            values["where"] = where
            values["raw"] = raw
            nodes.append(values)
        archived = []
        for i, raw in enumerate(archived_raw):
            where = f"archived[{i}]"
            values = self._load_stored_event(raw, where, clock)
            if "priority" in raw:
                values["priority"] = self._load_int(raw["priority"], where, "priority", 1, 3)
            values["where"] = where
            values["raw"] = raw
            archived.append(values)
        eliminated = [self._load_int(value, f"eliminated_ids[{i}]", "id", 1, 999999)
                    for i, value in enumerate(eliminated_raw)]

        # 3. Unicidad: un id no puede repetirse ni estar a la vez activo,
        #    archivado o eliminado.
        owner = {}
        for label, items in (("activo", [(v["where"], v["event_id"]) for v in nodes]),
                            ("archivado", [(v["where"], v["event_id"]) for v in archived]),
                            ("eliminado", [(f"eliminated_ids[{i}]", e) for i, e in enumerate(eliminated)])):
            for where, event_id in items:
                if event_id in owner:
                    first_where, first_label = owner[event_id]
                    raise self._load_error(
                        where, f"el id {event_id} ya aparece en {first_where} ({first_label}); "
                            f"no puede estar dos veces ni ser {first_label} y {label} a la vez"
                    )
                owner[event_id] = (where, label)

        # 4. Las estaciones referenciadas deben existir.
        for values in nodes + archived:
            for station_id in values["station_ids"]:
                if station_id not in stations:
                    raise self._load_error(values["where"], f"la estación {station_id!r} no existe")

        # 5. Referencias válidas: root_id y cada left_id/right_id apuntan a
        #    un nodo activo del archivo, o son null.
        by_id = {v["event_id"]: v for v in nodes}
        root_id = avl["root_id"]
        if not nodes:
            if root_id is not None:
                raise self._load_error("avl.root_id", "debe ser null si no hay nodos activos")
        else:
            if root_id is None or isinstance(root_id, bool) or root_id not in by_id:
                raise self._load_error("avl.root_id", f"{root_id!r} no es un nodo activo del archivo")
        for values in nodes:
            for side in ("left_id", "right_id"):
                child = values[side]
                if child is not None and child not in by_id:
                    raise self._load_error(values["where"], f"{side} = {child} no es un nodo activo del archivo")
                if child == values["event_id"]:
                    raise self._load_error(values["where"], f"{side} apunta al propio nodo (ciclo)")

        # 6. Cada nodo en una sola posición: un id no puede ser hijo de dos
        #    padres (ni dos veces del mismo), y la raíz no puede ser hija.
        parent_of = {}
        for values in nodes:
            for side in ("left_id", "right_id"):
                child = values[side]
                if child is None:
                    continue
                if child in parent_of:
                    other_parent, other_side = parent_of[child]
                    raise self._load_error(
                        values["where"], f"el id {child} aparece en dos posiciones: {other_side} de "
                                        f"{other_parent} y {side} de {values['event_id']}"
                    )
                parent_of[child] = (values["event_id"], side)
        if root_id in parent_of:
            raise self._load_error("avl.root_id", f"la raíz {root_id} aparece como hijo de {parent_of[root_id][0]} (ciclo)")

        # 7. Sin ciclos ni nodos sueltos: todos alcanzables desde la raíz.
        reached = set()
        pending = [root_id] if nodes else []
        while pending:
            current = pending.pop()
            if current in reached:
                raise self._load_error("avl", f"ciclo detectado en el nodo {current}")
            reached.add(current)
            for side in ("left_id", "right_id"):
                if by_id[current][side] is not None:
                    pending.append(by_id[current][side])
        unreached = sorted(set(by_id) - reached)
        if unreached:
            raise self._load_error(
                "avl", f"los nodos {unreached} no son alcanzables desde la raíz (forman un ciclo o están desconectados)"
            )

        # 8. Crear los eventos (objetos nuevos) y verificar que la prioridad
        #    guardada coincida con la calculada con las zonas del archivo
        #    (sección 4).
        def make_event(values):
            event = Event(
                event_id=values["event_id"], magnitude=values["magnitude"], depth=values["depth"],
                x=values["x"], y=values["y"], occurred_at=values["occurred_at"],
                revision=values["revision"],
                stations={stations[s] for s in values["station_ids"]},
                is_in_populated_zone=self._populated(zones, values["x"], values["y"]),
            )
            event.attention_status = values["attention_status"]
            if "priority" in values and values["priority"] != event.priority:
                raise self._load_error(
                    values["where"], f"prioridad guardada {values['priority']} no coincide con la calculada "
                                    f"{event.priority} (sección 4)"
                )
            return event

        active_events = {v["event_id"]: make_event(v) for v in nodes}
        archived_events = {v["event_id"]: make_event(v) for v in archived}

        # 9. Armar la topología EXACTA del archivo (sin reinsertar) con
        #    AVLTree.restore_topology y revisarla con AVLTree.audit: orden
        #    global por K contra todos los ancestros (equivale a que el
        #    inorden salga ordenado), unicidad, punteros parent, alturas
        #    guardadas contra reales.
        avl_nodes = {event_id: AVLNode(event, height=by_id[event_id]["height"])
                    for event_id, event in active_events.items()}
        links = []
        for values in nodes:
            node = avl_nodes[values["event_id"]]
            left = avl_nodes.get(values["left_id"]) if values["left_id"] is not None else None
            right = avl_nodes.get(values["right_id"]) if values["right_id"] is not None else None
            parent_id = parent_of.get(values["event_id"], (None,))[0]
            parent = avl_nodes[parent_id] if parent_id is not None else None
            links.append((node, left, right, parent, values["height"]))

        metrics = self._load_metrics(data)
        tree = AVLTree(metrics=metrics)
        root_node = avl_nodes[root_id] if nodes else None
        tree.restore_topology(AVLTopologySnapshot(root_node, len(nodes), links))

        errors = [issue for issue in tree.audit(require_balance=False) if issue["severity"] == "error"]
        if errors:
            errors.sort(key=lambda issue: self._AUDIT_ERROR_ORDER.index(issue["type"])
                        if issue["type"] in self._AUDIT_ERROR_ORDER else len(self._AUDIT_ERROR_ORDER))
            first = errors[0]
            where = by_id[first["event_id"]]["where"] if first["event_id"] in by_id else "avl"
            raise self._load_error(where, f"{first['type']}: {first['detail']}")

        # 10. Factor de balance guardado contra el real (las alturas ya
        #     se verificaron en el paso 9, así que node.balance_factor es el real).
        for values in nodes:
            real = avl_nodes[values["event_id"]].balance_factor
            if values["balance_factor"] != real:
                raise self._load_error(
                    values["where"], f"factor de balance guardado {values['balance_factor']}, real {real}"
                )

        # 11. Balance y modo. Ordenada y balanceada: se carga (en el modo
        #     del archivo, o el actual si no lo trae). Ordenada pero
        #     desbalanceada: solo con el modo estrés ACTIVADO, y se avisa.
        file_mode = None
        if "mode" in data:
            try:
                file_mode = Mode(data["mode"])
            except (ValueError, TypeError):
                raise self._load_error("mode", f"debe ser 'Normal' o 'Stress' (llegó {data['mode']!r})") from None
        unbalanced = [node.event.event_id for node in tree.unbalanced_nodes()]
        if unbalanced:
            if self.mode != Mode.STRESS:
                raise self._load_error(
                    "avl", f"la topología está ordenada pero desbalanceada (nodos {unbalanced}); "
                        f"solo se puede cargar con el modo estrés activado"
                )
            if file_mode == Mode.NORMAL:
                raise self._load_error(
                    "mode", f"el archivo declara modo Normal pero la topología está desbalanceada (nodos {unbalanced})"
                )
            new_mode = Mode.STRESS
            warnings.append(f"Topología desbalanceada (nodos {unbalanced}): cargada en modo estrés")
        else:
            new_mode = file_mode if file_mode is not None else self.mode

        # 12. Cola de reportes, en su orden original.
        queue = Queue()
        for i, raw in enumerate(queue_raw):
            where = f"report_queue[{i}]"
            values = self._load_event_values(raw, where, clock)
            revision = self._load_int(raw["revision_num"], where, "revision_num", 1)
            station_id = self._load_station_id(raw["station_id"], where, "station_id")
            if station_id not in stations:
                raise self._load_error(where, f"la estación {station_id!r} no existe")
            queue.enqueue(Report(values["event_id"], revision, stations[station_id], values["magnitude"],
                                values["depth"], values["x"], values["y"], values["occurred_at"]))

        # Construcción final en un Scenario TEMPORAL, para reconstruir las
        # asociaciones con la misma política determinista de siempre.
        # El BST se arma insertando en preorden del AVL: así queda con la
        # misma forma que la topología cargada.
        bst = BSTTree()
        for event in tree.preorder():
            bst.insert(event)
        params = general["params"]
        temp = Scenario(
            metrics=metrics, avl_tree=tree, bst_tree=bst,
            event_index={event_id: avl_nodes[event_id] for event_id in active_events},
            stations=stations, zones=zones, eliminated_IDs=set(eliminated),
            archived_history=archived_events, referenced_by={}, simulation_clock=clock,
            L=params["L"], W=params["W"], R=params["R"], T=params["T"], mode=new_mode,
            report_queue=queue,
        )
        for event in temp._all_active_and_archived_events():
            temp._recalculate_reference(event)

        # 13. Si el archivo guardó las referencias, deben coincidir con las
        #     reconstruidas (los valores derivados se verifican al cargar).
        for values in nodes + archived:
            if "reference_id" in values["raw"]:
                event = temp._find_any_event(values["event_id"])
                if values["raw"]["reference_id"] != event.reference_id:
                    raise self._load_error(
                        values["where"], f"reference_id guardado {values['raw']['reference_id']!r} no coincide "
                                        f"con el calculado {event.reference_id!r} (sección 7)"
                    )

        return temp._snapshot_full_state(), warnings

    def _load_metrics(self, data: dict) -> dict:
        """AUXILIAR: métricas acumuladas del archivo (enteros >= 0). Las de
        rotación que falten las completa AVLTree en 0."""
        metrics = data.get("metrics", {})
        if not isinstance(metrics, dict):
            raise self._load_error("metrics", "debe ser un objeto")
        loaded = {}
        for name, value in metrics.items():
            if not isinstance(name, str):
                raise self._load_error("metrics", "los nombres de las métricas deben ser texto")
            loaded[name] = self._load_int(value, "metrics", name, 0)
        return loaded














































    def update_station(self, station_id: str, changes: dict) -> Station:
        """This method is called to update the data of a station that already exists"""
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
        """This method deletes a station"""
        self.get_station(station_id)
        del self.stations[station_id]


    """==============================================="""
    """================REPORT METHODS================="""
    """==============================================="""

    # The queue only stores PREPARED reports: enqueueing does not touch
    # events or trees. The decision for each report (section 6 table) is
    # made when processing it, in process_next_report().
    #
    # Team decisions (Sep-29):
    # - Reports with a timestamp later than the clock are rejected at
    #   ENQUEUE time.
    # - A queued report cannot be removed individually; only the whole
    #   queue can be cleared.

    def _validate_report(self, report: Report) -> None:
        """Validations for a report that depend on the scenario state.
        Ranges and formats were already validated by the schema
        (ReportCreate).
        Raises KeyError if the station is not registered, and ValueError
        if the occurrence time is later than the simulation clock."""
        station_id = report.station.station_id
        if self.stations.get(station_id) is not report.station:
            raise KeyError(f"Station '{station_id}' was not found")

        if self._as_utc(report.occurred_at) > self.simulation_clock:
            raise ValueError(
                f"Report for event {report.event_id} occurred after the "
                f"simulation clock ({self.simulation_clock.replace(microsecond=0).isoformat()})"
            )

    def next_report_revision(self, event_id: int, preceding_reports: Optional[list[Report]] = None,) -> int:
        """Return the next revision after the latest queued or staged report.

        If this event has no pending report, continue from its current active
        or archived revision. A new event starts at revision 1.
        """
        queued_and_staged = self.report_queue.items() + (preceding_reports or [])
        for report in reversed(queued_and_staged):
            if report.event_id == event_id:
                return report.revision_num + 1

        node = self.event_index.get(event_id)
        if node is not None:
            return node.event.revision + 1

        archived_event = self.archived_history.get(event_id)
        if archived_event is not None:
            return archived_event.revision + 1

        return 1

    def enqueue_report(self, report: Report) -> int:
        """Append a report to the end of the FIFO queue and return its
        position (1 = the next one to be processed). If the report is not
        valid, raises the exception from _validate_report and the queue
        stays unchanged. O(1)."""
        self._validate_report(report)
        self.report_queue.enqueue(report)
        return len(self.report_queue)

    def enqueue_reports(self, reports: list[Report]) -> int:
        """Enqueue a burst of reports in the order received, atomically:
        first validate ALL of them, and only if every one is valid, enqueue
        them. So an error on report 5 does not leave the first 4 enqueued.
        Returns the position of the first report of the burst. O(N)."""
        for report in reports:
            self._validate_report(report)

        first_position = len(self.report_queue) + 1
        for report in reports:
            self.report_queue.enqueue(report)
        return first_position

    def list_reports(self) -> list[Report]:
        """Copy of the queue in reception order (the first one is the next
        to be processed). It is a copy: modifying the list does not alter
        the queue. O(n)."""
        return self.report_queue.items()

    def clear_report_queue(self) -> int:
        """Discard all pending reports and return how many there were.
        Does not touch events, trees, or the clock.

        PENDING (team decision): for now this is NOT recorded on the undo
        stack. The statement does not list "clear the queue" among the
        section 13 actions, but the queue IS part of the recoverable
        state."""
        return self.report_queue.clear()
    
    """==============================================="""
    """============TREE STATE (VISTAS)================"""
    """==============================================="""

    # Fotos de solo lectura de los árboles para la interfaz (vista del AVL,
    # vista comparativa con el BST, sección 11 y 15). Devuelven diccionarios
    # con datos simples (números, textos, listas, None), listos para JSON.
    #
    # Topología PLANA: root_id + una lista de nodos donde cada nodo nombra a
    # sus vecinos por id (left_id, right_id, parent_id). Es la misma idea del
    # esquema de carga por topología (sección 12), y evita anidar nodos.
    #
    # Cada nodo lleva solo lo necesario para dibujarlo; el detalle completo
    # del evento (estaciones, revisión, asociaciones) se pide con get_event(id).
    # La auditoría NO va aquí: es una operación aparte (avl_tree.audit()).

    def get_avl_state(self) -> dict:
        """Estado actual del AVL activo. Costo O(n)."""
        tree = self.avl_tree
        nodes = []
        self._collect_avl_rows(tree.root, None, 0, nodes)
        return {
            "tree": "AVL",
            "mode": self.mode.value,
            "size": len(tree),
            "root_id": tree.root.event.event_id if tree.root is not None else None,
            "height": tree.height(),
            "leaves": tree.count_leaves(),
            "is_avl": tree.is_avl(),
            "unbalanced_ids": [n.event.event_id for n in tree.unbalanced_nodes()],
            "L": self.L,
            "nodes": nodes,
            "traversals": self._traversal_ids(tree),
            "rotation_metrics": {k: self.metrics.get(k, 0) for k in ROTATION_METRIC_KEYS},
        }

    def _collect_avl_rows(self, node, parent_id, depth, rows):
        """AUXILIAR: preorden recursivo que arma una fila por nodo del AVL.
        La profundidad se lleva como parámetro al bajar (O(1) por nodo), en
        vez de llamar depth_of() en cada nodo (O(profundidad) cada vez).
        Altura y factor de balance se LEEN del nodo: el AVL los guarda."""
        if node is None:
            return
        row = self._event_row(node.event)
        row.update({
            "parent_id": parent_id,
            "left_id": node.left_son.event.event_id if node.left_son else None,
            "right_id": node.right_son.event.event_id if node.right_son else None,
            "depth": depth,
            "height": node.height,
            "balance_factor": node.balance_factor,
            "search_cost": depth + 1,  # nodos visitados al buscarlo por clave (sección 9)
            "costly_access": node.event.priority == 3 and depth > self.L,
        })
        rows.append(row)
        self._collect_avl_rows(node.left_son, row["event_id"], depth + 1, rows)
        self._collect_avl_rows(node.right_son, row["event_id"], depth + 1, rows)

    def get_bst_state(self) -> dict:
        """Estado actual del BST de comparación, con la misma forma que
        get_avl_state para poder dibujarlos y compararlos igual. El BST no
        guarda altura ni padre: se calculan durante el recorrido. Costo O(n)."""
        tree = self.bst_tree
        nodes = []
        height = self._collect_bst_rows(tree.root, None, 0, nodes)
        return {
            "tree": "BST",
            "size": len(tree),
            "root_id": tree.root.event.event_id if tree.root is not None else None,
            "height": height,
            "leaves": tree.count_leaves(),
            "nodes": nodes,
            "traversals": self._traversal_ids(tree),
        }

    def _collect_bst_rows(self, node, parent_id, depth, rows):
        """AUXILIAR: agrega la fila al BAJAR (así la lista queda en preorden)
        y completa altura y factor al REGRESAR de los hijos (como un
        postorden). Devuelve la altura del subárbol (vacío = -1)."""
        if node is None:
            return -1
        row = self._event_row(node.event)
        row.update({
            "parent_id": parent_id,
            "left_id": node.left_son.event.event_id if node.left_son else None,
            "right_id": node.right_son.event.event_id if node.right_son else None,
            "depth": depth,
            "search_cost": depth + 1,
        })
        rows.append(row)
        left_h = self._collect_bst_rows(node.left_son, row["event_id"], depth + 1, rows)
        right_h = self._collect_bst_rows(node.right_son, row["event_id"], depth + 1, rows)
        row["height"] = 1 + max(left_h, right_h)
        row["balance_factor"] = left_h - right_h  # informativo: el BST nunca rota
        return row["height"]

    @staticmethod
    def _event_row(event) -> dict:
        """AUXILIAR: datos del evento que se necesitan para dibujar su nodo."""
        p, m, i = event.key
        return {
            "event_id": i,
            "label": f"SIS-{i:06d}",
            "key": [p, m, i],
            "priority": p,
            "magnitude": m,
            "attention_status": event.attention_status.value,
        }

    @staticmethod
    def _traversal_ids(tree) -> dict:
        """AUXILIAR: recorridos del árbol como listas de ids (no de Event)."""
        return {
            "inorder": [e.event_id for e in tree.inorder()],
            "preorder": [e.event_id for e in tree.preorder()],
            "postorder": [e.event_id for e in tree.postorder()],
            "level_order": [e.event_id for e in tree.level_order()],
        }
