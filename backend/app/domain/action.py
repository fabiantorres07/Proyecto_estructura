from app.domain.event import Event, AttentionStatus
from app.structures.avl_node import AVLNode
from app.structures.avl_tree import AVLTopologySnapshot
from datetime import datetime
from typing import Optional
from app.domain.report import Report

"""Registra la creación de un evento nuevo. Para deshacer solo se necesita el id: basta eliminarlo del índice/árbol."""
class CreationAction:
    def __init__(self, event_id: int):
        self.event_id = event_id

"""Guarda los valores anteriores de los campos que cambia una corrección (magnitud, profundidad, coordenadas, zona poblada, revisión, estado de atención), para poder restaurarlos al deshacer."""
class CorrectionAction:
    def __init__(self, event_id: int, old_magnitude: float, old_depth: float,old_x: float, old_y: float, old_is_in_populated_zone: bool,old_revision: int, old_attention_status: AttentionStatus):
        self.event_id = event_id
        self.old_magnitude = old_magnitude
        self.old_depth = old_depth
        self.old_x = old_x
        self.old_y = old_y
        self.old_is_in_populated_zone = old_is_in_populated_zone
        self.old_revision = old_revision
        self.old_attention_status = old_attention_status

"""Guarda el Event completo que fue eliminado, ya que una vez borrado no queda en ninguna otra estructura; al deshacer se reinserta tal cual."""
class DeletionAction:
    def __init__(self, event: Event):
        self.event = event

"""Guarda la raíz del subárbol que se archivó en bloque, su antiguo padre y de qué lado colgaba, más la lista de ids afectados, para poder reinjertar todo el subárbol en su posición original al deshacer."""
class MassArchiveAction:
    def __init__(self, archived_root: AVLNode, former_parent: Optional[AVLNode], was_left_child: Optional[bool], event_ids: list[int]):
        self.archived_root = archived_root
        self.former_parent = former_parent
        self.was_left_child = was_left_child
        self.event_ids = event_ids

"""Guarda el nombre del parámetro global (L, W, R o T) y su valor anterior, para poder revertir el cambio."""
class ParameterChangeAction:
    def __init__(self, parameter_name: str, old_value: float):
        self.parameter_name = parameter_name
        self.old_value = old_value

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
    def __init__(self, report: Report, queue_position: int, inner_action: Optional[CreationAction | CorrectionAction] = None, confirmed_station_id: Optional[int] = None):
        self.report = report
        self.queue_position = queue_position
        self.inner_action = inner_action
        self.confirmed_station_id = confirmed_station_id