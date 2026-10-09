from app.domain.event import Event, AttentionStatus
from app.domain.zone import Zone
from app.domain.station import Station
from app.structures.avl_node import AVLNode
from app.structures.avl_tree import AVLTopologySnapshot
from datetime import datetime
from typing import Optional
from app.domain.report import Report


"""Action classes for the undo/redo stack (section 13).

An "action" is a small data container that records what a single user
operation changed, so Scenario.undo() can revert it later. Actions have
NO behaviour: they do not modify the scenario, they do not decide
anything, they do not touch the trees. They are created by Scenario,
pushed onto Scenario.undo_stack, and read back by Scenario.undo() via
isinstance() dispatch.

What each action stores (the minimum to invert its operation):

    CreationAction         event_id + old references of affected events
    CorrectionAction       old field values + old references of affected events
    ReactivationAction     same as CorrectionAction, but the "before" state
                           was being archived, not being in the AVL
    DeletionAction         the complete Event + old references
    MassArchiveAction      archived subtree root + where it hung from
    ParameterChangeAction  name(s) and old value(s) of the changed parameter(s),
                           plus old references if W or R changed
    ClockAdvanceAction     the previous simulation clock value
    AttentionChangeAction  the previous attention status
    LoadAction             the entire previous scenario state
    GlobalRecoveryAction   topology snapshot + rotation delta + previous mode
    QueueStepAction        the processed Report, its position, and the inner
                           action (create / correct / reactivate) it produced
    ClearReportQueueAction the reports that were in the queue when cleared
    ReportEnqueueAction    the report(s) added to the queue
    ZoneAction             zone CRUD operation (create / update / delete)
    StationAction          station CRUD operation (create / update / delete)

Most actions also carry:

    tree_checkpoint   shape of AVL/BST before the operation + rotation
                      metric deltas. Restored as-is on undo (section 13).
    counter_delta     what the operation added to section 14 counters.
                      Subtracted on undo.

Why LoadAction is the exception
-------------------------------
Every other action stores the minimum. LoadAction stores a reference to
the entire previous scenario state, because a load replaces everything.
The reference is kept (not deep-copied) because a load never mutates the
old state: it builds a new one. Previous actions hold live references to
real nodes of that old state, and their identity must be preserved across
the load, or undoing them after undoing the load would break.
"""


class CreationAction:
    """Action representing the manual creation of an event.

    Pushed to Scenario.undo_stack after create_event completes
    successfully. On undo, Scenario must be able to revert EVERYTHING that
    creation changed, not just the new event.

    The previous version only stored `event_id`. That was enough to
    remove the new event from the AVL, BST, and event_index, but NOT
    enough to restore references of other events. When creating
    B, B can become a candidate for existing events X (late
    reports with higher magnitude), and those X change their reference. If on
    undo we only removed B, those X would remain pointing to an event
    that no longer exists: breaking the section 7 invariant.

    Scenario.undo() pops from the stack and decides with isinstance()
    what to revert. For a CreationAction it needs to know:
      - which event to remove (event_id), and
      - which reference to restore for each affected event
        (old_references).

    old_references is a dict {event_id: previous_reference_id}. Always
    includes the new event (which previously did not exist -> None) and any
    other event whose reference changed due to this creation.
    """

    def __init__(self, event_id: int, old_references: dict[int, int | None],
                 tree_checkpoint: Optional[dict] = None):
        self.event_id = event_id
        self.old_references = old_references
        # Snapshot of the AVL and BST shape taken BEFORE touching the
        # trees, plus what the operation added to rotation metrics
        # (see Scenario._tree_checkpoint). On undo it is restored as-is:
        # same topology and same metrics (section 13).
        self.tree_checkpoint = tree_checkpoint


class CorrectionAction:
    """Action representing a manual correction of an active event.

    Pushed to Scenario.undo_stack after correct_event completes
    successfully. On undo, Scenario must be able to revert EVERYTHING that
    the correction changed, not just the event data.

    The first version of CorrectionAction only stored the event id.
    That was insufficient for three reasons that arose when
    writing correct_event:

    1) The correction modifies several fields of Event.
       apply_correction() can change magnitude, depth, x, y,
       is_in_populated_zone, revision, and attention_status (returns to
       PENDING). To undo, ALL those values must be restored.
       With only the id it is impossible: there is nowhere to get the old
       values from. That is why they are saved field by field.

    2) The correction can change the key K of the event.
       If magnitude, depth, or populated zone changes, priority
       changes, and with it key K = (P, M, I). That requires removing
       the node from AVL and BST and reinserting it. On undo we must
       do the same in reverse: remove with CURRENT key and
       reinsert with OLD key.
       NOTE: the old key is NOT stored in the action. It is reconstructed
       on its own when restoring old_magnitude, old_depth, and
       old_is_in_populated_zone, because Event.priority and Event.key are
       @property: as soon as attributes change, the key is recalculated.
       Storing it would duplicate information.

    3) The correction can change associations (section 7).
       If magnitude increases or the date changes, B can become a candidate
       for events that previously did not have it as a reference. And if magnitude
       decreases or it moves further from the epicenter, B may cease to be a candidate
       for events that did have it as a reference. Both groups must be
       recalculated.
       To undo, references they had BEFORE the correction must be restored.
       That is stored in old_references, following the same
       pattern used by CreationAction: a dict {event_id: reference_id}
       with the previous snapshot of each affected event.

    Why does Scenario need this?
    ----------------------------
    Scenario.undo() pops from the stack and decides with isinstance() what
    to revert. For a CorrectionAction it needs to know:

      - which event to correct (event_id),
      - which values to restore (old_magnitude, old_depth, old_x, old_y,
        old_is_in_populated_zone, old_revision, old_attention_status), and
      - which references to restore for each affected event
        (old_references).

    What is NOT stored, and why:
      - old_key: reconstructed on its own when restoring old values.
      - old_stations: apply_correction() does not touch stations, so
        they do not change and there is nothing to restore.
      - a complete copy of Event: not needed, the fields that do
        change are immutable (float, bool, int, enum) and storing them
        individually suffices. There are no lists or sets that can be mutated
        accidentally.
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
        tree_checkpoint: Optional[dict] = None,
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
        # What this correction added to the section 14 counters
        # ({"corrections_accepted": 1}). Subtracted on undo.
        self.counter_delta = counter_delta or {}
        # Snapshot of the AVL and BST shape taken BEFORE touching the
        # trees, plus what the operation added to rotation metrics
        # (see Scenario._tree_checkpoint). On undo it is restored as-is:
        # same topology and same metrics (section 13).
        self.tree_checkpoint = tree_checkpoint


class ReactivationAction:
    """Action representing the reactivation of an archived event by
    a report with a higher revision (section 6).

    Pushed to Scenario.undo_stack inside archived_reactivation().
    process_next_report pops it and places it inside
    QueueStepAction, just as it already does with CreationAction and
    CorrectionAction.

    Differences from CorrectionAction:
    - Same old_* fields + old_references, but the "before" state of the event
      is not being in the AVL: it is being in archived_history.
    - On undo, the event is NOT relocated within the tree: it leaves the
      AVL/BST/event_index and returns to archived_history (see
      _undo_reactivation in Scenario).

    Why it is a separate class instead of reusing CorrectionAction: the project
    criterion was never "what data it stores" but "what undo() has to do
    with it", and there they are indeed different.
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
        tree_checkpoint: Optional[dict] = None,
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
        # What this reactivation added to section 14 counters
        # ({"corrections_accepted": 1}). Subtracted on undo.
        self.counter_delta = counter_delta or {}
        # Snapshot of the AVL and BST shape taken BEFORE touching the
        # trees, plus what the operation added to rotation metrics
        # (see Scenario._tree_checkpoint). On undo it is restored as-is:
        # same topology and same metrics (section 13).
        self.tree_checkpoint = tree_checkpoint


class DeletionAction:
    """Stores the complete Event that was deleted, since once deleted
    it does not remain in any other structure; on undo it is reinserted as-is.
    Also stores old references of events affected by the
    deletion (those having the deleted event as reference), to be able
    to restore them on undo."""

    def __init__(self, event: Event, old_references: dict[int, int | None],
                 tree_checkpoint: Optional[dict] = None):
        self.event = event
        self.old_references = old_references
        # Snapshot of the AVL and BST shape taken BEFORE touching the
        # trees, plus what the operation added to rotation metrics
        # (see Scenario._tree_checkpoint). On undo it is restored as-is:
        # same topology and same metrics (section 13).
        self.tree_checkpoint = tree_checkpoint


class MassArchiveAction:
    """Stores the root of the subtree that was archived in bulk, its former
    parent and which side it hung from, plus the list of affected ids, to be able
    to reattach the entire subtree in its original position on undo.

    rotation_delta: what detach_subtree added to rotation metrics.
    Subtracted on undo with avl_tree.revert_rotation_metrics(delta).

    counter_delta: what archiving added to section 14 counters
    ({"mass_archives": 1, "archived_events": branch size}). Subtracted
    on undo with Scenario._revert_counters(delta).
    """

    def __init__(self, archived_root: AVLNode, former_parent: Optional[AVLNode],
                 was_left_child: Optional[bool], event_ids: list[int],
                 rotation_delta: dict = None, counter_delta: dict = None,
                 tree_checkpoint: Optional[dict] = None):
        self.archived_root = archived_root
        self.former_parent = former_parent
        self.was_left_child = was_left_child
        self.event_ids = event_ids
        self.rotation_delta = rotation_delta or {}
        self.counter_delta = counter_delta or {}
        # Snapshot of the AVL and BST shape taken BEFORE touching the
        # trees, plus what the operation added to rotation metrics
        # (see Scenario._tree_checkpoint). On undo it is restored as-is:
        # same topology and same metrics (section 13).
        self.tree_checkpoint = tree_checkpoint


class ParameterChangeAction:
    """Stores the name of the global parameter (L, W, R, or T), its previous
    value, and — when the parameter affects associations (W or R) —
    the snapshot of references of all active and archived events
    before recalculating them.

    Why old_references?
    Changing W or R redefines which events are candidates for each other. No
    filter is possible: any event can gain or lose candidates.
    Therefore, when changing W or R, Scenario recalculates the reference of ALL
    active and archived events. To be able to undo, the reference_id each one had
    before recalculation must be saved.

    For L and T this does not apply: L only affects the "costly access" flag
    (does not touch references) and T only affects future archive operations
    (already archived branches remain as they are). In those
    cases old_references remains None.
    """

    def __init__(self, parameter_name: str, old_value: float,
                 old_references: dict[int, int | None] = None,
                 old_values: Optional[dict[str, float]] = None):
        self.parameter_name = parameter_name
        self.old_value = old_value
        self.old_references = old_references
        # All parameters changed by ONE call to change_parameters,
        # with their old value ({"W": 48.0, "R": 40.0}). Changing multiple
        # parameters at once is ONE single action: undone with a single
        # "undo". parameter_name has the joined names ("W,R").
        self.old_values = old_values or {parameter_name: old_value}


class ClockAdvanceAction:
    """Records the previous simulation clock, so undo can rewind it.

    Advancing the clock is one-directional (update_simulation_clock refuses
    to move it backwards). Undo is the only way to move it back, and to do
    so it needs the exact old value. A datetime is immutable, so storing
    it directly is safe.
    """

    def __init__(self, old_clock: datetime):
        self.old_clock = old_clock


class AttentionChangeAction:
    """Records the previous attention status of an event, so undo can
    restore it.

    Only one field changes when an event is marked as reviewed
    (attention_status). The key, the tree position, and the associations
    are untouched, so nothing else needs to be stored. The event is found
    on undo with _find_any_event(event_id), which is why the id is saved
    even though it is not strictly needed to identify the field.
    """

    def __init__(self, event_id: int, old_attention_status: AttentionStatus):
        self.event_id = event_id
        self.old_attention_status = old_attention_status


class LoadAction:
    """Records the entire scenario state before a load, so undo can
    restore it.

    This action is the exception to the "store only the minimum" rule:
    loading a file (or restoring a version) replaces every operational
    attribute of the scenario, so the only thing that can be stored is
    the whole previous state.

    `previous_state` is a REFERENCE, not a deep copy. A load never mutates
    the old state (it builds a new one and assigns it to self), so keeping
    the reference is both safe and required: previous actions hold live
    references to real nodes of that old state, and their identity must be
    preserved across the load. See Scenario._snapshot_full_state and
    Scenario._restore_full_state for the shape of the dict.
    """

    def __init__(self, previous_state):
        self.previous_state = previous_state


class GlobalRecoveryAction:
    """Stores the state of the AVL before a global recovery, to
    be able to restore it identically on undo (section 13).

    - topology_snapshot: copy of tree shape taken with
      avl_tree.snapshot_topology() BEFORE recovering. Storing only the previous
      root is not enough: rotations change the links of those same
      nodes, so the old root no longer describes the old shape.
    - rotation_delta: what recovery added to rotation
      metrics (avl_tree.last_rotation_delta() AFTER recovering), to
      subtract it on undo with avl_tree.revert_rotation_metrics(delta).
    - previous_mode: mode the scenario was in before (normally
      Mode.STRESS), in case recovery ends up returning to normal mode.
      Without type annotation intentionally: importing Mode from scenario.py
      would create a circular import when Scenario imports these actions.

    Expected flow in Scenario:
        snapshot = self.avl_tree.snapshot_topology()
        self.avl_tree.recover_balance()
        action = GlobalRecoveryAction(snapshot, self.avl_tree.last_rotation_delta(), self.mode)
        self.undo_stack.push(action)
    On undo:
        self.avl_tree.restore_topology(action.topology_snapshot)
        self.avl_tree.revert_rotation_metrics(action.rotation_delta)
        self.mode = action.previous_mode
    """

    def __init__(self, topology_snapshot: AVLTopologySnapshot, rotation_delta: dict[str, int], previous_mode=None):
        self.topology_snapshot = topology_snapshot
        self.rotation_delta = rotation_delta
        self.previous_mode = previous_mode


class QueueStepAction:
    """Records the processing of ONE report from the queue.

    Pushed by Scenario.process_next_report() after the report has been
    dequeued. On undo, the step must be reversed in this order:

      1. Remove the confirmed station from the event (if any), while the
         event still exists.
      2. Revert the inner action (creation / correction / reactivation)
         by calling the matching _undo_* helper.
      3. Return the report to its original queue position.

    Why inner_action
    ----------------
    A queue step is ONE action for the user, but internally it can trigger
    another operation (create_event, correct_event, archived_reactivation),
    each of which pushes its own action. To avoid two "undo" presses per
    step, process_next_report pops that inner action and stores it here.
    The stack sees only the QueueStepAction; this action carries the inner
    one inside.

    counter_delta holds only what the STEP itself added to section 14
    counters (conflict or discarded report). An inner correction or
    reactivation stores its count in inner_action, not here, to avoid
    counting it twice on undo.
    """

    def __init__(
        self,
        report: Report,
        queue_position: int,
        inner_action: Optional[CreationAction | CorrectionAction | ReactivationAction] = None,
        confirmed_station_id: Optional[str] = None,
        counter_delta: Optional[dict[str, int]] = None,
    ):
        self.report = report
        self.queue_position = queue_position
        self.inner_action = inner_action
        self.confirmed_station_id = confirmed_station_id
        # What the step ITSELF added to section 14 counters
        # (conflict or discarded report). An inner correction or reactivation
        # stores its count in inner_action, not here.
        self.counter_delta = counter_delta or {}


class ClearReportQueueAction:
    """Records the reports that were in the queue when clear_report_queue()
    removed them, so undo can put them back in their original order.

    The whole queue is cleared as ONE action. If the queue was empty,
    clear_report_queue() does NOT push an action (nothing changed), so
    this class is only instantiated when there was something to clear.
    """

    def __init__(self, reports: list[Report]):
        self.reports = reports


class ReportEnqueueAction:
    """Records the report(s) that were added to the queue, so undo can
    remove them.

    batch=False -> a single report was enqueued (enqueue_report).
    batch=True  -> a burst of reports was enqueued at once
                   (enqueue_reports). The whole burst is undone as one
                   action, matching the atomicity of the enqueue.

    On undo, the reports are removed by identity, not by position,
    because other reports may have been enqueued after them.
    """

    def __init__(self, reports: list[Report], batch: bool):
        self.reports = reports
        self.batch = batch


class ZoneAction:
    """Records a zone CRUD operation (create / update / delete), so undo
    can reverse it.

    operation  : "create" | "update" | "delete"
    old_zone   : the zone before the operation (None for "create")
    new_zone   : the zone after the operation (None for "delete")
    index      : position in the zones list, so undo restores order
                 exactly (list order matters to the UI)
    """

    def __init__(self, operation: str, old_zone: Optional[Zone],
                 new_zone: Optional[Zone], index: int):
        self.operation = operation
        self.old_zone = old_zone
        self.new_zone = new_zone
        self.index = index


class StationAction:
    """Records a station CRUD operation (create / update / delete), so
    undo can reverse it.

    operation   : "create" | "update" | "delete"
    old_station : the station before the operation (None for "create")
    new_station : the station after the operation (None for "delete")
    index       : position in the stations dict, so undo restores order
                  exactly (the UI shows them in insertion order)

    Note on "update" with a changed id: undo removes the new id and
    reinserts the old one at the saved index, because the identity of a
    station is its id (Station.__eq__ / __hash__).
    """

    def __init__(self, operation: str, old_station: Optional[Station],
                 new_station: Optional[Station], index: int):
        self.operation = operation
        self.old_station = old_station
        self.new_station = new_station
        self.index = index