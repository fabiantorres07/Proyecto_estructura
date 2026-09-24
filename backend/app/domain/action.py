from app.domain.event import Event, AttentionStatus
from app.structures.avl_node import AVLNode
from datetime import datetime
from typing import Optional
from app.domain.report import Report


class CreationAction:
    def __init__(self, event_id: int):
        self.event_id = event_id


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


class DeletionAction:
    def __init__(self, event: Event):
        self.event = event


class MassArchiveAction:
    def __init__(self, archived_root: AVLNode, former_parent: Optional[AVLNode], was_left_child: Optional[bool], event_ids: list[int]):
        self.archived_root = archived_root
        self.former_parent = former_parent
        self.was_left_child = was_left_child
        self.event_ids = event_ids


class ParameterChangeAction:
    def __init__(self, parameter_name: str, old_value: float):
        self.parameter_name = parameter_name
        self.old_value = old_value


class ClockAdvanceAction:
    def __init__(self, old_clock: datetime):
        self.old_clock = old_clock


class AttentionChangeAction:
    def __init__(self, event_id: int, old_attention_status: AttentionStatus):
        self.event_id = event_id
        self.old_attention_status = old_attention_status


class LoadAction:
    def __init__(self, previous_state):
        self.previous_state = previous_state


class GlobalRecoveryAction:
    def __init__(self, previous_root: AVLNode):
        self.previous_root = previous_root

class QueueStepAction:
    def __init__(self, report: Report, queue_position: int, inner_action: Optional[CreationAction | CorrectionAction] = None, confirmed_station_id: Optional[int] = None):
        self.report = report
        self.queue_position = queue_position
        self.inner_action = inner_action
        self.confirmed_station_id = confirmed_station_id