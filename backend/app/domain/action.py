from app.domain.event import Event, AttentionStatus
from app.structures.avl_node import AVLNode
from app.structures.avl_tree import AVLTopologySnapshot
from datetime import datetime
from typing import Optional
from app.domain.report import Report


"CLASE ACTION"
"""Cada tipo de operación se tiene que deshacer por separado. Son diez: crear, corregir, eliminar, archivar rama, cambiar parámetros, avanzar el reloj, cambiar el estado de atención, cargar un escenario, recuperación global y cada paso de la cola."""

"""Cada vez que el usuario hace algo (crear un evento, corregirlo, etc.), el sistema guarda en la pila una nota de lo que se hizo. 
Si el usuario pulsa deshacer, se saca la última nota y se hace lo contrario.
Su rol es solo guardar datos, nada más. Estas clases no hacen nada por sí solas. Scenario es quien crea las notas y quien las usa para deshacer."""

"""CreationAction: solo el id del evento, para poder quitarlo.

CorrectionAction: Acción que representa una corrección manual de un evento activo.

DeletionAction: el evento completo, porque al borrarlo ya no existe en ningún otro lado.

MassArchiveAction: la rama archivada y de dónde colgaba, para volver a pegarla.

ParameterChangeAction: qué parámetro cambió (L, W, R o T) y su valor viejo.

ClockAdvanceAction: la hora vieja del reloj.

AttentionChangeAction: el estado viejo (pendiente o revisado).

LoadAction: una copia de todo el escenario anterior. La regla general es guardar lo mínimo, pero esta es la excepción, porque cargar un archivo reemplaza todo.

GlobalRecoveryAction: una "foto" de la forma del árbol antes de repararlo, para dejarlo idéntico al deshacer.

QueueStepAction: el reporte procesado, su lugar en la cola y la acción interna (crear o corregir) que produjo."""

"""Cada operación necesita guardar cosas distintas para poder deshacerse. Una corrección guarda valores viejos, 
un borrado guarda el evento completo y el reloj guarda una hora."""






class CreationAction:
    """Acción que representa la creación manual de un evento.

    Se apila en Scenario.undo_stack después de que create_event termine
    correctamente. Al deshacer, Scenario debe poder revertir TODO lo que
    la creación cambió, no solo el evento nuevo.

    La versión anterior solo guardaba `event_id`. Eso alcanzaba para
    retirar el evento nuevo del AVL, del BST y de event_index, pero NO
    alcanzaba para restaurar las referencias de otros eventos. Al crear
    B, B puede volverse candidato de eventos X que ya existían (reportes
    tardíos con mayor magnitud), y esos X cambian su referencia. Si al
    deshacer solo quitáramos B, esos X quedarían apuntando a un evento
    que ya no existe: se rompe el invariante de la sección 7.

    Scenario.undo() hace pop de la pila y decide con isinstance()
    qué revertir. Para una CreationAction necesita saber:
      - qué evento retirar (event_id), y
      - a qué referencia volver para cada evento afectado
        (old_references).

    old_references es un dict {event_id: reference_id_anterior}. Incluye
    siempre al evento nuevo (que antes no existía -> None) y a cualquier
    otro evento cuya referencia haya cambiado por culpa de esta creación.
    """

    def __init__(self, event_id: int, old_references: dict[int, int | None]):
        self.event_id = event_id
        self.old_references = old_references

class CorrectionAction:
    """Acción que representa una corrección manual de un evento activo.

    Se apila en Scenario.undo_stack después de que correct_event termine
    correctamente. Al deshacer, Scenario debe poder revertir TODO lo que
    la corrección cambió, no solo los datos del evento.


    La primera versión de CorrectionAction solo guardaba el id del
    evento. Eso era insuficiente por tres razones que aparecieron al
    escribir correct_event:

    1) La corrección modifica varios campos del Event.
       apply_correction() puede cambiar magnitud, profundidad, x, y,
       is_in_populated_zone, revision y attention_status (vuelve a
       PENDING). Para deshacer hay que restaurar TODOS esos valores.
       Con solo el id no se puede: no hay de dónde sacar los valores
       viejos. Por eso se guardan campo por campo.

    2) La corrección puede cambiar la clave K del evento.
       Si cambia magnitud, profundidad o zona poblada, la prioridad
       cambia, y con ella la clave K = (P, M, I). Eso obliga a retirar
       el nodo del AVL y del BST y reinsertarlo. Al deshacer hay que
       hacer lo mismo pero al revés: retirar con la clave ACTUAL y
       reinsertar con la clave VIEJA.
       OJO: la clave vieja NO se guarda en la acción. Se reconstruye
       sola al restaurar old_magnitude, old_depth y
       old_is_in_populated_zone, porque Event.priority y Event.key son
       @property: en cuanto cambias los atributos, la clave se recalcula.
       Guardarla sería duplicar información.

    3) La corrección puede mover las asociaciones (sección 7).
       Si sube la magnitud o cambia la fecha, B puede volverse candidato
       de eventos que antes no lo tenían como referencia. Y si baja la
       magnitud o se aleja del epicentro, B puede dejar de ser candidato
       de eventos que sí lo tenían como referencia. Ambos grupos hay que
       recalcularlos.
       Para deshacer, hay que restaurar las referencias que tenían ANTES
       de la corrección. Eso se guarda en old_references, con el mismo
       patrón que usa CreationAction: un dict {event_id: reference_id}
       con la foto previa de cada evento afectado.

    ──────────────────────────────────────────────────────────────
    ¿Por qué lo necesita Scenario?
    ──────────────────────────────────────────────────────────────

    Scenario.undo() hace pop de la pila y decide con isinstance() qué
    revertir. Para una CorrectionAction necesita saber:

      - qué evento corregir (event_id),
      - a qué valores volver (old_magnitude, old_depth, old_x, old_y,
        old_is_in_populated_zone, old_revision, old_attention_status), y
      - a qué referencias volver para cada evento afectado
        (old_references).

    Lo que NO se guarda, y por qué:
      - old_key: se reconstruye sola al restaurar los valores viejos.
      - old_stations: apply_correction() no toca las estaciones, así
        que no cambian y no hay nada que restaurar.
      - una copia completa del Event: no hace falta, los campos que sí
        cambian son inmutables (float, bool, int, enum) y basta con
        guardarlos sueltos. No hay listas ni sets que se puedan mutar
        por accidente.

    ──────────────────────────────────────────────────────────────
    Resumen
    ──────────────────────────────────────────────────────────────

    Guarda solo lo mínimo necesario para volver al estado exacto
    anterior: los campos que apply_correction pudo haber tocado, y las
    referencias previas de los eventos cuyas asociaciones cambiaron.
    """

    def __init__(
        self,
        event_id: int,
        old_magnitude: float,
        old_depth: float,
        old_x: float,
        old_y: float,
        old_occurred_at: datetime,
        old_is_in_populated_zone: bool,
        old_revision: int,
        old_attention_status,
        old_references: dict[int, int | None],
        counter_delta: Optional[dict[str, int]] = None,
    ):
        self.event_id = event_id
        self.old_magnitude = old_magnitude
        self.old_depth = old_depth
        self.old_x = old_x
        self.old_y = old_y
        self.old_occurred_at = old_occurred_at
        self.old_is_in_populated_zone = old_is_in_populated_zone
        self.old_revision = old_revision
        self.old_attention_status = old_attention_status
        self.old_references = old_references
        # Lo que esta corrección sumó a los contadores de la sección 14
        # ({"corrections_accepted": 1}). Se resta al deshacer.
        self.counter_delta = counter_delta or {}


class ReactivationAction:
    """Acción que representa la reactivación de un evento archivado por
    un reporte con revisión mayor (sección 6).

    Se apila en Scenario.undo_stack dentro de archived_reactivation().
    process_next_report la saca con pop() y la mete dentro del
    QueueStepAction, igual que ya hace con CreationAction y
    CorrectionAction.

    Diferencias con CorrectionAction:
    - Mismos campos old_* + old_references, pero el "antes" del evento
      no es estar en el AVL: es estar en archived_history.
    - Al deshacer, el evento NO se reubica dentro del árbol: sale del
      AVL/BST/event_index y vuelve a archived_history (ver
      _undo_reactivation en Scenario).

    Por qué es clase aparte y no reutilizar CorrectionAction: el criterio
    del proyecto nunca fue "qué datos guarda" sino "qué tiene que hacer
    undo() con ellos", y ahí sí son distintos.
    """

    def __init__(
        self,
        event_id: int,
        old_magnitude: float,
        old_depth: float,
        old_x: float,
        old_y: float,
        old_occurred_at: datetime,
        old_is_in_populated_zone: bool,
        old_revision: int,
        old_attention_status,
        old_references: dict[int, int | None],
        counter_delta: Optional[dict[str, int]] = None,
    ):
        self.event_id = event_id
        self.old_magnitude = old_magnitude
        self.old_depth = old_depth
        self.old_x = old_x
        self.old_y = old_y
        self.old_occurred_at = old_occurred_at
        self.old_is_in_populated_zone = old_is_in_populated_zone
        self.old_revision = old_revision
        self.old_attention_status = old_attention_status
        self.old_references = old_references
        # Lo que esta reactivación sumó a los contadores de la sección 14
        # ({"corrections_accepted": 1}). Se resta al deshacer.
        self.counter_delta = counter_delta or {}


class DeletionAction:
    """Guarda el Event completo que fue eliminado, ya que una vez borrado
    no queda en ninguna otra estructura; al deshacer se reinserta tal cual.
    También guarda las referencias viejas de los eventos afectados por la
    eliminación (los que tenían al eliminado como referencia), para poder
    restaurarlas al deshacer."""
    def __init__(self, event: Event, old_references: dict[int, int | None]):
        self.event = event
        self.old_references = old_references

class MassArchiveAction:
    """Guarda la raíz del subárbol que se archivó en bloque, su antiguo
    padre y de qué lado colgaba, más la lista de ids afectados, para poder
    reinjertar todo el subárbol en su posición original al deshacer.

    rotation_delta: lo que sumó detach_subtree a las métricas de rotación.
    Se resta al deshacer con avl_tree.revert_rotation_metrics(delta).

    counter_delta: lo que sumó el archivo a los contadores de la sección 14
    ({"mass_archives": 1, "archived_events": tamaño de la rama}). Se resta
    al deshacer con Scenario._revert_counters(delta).
    """
    def __init__(self, archived_root: AVLNode, former_parent: Optional[AVLNode],
                 was_left_child: Optional[bool], event_ids: list[int],
                 rotation_delta: dict = None, counter_delta: dict = None):
        self.archived_root = archived_root
        self.former_parent = former_parent
        self.was_left_child = was_left_child
        self.event_ids = event_ids
        self.rotation_delta = rotation_delta or {}
        self.counter_delta = counter_delta or {}
        
class ParameterChangeAction:
    """Guarda el nombre del parámetro global (L, W, R o T), su valor
    anterior, y — cuando el parámetro afecta las asociaciones (W o R) —
    la foto de las referencias de todos los eventos activos y archivados
    antes de recalcularlas.

    ¿Por qué old_references?
    Cambiar W o R redefine qué eventos son candidatos entre sí. No hay
    filtro posible: cualquier evento puede ganar o perder candidatos.
    Por eso, al cambiar W o R, Scenario recalcula la referencia de TODOS
    los eventos activos y archivados. Para poder deshacer, hay que
    guardar el reference_id que tenía cada uno antes del recálculo.

    Para L y T no aplica: L solo afecta la marca de "acceso costoso"
    (no toca referencias) y T solo afecta a futuras operaciones de
    archivo (las ramas ya archivadas se quedan como están). En esos
    casos old_references queda en None.
    """

    def __init__(self, parameter_name: str, old_value: float,
                 old_references: dict[int, int | None] = None):
        self.parameter_name = parameter_name
        self.old_value = old_value
        self.old_references = old_references

class ClockAdvanceAction:
    """Guarda el valor anterior del reloj de simulación antes de avanzarlo, para poder retrocederlo al deshacer."""
    def __init__(self, old_clock: datetime):
        self.old_clock = old_clock

"""Guarda el estado de atención anterior de un evento antes de un cambio manual de atención, para poder restaurarlo."""
class AttentionChangeAction:
    def __init__(self, event_id: int, old_attention_status: AttentionStatus):
        self.event_id = event_id
        self.old_attention_status = old_attention_status

"""Guarda el estado previo completo del escenario antes de cargar uno nuevo (por archivo o topología). Es una excepción a la regla de costo proporcional porque la acción misma reemplaza todo el estado."""
class LoadAction:
    def __init__(self, previous_state):
        self.previous_state = previous_state

class GlobalRecoveryAction:
    """Guarda cómo estaba el AVL antes de una recuperación global, para
    poder dejarlo exactamente igual al deshacer (sección 13).

    - topology_snapshot: copia de la forma del árbol tomada con
      avl_tree.snapshot_topology() ANTES de recuperar. Guardar solo la raíz
      anterior no basta: las rotaciones cambian los enlaces de esos mismos
      nodos, así que la raíz vieja ya no describe la forma vieja.
    - rotation_delta: lo que sumó la recuperación a las métricas de
      rotación (avl_tree.last_rotation_delta() DESPUÉS de recuperar), para
      restarlo al deshacer con avl_tree.revert_rotation_metrics(delta).
    - previous_mode: modo en que estaba el escenario antes (normalmente
      Mode.STRESS), por si la recuperación termina volviendo a modo normal.
      Sin anotación de tipo a propósito: importar Mode desde scenario.py
      crearía un import circular cuando Scenario importe estas acciones.

    Flujo esperado en Scenario:
        snapshot = self.avl_tree.snapshot_topology()
        self.avl_tree.recover_balance()
        action = GlobalRecoveryAction(snapshot, self.avl_tree.last_rotation_delta(), self.mode)
        self.undo_stack.push(action)
    Al deshacer:
        self.avl_tree.restore_topology(action.topology_snapshot)
        self.avl_tree.revert_rotation_metrics(action.rotation_delta)
        self.mode = action.previous_mode
    """
    def __init__(self, topology_snapshot: AVLTopologySnapshot, rotation_delta: dict[str, int], previous_mode=None):
        self.topology_snapshot = topology_snapshot
        self.rotation_delta = rotation_delta
        self.previous_mode = previous_mode

"""Guarda el reporte procesado y la posición que ocupaba en la cola, junto con la acción interna que generó ese paso (creación o corrección) y la estación confirmada si aplicó, para poder revertir el procesamiento de ese reporte y devolverlo a su posición en la cola."""
class QueueStepAction:
    def __init__(
        self,
        report: Report,
        queue_position: int,
        inner_action: Optional[CreationAction | CorrectionAction | ReactivationAction] = None,
        confirmed_station_id: Optional[int] = None,
        counter_delta: Optional[dict[str, int]] = None,
    ):
        self.report = report
        self.queue_position = queue_position
        self.inner_action = inner_action
        self.confirmed_station_id = confirmed_station_id
        # Lo que sumó el PROPIO paso a los contadores de la sección 14
        # (conflicto o reporte descartado). Una corrección o reactivación
        # interna guarda su conteo en inner_action, no aquí.
        self.counter_delta = counter_delta or {}