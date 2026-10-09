from enum import Enum
from datetime import datetime, timedelta, timezone
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
    GlobalRecoveryAction, LoadAction, ReactivationAction, ClearReportQueueAction,
    ReportEnqueueAction, ZoneAction, StationAction,
)
from app.structures.avl_tree import AVLTree, ROTATION_METRIC_KEYS, AVLTopologySnapshot
from app.structures.avl_node import AVLNode
from app.structures.bst_node import BSTNode
from app.structures.bst_tree import BSTTree

#Counters. They live in the same dictionary as self. metrics, so they get exported
#They load and get reinstated with the same state.When undone, each action substracts
#whatever they added (counter_delta), the same as rotation_delta.

# corrections_accepted: corrections appliad (manual, from reports and reactivations of archived)
# reports_discarded: reports that were denied when processing the queue for antiquity (active or archived) or because of a deleted id
#                    reports with the same revision and disfferent data over an active or archived event.
# conflicts: reports with the same revision and distinct data over an active or archived event. (a confirmation, active or archived)
#            doesn't count: the report gets accepted)
# mass_archives: massive executed archives
# archived_events: events sent to the historic by massive archivations (it accumulates, the current amount of archived events is len(archiced_history))

COUNTER_KEYS = ("corrections_accepted", "reports_discarded", "conflicts",
                "mass_archives", "archived_events")

"""==========================================================================================
INFRASTRUCTURE: Methods that are important for the project but are not specific to any class
============================================================================================="""

class Scenario:

    def __init__(self, metrics : Optional[dict[str, int]] = None,avl_tree: Optional[AVLTree] = None, bst_tree: Optional[BSTTree] = None, 
                event_index : Optional[dict[int, AVLNode]] = None, stations : Optional[dict[str, Station]] = None, zones: Optional[list[Zone]] = None, 
                eliminated_IDs: Optional[set[int]] = None, archived_history: Optional[dict[int, Event]] = None, referenced_by=None, simulation_clock: Optional[datetime] = None, 
                L: int=3, W: float = 48.0, R: float = 40.0, T: float = 72.0, mode: Mode = Mode.NORMAL, undo_stack: Optional[Stack] = None, report_queue: Optional[Queue] = None, versions: Optional[dict[str, dict]] = None):

        # Collections for elimination and history.
        self.eliminated_IDs = eliminated_IDs if eliminated_IDs is not None else set()
        self.archived_history = archived_history if archived_history is not None else dict()

        # Simulation clock, second precision. If none is provided, start at
        # the current system UTC time. From then on it does NOT move by
        # itself: it only changes through update_simulation_clock (user
        # action, section 3), undo, or loading a scenario/version.
        self._simulation_clock: datetime = simulation_clock or datetime.now(timezone.utc).replace(microsecond=0)

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
        # Section 14 counters set to 0 if not provided (for example, when
        # loading a file saved before they existed).
        for counter_key in COUNTER_KEYS:
            self.metrics.setdefault(counter_key, 0)

        # AVLTree must receive self.metrics after it is created, so both
        # share the same metrics dictionary (single source of truth).
        self.avl_tree = avl_tree if avl_tree is not None else AVLTree(metrics=self.metrics)
        self.bst_tree = bst_tree if bst_tree is not None else BSTTree()

        self.undo_stack = undo_stack if undo_stack is not None else Stack()
        self.report_queue = report_queue if report_queue is not None else Queue()

        self.referenced_by = referenced_by if referenced_by is not None else dict()

        self.versions = versions if versions is not None else dict()

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Checks that the datetime contains a timezone. If not, raises an error. If it does, transforms it into UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Event and report timestamps must include a timezone")
        return value.astimezone(timezone.utc)

    def _add_counters(self, delta: dict) -> None:
        """HELPER: adds `delta` to section 14 counters. The caller
        saves the same delta in its action to be able to subtract it."""
        for counter_key, amount in delta.items():
            self.metrics[counter_key] = self.metrics.get(counter_key, 0) + amount

    # SNAPSHOTS OF THE TREES TO UNDO
    #
    # Undo must recover the exact state, including the topology
    # reinserting or deleting when undoing is not enough, because those actions may cause rotations
    # that would give a different shape to the tree and add more metrics.
    # Because of this, each operation that may change the tree's state (Create, edit, reactivate, delete or archive)
    # takes a snapshot before doing any changes, saves it on its own action and when undone
    # the snapshot gets reinstated. It's the same mechanism already used by GlobalRecoveryAction
    #
    # Memory: O(n) references by action (5 for the AVL node and 3 for the node of the BST)
    # Without copying events or creating nodes. With 100 events is very little, and in exchange, undoing is exact and O(n).

    def _tree_checkpoint(self) -> dict:
        """AUXILIAR: Snapshot of the current shape of the AVL, BST and rotation metrics.
        It's taken before doing any changes"""
        # Opens the journal of the AVL rotations: From here to _close_tree_checkpoint it
        # writes each attended case
        self.avl_tree.rotation_journal = []
        return {
            "avl": self.avl_tree.snapshot_topology(),
            "bst": self.bst_tree.snapshot_topology(),
            "rotations_before": {k: self.metrics.get(k, 0) for k in ROTATION_METRIC_KEYS},
        }

    def _close_tree_checkpoint(self, checkpoint: dict) -> dict:
        """AUXILIAR: completes the snapshot after modifying the trees, with the operations that were
        added to the rotation metrics. Gets calculated by the difference because a correction
        does delete and insert, and each one resets last_rotations."""
        before = checkpoint["rotations_before"]
        checkpoint["rotation_delta"] = {
            k: self.metrics.get(k, 0) - before[k] for k in ROTATION_METRIC_KEYS
        }
        # Lists the attended cases in the whole operation
        checkpoint["rotations"] = self.avl_tree.rotation_journal or []
        self.avl_tree.rotation_journal = None
        return checkpoint

    def _restore_tree_checkpoint(self, checkpoint: dict, event_ids=()) -> None:
        """AUXILIAR: returns the AVL and the BST to the original snapshot.
        substracts the rotations that were added by the operation and 
        rewrites event_index to the original nodes."""
        self.avl_tree.restore_topology(checkpoint["avl"])
        self.bst_tree.restore_topology(checkpoint["bst"])
        self.avl_tree.revert_rotation_metrics(checkpoint.get("rotation_delta", {}))
        if event_ids:
            wanted = set(event_ids)
            for node, *_ in checkpoint["avl"].links:
                if node.event.event_id in wanted:
                    self.event_index[node.event.event_id] = node

    def _revert_counters(self, delta: dict) -> None:
        """AUXILIAR: substracts the delta that an action saved (when undoing)."""
        for counter_key, amount in delta.items():
            self.metrics[counter_key] = self.metrics.get(counter_key, 0) - amount

    """==============================================="""
    """=================MODE METHODS=================="""
    """==============================================="""

    def set_mode(self, mode):
        """Sets the mode. If trying to change from stress to normal, it checks if the AVL tree is balanced before approving
        the opperation."""
        if not isinstance(mode, Mode):
            raise ValueError("Mode must either be Stress or Normal")

        if mode == Mode.NORMAL:
            audit = self.verify_structure()
            if not audit["is_valid"] or not audit["is_avl"]:
                raise ValueError("The AVL tree must be valid and balanced before leaving Stress mode")

        self.mode = mode
        return self.mode
    
    def get_mode(self):
        """Returns the current mode"""
        return self.mode


    """==============================================="""
    """=================CLOCK METHODS================="""
    """==============================================="""
    @property
    def simulation_clock(self) -> datetime:
        """Simulation clock. It's a fixed value. The user can set a new time from the Frontend."""
        return self._simulation_clock

    @simulation_clock.setter
    def simulation_clock(self, value: datetime) -> None:
        """Sets the initial time as the setted time. Creates a monotonic that'll check how much time passes since the clock
        has been set"""
        self._simulation_clock = value

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

        # Save the current simulation clock BEFORE changing it, so undo can
        # return to this exact instant.
        old_clock = self.simulation_clock

        # Apply the new clock.
        self.simulation_clock = new_clock

        # Push the action with the old value.
        self.undo_stack.push(ClockAdvanceAction(old_clock))

        return self.simulation_clock

    """==============================================="""
    """================GLOBAL PARAMETERS==================="""
    """==============================================="""

    def change_parameters(self, changes: dict) -> dict:
        """Change one or several global parameters (L, W, R, T).

        Receives a dict {name: new_value}. Validates ALL names and values
        before applying anything (atomic: if one fails, none is changed).
        Ignores parameters whose value does not actually change.

        Returns a dict with only the parameters that did change.

        If W or R changes, the definition of "candidate" between events
        changes, so it recalculates the reference of every active and
        archived event. In that case, the action saves old_references so it
        can be undone. For L and T there is no recalculation and no
        old_references.

        Several parameters in one call (for example {"W": 24, "R": 50}) are
        ONE action: one undo reverts all of them. The references are
        snapshotted once (before any change) and recalculated once (after
        all of them), only if W or R changed.
        """
        valid_names = {"L", "W", "R", "T"}

        # 1. Validate names.
        for name in changes:
            if name not in valid_names:
                raise ValueError(f"Unknown parameter: {name}")

        # 2. Validate values (in case someone calls Scenario directly).
        if "L" in changes:
            new_L = changes["L"]
            if not isinstance(new_L, int) or isinstance(new_L, bool) or new_L < 0:
                raise ValueError("L must be a non-negative integer")

        for name in ("W", "R", "T"):
            if name in changes and changes[name] <= 0:
                raise ValueError(f"{name} must be a positive number")

        # 3. Keep only those that truly change. Nothing changed -> no action.
        changed = {name: value for name, value in changes.items()
                if getattr(self, name) != value}
        if not changed:
            return {}
        old_values = {name: getattr(self, name) for name in changed}

        # 4. Snapshot of references BEFORE touching anything, only if W or R
        # changes (they redefine who is a candidate of whom).
        affects_references = "W" in changed or "R" in changed
        old_refs = None
        if affects_references:
            old_refs = {
                event.event_id: event.reference_id
                for event in self._all_active_and_archived_events()
            }

        # 5. Apply all the changes, then recalculate references once.
        for name, new_value in changed.items():
            setattr(self, name, new_value)
        if affects_references:
            for event in self._all_active_and_archived_events():
                self._recalculate_reference(event)

        # 6. ONE action for the whole change.
        names = ",".join(changed)
        first = next(iter(changed))
        self.undo_stack.push(ParameterChangeAction(
            names, old_values[first], old_refs, old_values=old_values,
        ))
        return changed
    """==============================================="""
    """================ZONE METHODS==================="""
    """==============================================="""

    def _check_zones_and_stations_are_fixed(self) -> None:
        """AUXILIAR: zones and stations are FIXED once the scenario has
        events (sections 1 and 3: "the geometry remains fixed during the
        scenario" and "stations... are immutable during the execution of
        the system").

        The CRUD is only free while there are NO events at all (neither
        active nor archived). As soon as there is at least one event, the
        three zone methods and the three station methods refuse to run.

        Why ValueError: the operation is valid in the abstract, it is
        just forbidden by the current state of the scenario. The router
        translates ValueError -> 409 (conflict).

        Why archived_history also counts: archived events keep their
        identity and their associations (section 7), and their
        `event.stations` still reference real stations. Blocking only on
        event_index would let us delete a station that is still being
        referenced by an archived event.
        """
        if self.event_index or self.archived_history:
            raise ValueError(
                "Zones and stations are fixed once the scenario has events"
            )

    def add_zone(self, zone: Zone):
        """Add a zone. Only allowed while the scenario has no events
        (see _check_zones_and_stations_are_fixed).

        Checks that no other existing zone has the same name, and if not,
        appends the new zone."""
        self._check_zones_and_stations_are_fixed()

        if any(existing.name == zone.name for existing in self.zones):
            raise ValueError("A zone with this name already exists")

        index = len(self.zones)
        self.zones.append(zone)
        self.undo_stack.push(ZoneAction("create", None, zone, index))
        return zone

    def get_zone(self, zone_name: str) -> Zone:
        """Return the zone with the requested name. Reads are always
        allowed: the restriction is only on add/update/delete."""
        for zone in self.zones:
            if zone.name == zone_name:
                return zone

        raise KeyError(f"Zone '{zone_name}' was not found")

    def list_zones(self) -> list[Zone]:
        """Return a COPY of the zones list. Same pattern as
        list_stations: callers cannot modify the scenario's internal
        list by accident."""
        return list(self.zones)

    def update_zone(self, zone_name: str, changes: dict) -> Zone:
        """Update an existing zone. Only allowed while the scenario has
        no events (see _check_zones_and_stations_are_fixed).

        Fields not present in `changes` keep their old value. Replaces
        the old Zone instance with a new one (so __init__ revalidates),
        in the same position in the list."""
        self._check_zones_and_stations_are_fixed()

        current_zone = self.get_zone(zone_name)

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

        updated_zone = Zone(**updated_values)
        zone_index = self.zones.index(current_zone)
        self.zones[zone_index] = updated_zone
        self.undo_stack.push(ZoneAction("update", current_zone, updated_zone, zone_index))
        return updated_zone

    def delete_zone(self, zone_name: str) -> None:
        """Delete a zone. Only allowed while the scenario has no events
        (see _check_zones_and_stations_are_fixed)."""
        self._check_zones_and_stations_are_fixed()

        zone = self.get_zone(zone_name)
        zone_index = self.zones.index(zone)
        self.zones.remove(zone)
        self.undo_stack.push(ZoneAction("delete", zone, None, zone_index))


    """==============================================="""
    """================STATION METHODS================"""
    """==============================================="""

    def add_station(self, station: Station) -> Station:
        """Add a station, using its ID as the dictionary key. Only
        allowed while the scenario has no events (see
        _check_zones_and_stations_are_fixed)."""
        self._check_zones_and_stations_are_fixed()

        if station.station_id in self.stations:
            raise ValueError("A station with this ID already exists")

        index = len(self.stations)
        self.stations[station.station_id] = station
        self.undo_stack.push(StationAction("create", None, station, index))
        return station

    def get_station(self, station_id: str) -> Station:
        """Return the station with the requested id. Reads are always
        allowed: the restriction is only on add/update/delete."""
        try:
            return self.stations[station_id]
        except KeyError:
            raise KeyError(f"Station '{station_id}' was not found") from None

    def list_stations(self) -> list[Station]:
        """Return a COPY of the stations as a list. Same pattern as
        list_zones: callers cannot modify the scenario's internal dict."""
        return list(self.stations.values())

    def update_station(self, station_id: str, changes: dict) -> Station:
        """Update an existing station. Only allowed while the scenario
        has no events (see _check_zones_and_stations_are_fixed).

        Fields not present in `changes` keep their old value. If the
        station_id itself changes, the old key is removed and the new
        key is added (the identity of the station is its id)."""
        self._check_zones_and_stations_are_fixed()

        current_station = self.get_station(station_id)

        updated_values = {
            "station_id": changes.get("station_id", current_station.station_id),
            "x": changes.get("x", current_station.x),
            "y": changes.get("y", current_station.y),
        }

        if updated_values["station_id"] != station_id and any(
            existing_id == updated_values["station_id"] for existing_id in self.stations
        ):
            raise ValueError("A station with this id already exists")

        station_index = list(self.stations).index(station_id)
        updated_station = Station(**updated_values)
        if updated_station.station_id != station_id:
            del self.stations[station_id]
        self.stations[updated_station.station_id] = updated_station
        self.undo_stack.push(StationAction("update", current_station, updated_station, station_index))
        return updated_station

    def delete_station(self, station_id: str) -> None:
        """Delete a station. Only allowed while the scenario has no
        events (see _check_zones_and_stations_are_fixed)."""
        self._check_zones_and_stations_are_fixed()

        station = self.get_station(station_id)
        station_index = list(self.stations).index(station_id)
        del self.stations[station_id]
        self.undo_stack.push(StationAction("delete", station, None, station_index))


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
        if the occurrence time is later than the simulation clock.

        Why we check the id and not the Station object:
        the schema reconstructs the Station from the payload, so it is
        never the same instance as the one stored in self.stations. What
        we really care about is "does this station id exist in the
        scenario", not "is this the exact object we registered". Checking
        the id is both simpler and less fragile.
        """
        station_id = report.station.station_id
        if station_id not in self.stations:
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
        self.undo_stack.push(ReportEnqueueAction([report], batch=False))
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
        if reports:
            self.undo_stack.push(ReportEnqueueAction(list(reports), batch=True))
        return first_position

    def list_reports(self) -> list[Report]:
        """Copy of the queue in reception order (the first one is the next
        to be processed). It is a copy: modifying the list does not alter
        the queue. O(n)."""
        return self.report_queue.items()
    
    def replace_next_report(self, report: Report) -> Report:
        """Replace the FIFO head without changing its position or revision."""
        if self.report_queue.is_empty():
            raise ValueError("No hay reportes pendientes en la cola")
        
        current = self.report_queue.peek()
        if report.event_id != current.event_id:
            raise ValueError("El identificador del reporte en revisión no se puede cambiar")
        
        report.revision_num = current.revision_num
        self._validate_report(report)
        self.report_queue.replace_first(report)
        return report
    
    def discard_next_report(self) -> Report:
        """Discard only the FIFO head, leaving its event unchanged."""
        if self.report_queue.is_empty():
            raise ValueError("No hay reportes pendientes en la cola")
        return self.report_queue.dequeue()

    def clear_report_queue(self) -> int:
        """Discard all pending reports and return how many there were.
        Does not touch events, trees, or the clock. A snapshot of the FIFO
        queue is recorded so undo can restore the reports in their original
        order. If the queue is empty, nothing is recorded and 0 is returned."""
        reports = self.report_queue.items()
        removed = self.report_queue.clear()
        if removed:
            self.undo_stack.push(ClearReportQueueAction(reports))
        return removed


    def process_next_report(self) -> dict:
        """Process ONE report from the queue (section 8: "one report per step").

        Takes the first one from the queue and decides which case it is. The
        possible cases are in the section 6 table: unknown id (create),
        greater revision (correct), same revision and same data (confirm),
        same revision and different data (conflict), lower revision (old),
        and eliminated id (reject).

        Data equality refers to magnitude, depth, epicenter (x, y), and
        occurrence time. It does NOT count the sending station.

        Even if the report is rejected/old/conflict, a QueueStepAction is
        pushed so the report can be put back in its queue position on undo.

        ──────────────────────────────────────────────────────────────
        The problem of TWO actions for a single step
        ──────────────────────────────────────────────────────────────

        A queue step is ONE action for the user, but internally it may
        trigger another operation (create, correct, or reactivate an event).
        create_event, correct_event, and archived_reactivation push their own
        action at the end. If process_next_report also pushed a
        QueueStepAction, there would be TWO actions on the stack per single
        step, and the user would have to press "undo" twice.

        The solution is to pop the inner action they just pushed and put it
        INSIDE the QueueStepAction. So the stack only sees one action per
        step, but that action carries inside everything needed to revert the
        inner operation.
        """

        # 1. Empty queue → nothing to process.
        if self.report_queue.is_empty():
            raise ValueError("No hay reportes pendientes en la cola")

        # 2. Peek: look at the first one without removing it.
        report = self.report_queue.peek()
        queue_position = 0   # always the first one (the queue is FIFO)
        event_id = report.event_id

        # 3. Decide the case and execute.
        case = None
        inner_action = None
        confirmed_station_id = None

        # Special case: eliminated id. Rejected without touching anything.
        if event_id in self.eliminated_IDs:
            case = "eliminated"

        # Case: unknown id → create a new event.
        # "Unknown" = not active, not archived, not eliminated.
        elif event_id not in self.event_index and event_id not in self.archived_history:
            case = "created"
            self.create_event(
                event_id=event_id,
                magnitude=report.magnitude,
                depth=report.depth,
                x=report.x,
                y=report.y,
                occurred_at=report.occurred_at,
                stations={report.station},       # the set with the report's only station
                revision=report.revision_num,    # the report's claimed revision (can be > 1)
            )
            # create_event already pushed a CreationAction. Pop it to put it
            # inside the QueueStepAction: one queue step = one action in the
            # stack, not two.
            inner_action = self.undo_stack.pop()

        # Case: archived id.
        elif event_id in self.archived_history:
            archived_event = self.archived_history[event_id]
            if report.revision_num > archived_event.revision:
                # A report with a greater revision REACTIVATES the archived
                # event: it leaves archived_history and goes back to the AVL
                # with the corrected data (section 6).
                case = "reactivated"
                event = self.archived_reactivation(report)

                # archived_reactivation already pushed its own
                # ReactivationAction. Pop it to put it inside the
                # QueueStepAction, same pattern as "created" and "corrected":
                # one queue step = one action in the stack.
                inner_action = self.undo_stack.pop()

                # Add the report's station if it was not there. This is done
                # HERE and not inside archived_reactivation, for the same
                # reason as in "corrected": this way we can compare
                # before/after and know if the station was new, so we can
                # remove it when undoing the step.
                if report.station not in event.stations:
                    event.stations.add(report.station)
                    confirmed_station_id = report.station.station_id

            elif report.revision_num == archived_event.revision:
                # Same revision on an archived event. Section 6 says:
                #   - Confirmation ("same revision, same data") adds the
                #     station if it was not already there. The statement
                #     does NOT distinguish active from archived here.
                #   - Confirmation does NOT reactivate the archived event
                #     (that only happens with a greater revision). The
                #     event stays in archived_history.
                # So: same data -> add station, stay archived.
                #     different data -> conflict, touch nothing.
                same_data = (
                    report.magnitude == archived_event.magnitude
                    and report.depth == archived_event.depth
                    and report.x == archived_event.x
                    and report.y == archived_event.y
                    and report.occurred_at == archived_event.occurred_at
                )
                if same_data:
                    case = "archived_confirmed"
                    if report.station not in archived_event.stations:
                        archived_event.stations.add(report.station)
                        confirmed_station_id = report.station.station_id
                else:
                    case = "archived_conflict"

            else:
                case = "old"

        # Case: active id.
        else:
            event = self.event_index[event_id].event

            if report.revision_num > event.revision:
                # Greater revision → correct, using the report's revision
                # (not current + 1). Section 6: "substitute the current data
                # with the report's revision". If we let apply_correction
                # increment, the event would end at revision current + 1
                # instead of the revision the station actually claims.
                case = "corrected"
                changes = {
                    "magnitude": report.magnitude,
                    "depth": report.depth,
                    "x": report.x,
                    "y": report.y,
                    "occurred_at": report.occurred_at,
                    "revision": report.revision_num,
                }
                self.correct_event(event_id, changes)
                inner_action = self.undo_stack.pop()

                # Add the report's station if it was not there.
                # If adding it "had an effect", save its id so it can be
                # removed when undoing the queue step.
                if report.station not in event.stations:
                    event.stations.add(report.station)
                    confirmed_station_id = report.station.station_id

            elif report.revision_num == event.revision:
                # Same revision → same data?
                same_data = (
                    report.magnitude == event.magnitude
                    and report.depth == event.depth
                    and report.x == event.x
                    and report.y == event.y
                    and report.occurred_at == event.occurred_at
                )
                if same_data:
                    # Confirmation.
                    case = "confirmed"
                    if report.station not in event.stations:
                        event.stations.add(report.station)
                        confirmed_station_id = report.station.station_id
                else:
                    # Conflict: the event is not touched.
                    case = "conflict"

            else:
                # Lower revision → old.
                case = "old"

        # Counters from the changes made on the step.
        # The corrections and reactivations were already counted inside of correct_event
        # / archived_reactivation (and its delta comes in inner_action)
        counter_delta = {}
        if case in ("conflict", "archived_conflict"):
            counter_delta["conflicts"] = 1
        elif case in ("old", "eliminated"):
            counter_delta["reports_discarded"] = 1
        self._add_counters(counter_delta)

        # 4. Now actually remove the report from the queue.
        self.report_queue.dequeue()

        # 5. Push the step action. Even if the case did not modify anything
        # (conflict, old, eliminated, archived not reactivated), the action
        # saves the report and its position so it can be put back in the
        # queue on undo.
        self.undo_stack.push(QueueStepAction(
            report=report,
            queue_position=queue_position,
            inner_action=inner_action,
            confirmed_station_id=confirmed_station_id,
            counter_delta=counter_delta,
        ))

        # 6. Return info about the step, so the frontend can show what
        # happened. Section 8: station, event, revision, decision and
        # rotations. The rotations come from the inner operation (create,
        # correct or reactivate); the other cases do not touch the trees.
        checkpoint = getattr(inner_action, "tree_checkpoint", None) or {}
        return {
            "case": case,
            "event_id": event_id,
            "revision_num": report.revision_num,
            "station_id": report.station.station_id,
            "rotations": list(checkpoint.get("rotations", [])),
            "rotation_delta": dict(checkpoint.get("rotation_delta", {})),
            "report": report,
        }
    
    """=========================================================================================="""\
    """====================================== EVENT METHODS ======================================"""\
    """=========================================================================================="""

    def create_event(self, event_id: int, magnitude: float, depth: float, x: float, y: float,
                    occurred_at, stations: set, revision: int = 1) -> Event:
        """Triggered by the UI when the user clicks 'create event'. Builds the
        event from scratch.

        The `revision` parameter defaults to 1, which is the manual creation
        case (section 6: "assign revision 1"). A different value is used when
        the event is created from a processed report, because section 6 says:
        "the first revision received may be greater than 1".

        An event A is a candidate reference of B when it has greater
        magnitude and occurred strictly before...
        A = the event that will be the reference (the candidate).
        B = the event being referenced (the one that "needs" a reference)."""

        if self._id_exists(event_id):
            raise ValueError(f"El identificador {event_id} ya existe")

        # An event cannot happen after the current simulation clock.
        # it gets validated here so an event from the future cannot be created
        if self._as_utc(occurred_at) > self.simulation_clock:
            raise ValueError(
                f"La fecha del evento {event_id} es posterior al reloj de simulación"
            )

        is_populated = self.epicenter_in_populated_zone(x, y)

        # Here the new event is born (we call it B).
        event = Event(
            event_id=event_id, magnitude=magnitude, depth=depth,
            x=x, y=y, occurred_at=occurred_at, revision=revision,
            stations=stations, is_in_populated_zone=is_populated,
        )

        balance = (self.mode == Mode.NORMAL)

        # Snapshot of the trees before insertion (so the undo returns to the same state)
        checkpoint = self._tree_checkpoint()
        node = self.avl_tree.insert(event, balance=balance)
        self.bst_tree.insert(event)
        self.event_index[event_id] = node
        self._close_tree_checkpoint(checkpoint)

        # Look for existing events that could now have B as a new candidate
        # (section 7). An event X can only have B as a candidate if B occurred
        # BEFORE X and has GREATER magnitude than X.
        # This happens with late reports: B is new to the system but its
        # occurrence time is earlier than that of already registered events.
        affected_others = [other for other in self._all_active_and_archived_events()
            if other.event_id != event_id
            and other.occurred_at > event.occurred_at
            and other.magnitude < event.magnitude
        ]

        # Save a snapshot of the references BEFORE recalculating, so we can
        # undo. B enters with None because it did not exist before. Each other
        # affected event saves its current reference_id (the one that will
        # change).
        old_references = {event_id: None}
        for other in affected_others:
            old_references[other.event_id] = other.reference_id

        # Recalculate B's reference (it looks for its candidates among the old
        # events) and the reference of each affected event (B now appears as a
        # candidate).
        self._recalculate_reference(event)
        for other in affected_others:
            self._recalculate_reference(other)

        # Push the action with B's id and the snapshot of old references, so
        # undo() can restore everything this creation changed.
        self.undo_stack.push(CreationAction(event_id, old_references, tree_checkpoint=checkpoint))

        return event

    def get_event(self, event_id: int) -> dict:
        """Look up an event by id. Returns the whole event object if it is
        active, and the id with its status (eliminated or archived) if it is
        not. If archived or eliminated, only the id is returned (the archived
        case could return the full object, but for consistency with the
        eliminated case, only the id is returned)."""
        # Active
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
        # Archived: keeps its identity, data and associations (section 6),
        # so its data and associations are returned too. It has no node in
        # the AVL, so depth, height and balance factor are None.
        if event_id in self.archived_history:
            event = self.archived_history[event_id]
            return {
                "status": "archived",
                "event_id": event_id,
                "event": event,
                "revision": event.revision,
                "stations": event.stations,
                "is_in_populated_zone": event.is_in_populated_zone,
                "priority": event.priority,
                "key": event.key,
                "attention_status": event.attention_status,
                "depth": None,
                "height": None,
                "balance_factor": None,
                "associations": self._build_associations(event_id),
            }

        # Eliminated
        if event_id in self.eliminated_IDs:
            return {
                "status": "eliminated",
                "event_id": event_id,
                "event": None,
            }

        raise KeyError(f"No existe un evento con id {event_id}")

    def correct_event(self, event_id: int, changes: dict) -> Event:
            """Manual correction of an active event (PUT /events/{id}).

            `changes` is a dict with the fields to touch: magnitude, depth, x, y,
            occurred_at. Whatever is not in the dict keeps its current value.
            event_id cannot be corrected (it is immutable). occurred_at can,
            even though it is not in K, because it affects the associations.

            Steps (same order as create_event, but on an existing event):
            1. Validate that it is active.
            2. Save a snapshot of the old values.
            3. If the epicenter changes, recalculate populated zone.
            4. Apply the correction on the same Event object.
            5-6. Relocate in AVL/BST if the key changed.
            7-10. Recalculate associations (own + affected).
            11. Push CorrectionAction so it can be undone.
            12. Return the event.
            """

            # 1. Validation: only an ACTIVE event can be corrected.
            if event_id in self.archived_history:
                raise ValueError(f"El evento {event_id} está archivado, no se puede corregir")
            if event_id in self.eliminated_IDs:
                raise ValueError(f"El evento {event_id} está eliminado, no se puede corregir")
            if event_id not in self.event_index:
                raise KeyError(f"No existe un evento con id {event_id}")

            # The corrected date cannot be after the clock (section 3).
            # Validated here, before modifying anything.
            if changes.get("occurred_at") is not None:
                if self._as_utc(changes["occurred_at"]) > self.simulation_clock:
                    raise ValueError(
                        f"La fecha corregida del evento {event_id} es posterior "
                        f"al reloj de simulación"
                    )

            node = self.event_index[event_id]
            event = node.event

            # 2. Snapshot of the old values, read from the event BEFORE touching it.
            old_magnitude = event.magnitude
            old_depth = event.depth
            old_x = event.x
            old_y = event.y
            old_occurred_at = event.occurred_at
            old_is_in_populated_zone = event.is_in_populated_zone
            old_revision = event.revision
            old_attention_status = event.attention_status

            # 3. If x or y changes, the populated zone must be recalculated with
            # the COMPLETE epicenter: if only one of the two is given, the other
            # is filled with the event's current value (same pattern as
            # update_zone with its "changes").
            is_in_populated_zone = None
            if "x" in changes or "y" in changes:
                new_x = changes.get("x", event.x)
                new_y = changes.get("y", event.y)
                is_in_populated_zone = self.epicenter_in_populated_zone(new_x, new_y)

            # 4. Apply the correction. Mutates the same event object and returns
            # the key before and the key after.
            old_key, new_key = event.apply_correction(
            magnitude=changes.get("magnitude"),
            depth=changes.get("depth"),
            x=changes.get("x"),
            y=changes.get("y"),
            occurred_at=changes.get("occurred_at"),
            revision=changes.get("revision"),
            is_in_populated_zone=is_in_populated_zone,
        )
            # 5-6. If the key changed (priority went up/down, or M changed), it
            # must be removed from the trees with the old key and reinserted with
            # the new one. event_index is updated with the NEW node.
            balance = (self.mode == Mode.NORMAL)

            # Snapshot of trees BEFORE relocating (for exact undo).
            checkpoint = self._tree_checkpoint()
            if old_key != new_key:
                self.avl_tree.delete(old_key, balance=balance)
                self.bst_tree.delete(old_key)
                new_node = self.avl_tree.insert(event, balance=balance)
                self.bst_tree.insert(event)
                self.event_index[event_id] = new_node
            self._close_tree_checkpoint(checkpoint)

            # 7. Group 1: other events that could have gained or lost this event
            # as a new candidate. The RANGE between the old and the new value is
            # used, because:
            #   - If the date moved to a MORE RECENT one, some events stop having
            #     it as candidate (they were between the new and the old date).
            #   - If the date moved to an OLDER one, some events gain it.
            #   - Same with magnitude: if it went down, some stop having it; if
            #     it went up, some gain it.
            # Using min/max covers both directions. It recalculates a bit more,
            # but no reference is left outdated.
            min_occurred = min(old_occurred_at, event.occurred_at)
            max_magnitude = max(old_magnitude, event.magnitude)

            affected_group_1 = [
                other for other in self._all_active_and_archived_events()
                if other.event_id != event_id
                and other.occurred_at > min_occurred
                and other.magnitude < max_magnitude
            ]

            # 8. Group 2: events that ALREADY had this event as reference before
            # the correction. They are taken from the inverse index.
            group_2_ids = self.referenced_by.get(event_id, set())
            affected_group_2 = [self._find_any_event(other_id) for other_id in group_2_ids]

            # Union without duplicates (an event could be in both groups).
            affected_others = {other.event_id: other for other in affected_group_1 + affected_group_2}.values()

            # 9. Snapshot of old references: the event itself + all the affected
            # ones, BEFORE recalculating anything.
            old_references = {event_id: event.reference_id}
            for other in affected_others:
                old_references[other.event_id] = other.reference_id

            # 10. Recalculate: first the event itself, then each affected one.
            self._recalculate_reference(event)
            for other in affected_others:
                self._recalculate_reference(other)

            # Counter of accepted correction
            counter_delta = {"corrections_accepted": 1}
            self._add_counters(counter_delta)

            # 11. Push the action so all of this can be undone in one go.
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
                counter_delta=counter_delta,
                tree_checkpoint=checkpoint,
            ))

            # 12. Return the corrected event.
            return event

    def mark_reviewed(self, event_id: int) -> Event:
            """Mark an active event as reviewed (section 'Attention status').

            Does not touch P, M or I, so it does not change the key, does not
            reinsert anything in the trees, and does not affect associations.
            """

            # 1. Validation: same criterion as correct_event, only an ACTIVE
            # event can be marked as reviewed.
            if event_id in self.archived_history:
                raise ValueError(f"El evento {event_id} está archivado, no se puede marcar como revisado")
            if event_id in self.eliminated_IDs:
                raise ValueError(f"El evento {event_id} está eliminado, no se puede marcar como revisado")
            if event_id not in self.event_index:
                raise KeyError(f"No existe un evento con id {event_id}")

            event = self.event_index[event_id].event

            # Already reviewed: nothing changes, so no action is pushed (the
            # user would otherwise have to undo a step that did nothing).
            if event.attention_status == AttentionStatus.REVIEWED:
                return event

            # 2. Snapshot of the old value, before changing it. It is the only
            # thing that needs to be saved to be able to undo.
            old_attention_status = event.attention_status

            # 3. Apply the change on the same object.
            event.mark_as_reviewed()

            # 4. No tree/event_index/associations step: the key did not change,
            # so the event position in the AVL and BST is still valid as is, and
            # associations do not depend on this field.

            # 5. Push the action so it can be undone.
            self.undo_stack.push(AttentionChangeAction(event_id, old_attention_status))

            # 6. Return the event already marked.
            return event

    def delete_event(self, event_id: int) -> Event:
            """Individual deletion of an active event (section 'Individual
            deletion'). Only removes THAT event; its descendants in the AVL stay
            intact (guaranteed by the tree's own delete()).

            There is no Group 1 here: an event that leaves the system cannot
            become a new candidate for anyone. Only those that ALREADY had it as
            reference need to be notified (Group 2).
            """

            # 1. Validation: same criterion as correct_event and mark_reviewed,
            # only an ACTIVE event can be deleted.
            if event_id in self.archived_history:
                raise ValueError(f"El evento {event_id} está archivado, no se puede eliminar así")
            if event_id in self.eliminated_IDs:
                raise ValueError(f"El evento {event_id} ya está eliminado")
            if event_id not in self.event_index:
                raise KeyError(f"No existe un evento con id {event_id}")

            node = self.event_index[event_id]
            event = node.event
            key = event.key  # saved now because, once deleted, there is nowhere to get it from

            # 2-3. Save the event's own reference BEFORE clearing it, and clear it
            # with _assign_reference (it already knows how to update referenced_by
            # without desyncing). If not saved first, the value is lost the moment
            # it is called.
            old_references = {event_id: event.reference_id}
            self._assign_reference(event, None)

            # 4. Remove the event from the three active structures. The order
            # between these three does not matter: we already have `event` saved
            # in a variable, we do not depend on it being in any of them.
            balance = (self.mode == Mode.NORMAL)
            # Snapshot of trees BEFORE deleting (for exact undo).
            checkpoint = self._tree_checkpoint()
            self.avl_tree.delete(key, balance=balance)
            self.bst_tree.delete(key)
            del self.event_index[event_id]
            self._close_tree_checkpoint(checkpoint)

            # Register the id as eliminated. This is what prevents a later report
            # from reactivating it (section 'Individual deletion').
            self.eliminated_IDs.add(event_id)

            # 5. Group 2: those that ALREADY had this event as reference. The list
            # is obtained (it is just a dict.get, does not depend on the trees),
            # but it is RECALCULATED after the event has left the AVL/BST — if it
            # were done before, get_candidates would still see it as valid and
            # someone would end up pointing to an event that no longer exists.
            affected_ids = self.referenced_by.get(event_id, set())
            affected = [self._find_any_event(other_id) for other_id in affected_ids]

            for other in affected:
                old_references[other.event_id] = other.reference_id

            for other in affected:
                self._recalculate_reference(other)

            # 6. Push the action: the complete event (to reinsert it as-is when
            # undoing) and the old references of all affected events.
            self.undo_stack.push(DeletionAction(event, old_references, tree_checkpoint=checkpoint))

            # 7. Return the event already deleted (the saved one, not the one from
            # the structure).
            return event
    
    def archived_reactivation(self, report: Report) -> Event:
        """Reactivate an archived event when a report with a greater revision
        arrives (section 6: "An archived event keeps its identity. A valid
        greater revision reactivates it as pending in the AVL with its
        corrected data").

        It is like a correct_event, but starting from an event that is no
        longer in the tree: it must be inserted from scratch, not relocated.
        That is why it uses apply_correction() like correct_event, but the
        "before" of this event is being in archived_history, not in the AVL.

        Steps:
        1. Snapshot of the old values (to be able to undo).
        2. Remove the event from archived_history.
        3. Recalculate populated zone with the report's epicenter.
        4. Apply the correction with the report's data and the report's
           revision.
        5. Insert into AVL and BST, add to event_index.
        6. Recalculate references (own + affected).
        7. Push ReactivationAction so this reactivation can be undone.
        8. Return the reactivated event.

        NOTE: the report's station is intentionally NOT added here. That part
        was left for process_next_report, just like the "corrected" case: that
        way the caller can compare before/after and know if the station was
        new, so it can register confirmed_station_id in the QueueStepAction
        and remove it when undoing the whole step.

        Unlike the previous version, this function DOES push its own action
        (ReactivationAction): process_next_report pops it, just like it
        already does with CreationAction and CorrectionAction, to put it
        inside the QueueStepAction of the step.
        """
        event_id = report.event_id
        event = self.archived_history[event_id]

        # 1. Snapshot of old values.
        old_magnitude = event.magnitude
        old_depth = event.depth
        old_x = event.x
        old_y = event.y
        old_occurred_at = event.occurred_at
        old_is_in_populated_zone = event.is_in_populated_zone
        old_revision = event.revision
        old_attention_status = event.attention_status

        # 2. Remove from the archive (it is no longer archived).
        del self.archived_history[event_id]

        # 3. Recalculate populated zone with the report's epicenter.
        is_populated = self.epicenter_in_populated_zone(report.x, report.y)

        # 4. Apply the correction. The event was NOT in the tree, so the
        # (old_key, new_key) that apply_correction returns is not needed here
        # (that is for relocating, and the insertion below is from scratch).
        event.apply_correction(
            magnitude=report.magnitude,
            depth=report.depth,
            x=report.x,
            y=report.y,
            occurred_at=report.occurred_at,
            revision=report.revision_num,
            is_in_populated_zone=is_populated,
        )

        # 5. Insert into AVL and BST (creation, not relocation).
        balance = (self.mode == Mode.NORMAL)
        # Snapshot of the trees before the insertion (so undo returns to the same state)
        checkpoint = self._tree_checkpoint()
        node = self.avl_tree.insert(event, balance=balance)
        self.bst_tree.insert(event)
        self.event_index[event_id] = node
        self._close_tree_checkpoint(checkpoint)

        # 6. Recalculate references. Same scheme as correct_event:
        # Group 1 (could now have it as a new candidate, with old-new range)
        # + Group 2 (already had it as reference).
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

        # Snapshot of old references, BEFORE recalculating (same pattern as
        # correct_event/delete_event: the event itself + all affected ones).
        old_references = {event_id: event.reference_id}
        for other in affected_others:
            old_references[other.event_id] = other.reference_id

        self._recalculate_reference(event)
        for other in affected_others:
            self._recalculate_reference(other)

        # Section 14 counter: a reactivation is an accepted higher
        # revision, so it counts as an accepted correction.
        counter_delta = {"corrections_accepted": 1}
        self._add_counters(counter_delta)

        # 7. Push the action. This is what was missing before: without it,
        # these values were lost here and undo had nothing to work with.
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
            counter_delta=counter_delta,
            tree_checkpoint=checkpoint,
        ))

        # 8. Return the reactivated event.
        return event

    """--------------------------------------- EVENT HELPERS ---------------------------------------"""

    def epicenter_in_populated_zone(self, x: float, y: float) -> bool:
        """HELPER: tells whether an epicenter is inside a populated zone. An
        epicenter belongs to a zone if it is inside it or on its border
        (already handled by Zone.contains). This is the value passed to the
        event attribute: is_in_populated_zone."""
        for zone in self.zones:
            if zone.contains(x, y) and zone.is_populated:
                return True
        return False

    def _id_exists(self, event_id: int) -> bool:
        """HELPER: an id exists if it is in any of these three:
        self.event_index, self.archived_history, self.eliminated_IDs."""
        return (
            event_id in self.event_index
            or event_id in self.archived_history
            or event_id in self.eliminated_IDs
        )

    def _find_any_event(self, event_id: int) -> Event:
        """HELPER: looks up an active or archived event by id (not eliminated
        events, because for the system it makes no sense to search eliminated
        ones and because only ids are kept for them)."""

        if event_id in self.event_index:
            return self.event_index[event_id].event

        if event_id in self.archived_history:
            return self.archived_history[event_id]
        raise KeyError(f"No existe un evento activo o archivado con id {event_id}")

    def _all_active_and_archived_events(self) -> list[Event]:
        """HELPER: returns all active events (inorder traversal of the AVL,
        because I felt like it and because it already returns the events)
        followed by all archived ones. Does not include eliminated events."""

        events = list(self.avl_tree.inorder())
        events.extend(self.archived_history.values())
        return events
    
    def _event_status(self, event_id: int) -> Optional[str]:
        """Returns 'active', 'archived', or None if the id is in neither.

        Used to label the reference and the candidates in the associations
        block of get_event (section 7 asks to identify whether each result is
        active or archived)."""

        if event_id in self.event_index:
            return "active"

        if event_id in self.archived_history:
            return "archived"

        return None
    
    """=========================================================================================="""\
    """=================================== ASSOCIATIONS =========================================="""\
    """=========================================================================================="""

    # The following methods are helpers to compute and return the associations
    # of an event, so they can be shown when get_event is called.

    # An association between events has two parts:
    #   - The chosen reference → "B has A as a possible replica". It is stored
    #     (Event.reference_id).
    #   - The candidates → "these are all the A's that could be a reference
    #     for B". They are computed on the fly (get_candidates).

    def get_candidates(self, event_id: int) -> list[Event]:
        """Candidates to be the reference of event `event_id`: active or
        archived events with greater magnitude, occurred strictly before,
        within W hours and R km. Sorted by a deterministic criterion."""

        event = self._find_any_event(event_id)
        candidates = []

        for other in self._all_active_and_archived_events():
            if other.event_id == event.event_id:
                continue

            if other.magnitude <= event.magnitude:
                continue

            if other.occurred_at >= event.occurred_at:
                continue

            # Convert the datetimes to hours and get the difference between
            # both, to know whether it exceeds the time window or not.
            horas = (event.occurred_at - other.occurred_at).total_seconds() / 3600
            if horas > self.W:
                continue

            # Compute the distance between epicenters with Euclidean distance.
            distancia = ((event.x - other.x) ** 2 + (event.y - other.y) ** 2) ** 0.5
            if distancia > self.R:
                continue

            candidates.append(other)

        candidates.sort(key=lambda other: ((event.occurred_at - other.occurred_at).total_seconds() / 3600, ((event.x - other.x) ** 2 + (event.y - other.y) ** 2) ** 0.5,
            -other.magnitude,other.event_id,) # this can be changed but well, we don't really need that much efficiency
        )
        return candidates

    # -------------------------------- REFERENCES ---------------------------------

    def get_reference(self, event_id: int) -> Optional[Event]:
        """Return the event that is the reference of event `event_id`
        (may be active or archived), or None if it has no reference."""

        event = self._find_any_event(event_id)

        if event.reference_id is None:
            return None

        return self._find_any_event(event.reference_id)

    # INVERSE INDEX FOR REFERENCES AND ASSOCIATIONS
    #
    # It is a dictionary in Scenario that goes the reverse way of the normal
    # reference.
    #
    # Normal reference (Event.reference_id):
    #   B (id 5) -> A (id 3)
    #   Read as: "event 5 has event 3 as its reference".
    #
    # Inverse index (Scenario.referenced_by):
    #   {3: {5, 8}}
    #   Read as: "event 3 is the reference of events 5 and 8".
    #
    # It is the same information, but reversed.
    #
    # Because some operations need to answer: "who has me as their reference?"
    #
    # When you delete event 3, you need to quickly find everyone that depended
    # on it (5 and 8) to recalculate their references. Two options:
    #
    # Without the inverse index: you walk through all active and archived
    # events and, for each one, ask "is your reference 3?". Cost O(n) each
    # time.
    #
    # With the inverse index: you do self.referenced_by.get(3) and get
    # {5, 8} directly. Cost O(1).

    def _assign_reference(self, event: Event, new_reference_id: Optional[int]) -> None:
        """HELPER: this is the one that keeps Event.reference_id synchronized
        with referenced_by. Every time the reference of an event changes, this
        helper makes both changes together."""
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
        """HELPER: recalculate the reference of `event` from its current
        candidates. Picks the first candidate (already sorted) or None if
        there is none, and applies it through _assign_reference so the inverse
        index stays in sync. IT ONLY MODIFIES, it does not return anything.

        candidates[0] is the best option because get_candidates already sorted
        them. If the list is empty -> None. This covers the case of "the
        previous candidate no longer exists" (because it was deleted, for
        example). Uses _assign_reference so referenced_by stays in sync."""

        candidates = self.get_candidates(event.event_id)
        new_ref_id = candidates[0].event_id if candidates else None
        self._assign_reference(event, new_ref_id)

    def _build_associations(self, event_id: int) -> dict:
        """Build the associations block for get_event.

        Returns a dict with:
        - 'reference': the event chosen as reference (with its status), or
          None if it has none.
        - 'candidates': list of candidates (with their status), excluding the
          reference so it does not appear twice.

        The reference is always the first candidate returned by get_candidates
        (already sorted by the criterion), so here it is filtered out of the
        candidates list."""

        reference = self.get_reference(event_id)
        reference_id = reference.event_id if reference is not None else None

        # Reference block: None when the event has no reference.
        reference_data = None

        if reference is not None:

            reference_data = {"event": reference, "status": self._event_status(reference_id),
            }

        # Candidates block: the reference is skipped so it does not appear twice.
        candidates_data = [
            {"event": candidate, "status": self._event_status(candidate.event_id)}

            for candidate in self.get_candidates(event_id)

            if candidate.event_id != reference_id
        ]

        return {
            "reference": reference_data,
            "candidates": candidates_data,
        }

    """=========================================================================================="""
    """==================================== MASS ARCHIVE ========================================="""\
    """=========================================================================================="""

    def preview_branch_archive(self) -> dict:
        """Preview of the mass archive: says WHICH subtree would be archived
        if the user confirms. Does NOT modify anything.

        Section 10: "Before executing, the affected identifiers, their
        quantity, and the justification of the selection are shown."

        The frontend calls this to show a confirmation dialog. If the user
        accepts, it calls branch_archive(winner_root_id) to actually run it.

        If there is no eligible branch, returns {"eligible": False, ...}.
        Otherwise returns the winner info and the list of event ids that
        would be archived.

        What it does NOT do (important):
        - Does not detach anything from the tree.
        - Does not move events to archived_history.
        - Does not touch event_index.
        - Does not touch reference_id or referenced_by.
        - Does not push any action (nothing changed).
        """
        # 1. Ask the AVL for all eligible subtrees.
        # A subtree is eligible if all its events have low priority and
        # age greater than T hours (section 10).
        eligible = self.avl_tree.eligible_archive_subtrees(self.simulation_clock, self.T)

        # 2. No eligible subtree: inform and do not touch anything.
        if not eligible:
            return {"eligible": False, "reason": "No eligible branch found"}

        # 3. Pick the winner per section 10: largest node count, then
        # deepest root, then largest root id. max() with a tuple applies
        # the comparisons in that exact order.
        winner = max(
            eligible,
            key=lambda e: (e["size"], e["depth"], e["root_id"]),
        )

        # 4. Freeze the list of ids of the winning subtree. It is what will
        # be shown to the user and used at execution time (the set is fixed
        # before touching the tree so rotations do not change the list).
        event_ids = self.avl_tree.subtree_event_ids(winner["root"])

        # 5. Return info for the frontend.
        return {
            "eligible": True,
            "root_id": winner["root_id"],
            "size": winner["size"],
            "depth": winner["depth"],
            "event_ids": event_ids,
        }

    def branch_archive(self, winner_root_id: int) -> dict:
        """Run the mass archive of the eligible subtree whose root id is
        `winner_root_id` (section 10).

        Revalidates the winner: between the preview and this call the tree
        may have changed, so it recalculates eligible ones and confirms the
        id is still eligible. If it is not, it informs and keeps the state.

        Steps:
        1. Revalidate: recalculate eligible ones and find the winner with
           that id.
        2. Freeze event_ids BEFORE touching the tree (section 10: "the set
           corresponds to the topology at the start of the operation and
           stays fixed during it").
        3. Detach the subtree with detach_subtree.
        4. Capture rotation_delta from the rotations the detach produced.
        5. Move the events to the archive and remove them from event_index.
           reference_id and referenced_by are NOT touched: archived events
           still count for associations (sections 7 and 10).
        6. Push MassArchiveAction so it can be undone as a single action.
        """
        # 1. Revalidate.
        eligible = self.avl_tree.eligible_archive_subtrees(self.simulation_clock, self.T)
        matches = [e for e in eligible if e["root_id"] == winner_root_id]

        if not matches:
            return {
                "archived": False,
                "reason": f"Subtree with root id {winner_root_id} is not eligible anymore",
                "rotations": [],
                "rotation_delta": {},
            }

        # Section 10: the archived branch is the one chosen by the
        # tie-break (most nodes, then deepest root, then largest root id).
        # If the tree changed since the preview and another branch wins now,
        # do not archive: the user must confirm the new preview.
        current_winner = max(eligible, key=lambda e: (e["size"], e["depth"], e["root_id"]))
        if current_winner["root_id"] != winner_root_id:
            return {
                "archived": False,
                "reason": (
                    f"Subtree with root id {winner_root_id} is eligible but is not the "
                    f"winning branch anymore (now it is {current_winner['root_id']}); "
                    f"request a new preview"
                ),
                "rotations": [],
                "rotation_delta": {},
            }

        winner = matches[0]
        node = winner["root"]

        # 2. Freeze ids BEFORE touching the tree.
        event_ids = self.avl_tree.subtree_event_ids(node)

        # 3. Detach. In normal mode it rotates; in stress mode, it does not.
        balance = (self.mode == Mode.NORMAL)
        # Snapshot of the trees before detaching them
        checkpoint = self._tree_checkpoint()
        archived_root, former_parent, was_left_child = self.avl_tree.detach_subtree(
            node, balance=balance
        )

        # 4. Capture the rotation metrics delta from the detach.
        rotation_delta = self.avl_tree.last_rotation_delta()

        # 5. Move the events to the archive and remove them from the active
        # index. Also remove them from the BST so both trees stay in sync.
        events = self.avl_tree.subtree_events(archived_root)
        for event in events:
            self.bst_tree.delete(event.key)
            self.archived_history[event.event_id] = event
            del self.event_index[event.event_id]
        # NOTE: reference_id and referenced_by are NOT touched (associations).
        self._close_tree_checkpoint(checkpoint)

        # Counters for the historic
        counter_delta = {"mass_archives": 1, "archived_events": len(event_ids)}
        self._add_counters(counter_delta)

        # 6. Push the action (a single one for the whole archive).
        self.undo_stack.push(MassArchiveAction(
            archived_root=archived_root,
            former_parent=former_parent,
            was_left_child=was_left_child,
            event_ids=event_ids,
            rotation_delta=rotation_delta,
            counter_delta=counter_delta,
            tree_checkpoint=checkpoint,
        ))

        return {
            "archived": True,
            "root_id": winner_root_id,
            "size": winner["size"],
            "depth": winner["depth"],
            "event_ids": event_ids,
            "rotations": list(self.avl_tree.last_rotations),
            "rotation_delta": rotation_delta,
        }


    """==============================================="""
    """========= GLOBAL RECOVERY (SECTION 8) ========="""
    """==============================================="""

    def recover_balance(self) -> dict:
        """Global AVL recovery (section 8) as ONE undoable action (section 13).

        Steps:
        1. Snapshot of the tree shape BEFORE rotating. Saving only the root
           is not enough: rotations change the links of those same nodes.
        2. Repair using ONLY rotations, without emptying or rebuilding the
           tree. Works with imbalances greater than 2.
        3. Capture what was added to the metrics, to subtract it on undo.
        4. Audit (verify_structure). The mode goes back to NORMAL only if
           the audit confirms balance.
        5. Push GlobalRecoveryAction only if something changed (rotations
           happened or the mode changed).

        The BST is not touched: it is the comparison tree, it never rotates.
        Section 8 also says to pause report processing: in the backend there
        is no continuous processing (each step is a request), so the UI must
        stop its loop before calling this.

        Returns a dict with the previous mode, the new mode, the rotation
        cases, the elementary rotations, the rotation list, the metric
        delta, the audit report, and whether the action was recorded.
        Cost: O(n) plus rotations."""
        previous_mode = self.mode

        # 1. Snapshot BEFORE touching the tree.
        snapshot = self.avl_tree.snapshot_topology()

        # 2. Repair with rotations.
        rotations = self.avl_tree.recover_balance()

        # 3. Metric delta for this operation.
        rotation_delta = self.avl_tree.last_rotation_delta()

        # 4. Only go back to NORMAL mode if the audit confirms it.
        audit = self.verify_structure()
        if audit["is_valid"] and audit["is_avl"] and self.mode != Mode.NORMAL:
            self.mode = Mode.NORMAL
            audit = self.verify_structure()  # final report, already in normal mode

        # 5. Push only if something changed.
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

    def undo(self) -> dict:
        """Undo the last action pushed on the undo stack (section 13).

        Pops the top action and dispatches to the right helper using
        isinstance. Each action type has its own private helper that
        knows how to revert it.

        If the stack is empty, raises ValueError (the router translates
        it to 409).

        If the action is a type that undo() does not know how to handle,
        it is pushed back (so it is not lost) and NotImplementedError is
        raised.

        Returns a dict with info about what was undone, so the frontend
        can show it. For example:
            {"undone": "creation", "event_id": 7}
            {"undone": "parameter_change", "parameter": "W"}
            {"undone": "clock_advance"}
        """
        if self.undo_stack.is_empty():
            raise ValueError("No hay acciones para deshacer")

        action = self.undo_stack.pop()

        if isinstance(action, CreationAction):
            return self._undo_creation(action)
        elif isinstance(action, CorrectionAction):
            return self._undo_correction(action)
        elif isinstance(action, ReactivationAction):
            return self._undo_reactivation(action)
        elif isinstance(action, DeletionAction):
            return self._undo_deletion(action)
        elif isinstance(action, AttentionChangeAction):
            return self._undo_attention_change(action)
        elif isinstance(action, ParameterChangeAction):
            return self._undo_parameter_change(action)
        elif isinstance(action, ClockAdvanceAction):
            return self._undo_clock_advance(action)
        elif isinstance(action, QueueStepAction):
            return self._undo_queue_step(action)
        elif isinstance(action, MassArchiveAction):
            return self._undo_mass_archive(action)
        elif isinstance(action, GlobalRecoveryAction):
            return self._undo_global_recovery(action)
        elif isinstance(action, LoadAction):
            return self._undo_load(action)
        elif isinstance(action, ClearReportQueueAction):
            return self._undo_clear_report_queue(action)
        elif isinstance(action, ReportEnqueueAction):
            return self._undo_report_enqueue(action)
        elif isinstance(action, ZoneAction):
            return self._undo_zone_change(action)
        elif isinstance(action, StationAction):
            return self._undo_station_change(action)
        else:
            # Unknown action: push it back so it is not lost.
            self.undo_stack.push(action)
            raise NotImplementedError(
                f"undo() no sabe deshacer {type(action).__name__}"
            )

    def _undo_clear_report_queue(self, action: ClearReportQueueAction) -> dict:
        self.report_queue.clear()
        for report in action.reports:
            self.report_queue.enqueue(report)
        return {"undone": "report_queue_clear", "removed": len(action.reports)}

    def _undo_report_enqueue(self, action: ReportEnqueueAction) -> dict:
        removed = 0
        for report in action.reports:
            try:
                self.report_queue.remove(report)
                removed += 1
            except ValueError:
                pass
        action_name = "report_batch_enqueue" if action.batch else "report_enqueue"
        return {"undone": action_name, "count": removed}

    def _undo_zone_change(self, action: ZoneAction) -> dict:
        if action.operation == "create":
            #assert checks that the condition is met
            assert action.new_zone is not None
            zone = action.new_zone
            self.zones.remove(zone)
        elif action.operation == "update":
            assert action.old_zone is not None and action.new_zone is not None
            self.zones[action.index] = action.old_zone
            zone = action.new_zone
        else:
            assert action.old_zone is not None
            self.zones.insert(action.index, action.old_zone)
            zone = action.old_zone
        return {"undone": f"zone_{action.operation}", "zone_name": zone.name}

    def _undo_station_change(self, action: StationAction) -> dict:
        if action.operation == "create":
            assert action.new_station is not None
            del self.stations[action.new_station.station_id]
            station = action.new_station
        else:
            if action.new_station is not None:
                self.stations.pop(action.new_station.station_id, None)
            assert action.old_station is not None
            station = action.old_station
            items = list(self.stations.items())
            items.insert(action.index, (station.station_id, station))
            self.stations = dict(items)
        return {"undone": f"station_{action.operation}", "station_id": station.station_id}


    def _undo_creation(self, action: CreationAction) -> dict:
        """Undoes an event creation: it takes the event out of the active structures
        and reinstates the reference that the creation had changed.

        old_references can come with an input for the proper event created with None, it gets 
        ignored, because the event no longer exists and _find_any_event would fail. The others get reinstated.
        """
        event_id = action.event_id
        event = self.event_index[event_id].event

        # The created event comes from the inverted index.
        # if a reference had been assigned to it, referenced_by[reference]
        # will continue to name it an it would point to an event that no longer exists.
        self._assign_reference(event, None)

        # The trees return to the exact shape from before the insertion
        # and the rotations that were caused by the insertion get removed
        self._restore_tree_checkpoint(action.tree_checkpoint)
        del self.event_index[event_id]

        for other_id, old_ref in action.old_references.items():
            if other_id == event_id:
                continue
            self._assign_reference(self._find_any_event(other_id), old_ref)

        return {"undone": "creation", "event_id": event_id}

    def _undo_correction(self, action: CorrectionAction) -> dict:
        """Undoes a correction:
        1. Saves the current event key with the corrected data
        2. Reinstates the old values one by one
        3. If the key changed, relocates the node in AVL/BST
        4. Reinstates the references of every event that was affected.
        """
        event_id = action.event_id
        node = self.event_index[event_id]
        event = node.event

        event.magnitude = action.old_magnitude
        event.depth = action.old_depth
        event.x = action.old_x
        event.y = action.old_y
        event.occurred_at = action.old_occurred_at
        event.is_in_populated_zone = action.old_is_in_populated_zone
        event.revision = action.old_revision
        event.attention_status = action.old_attention_status

        # priority and key are @property: when reinstating the values, the old key
        # recalculates on its own. The trees go back to the exact shape they had before the correction
        # with the original node on its place (had the key changed, the correction would have created a new node)
        self._restore_tree_checkpoint(action.tree_checkpoint, [event_id])

        for other_id, old_ref in action.old_references.items():
            self._assign_reference(self._find_any_event(other_id), old_ref)

        self._revert_counters(action.counter_delta)

        return {"undone": "correction", "event_id": event_id}
    
    def _undo_reactivation(self, action: ReactivationAction) -> dict:
        """Undoes a reactivation

        Different from _undo_correction, the event does not get relocated,
        it gets completely deleted from the AVL and returns to archived_history,
        because before the reactivation, it wasn't on the AVL.

        Important order: The event must be located and removed
        using its current key before reinstating the old values.
        If they got reinstated first, event.key changes and would no longer
        match with the position where it was inserted in the tree.

        1. Takes the event out of the AVL/BST/event_index with its current key
        2. Reinstates the 7 old values over the same object.
        3. Returns it to archived_history
        4. Reinstates the references of the affected events, including itself.
        """
        event_id = action.event_id
        event = self.event_index[event_id].event

        # Restores the tree's state to before the reinsertion
        self._restore_tree_checkpoint(action.tree_checkpoint)
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

        self._revert_counters(action.counter_delta)

        return {"undone": "reactivation", "event_id": event_id}

    def _undo_deletion(self, action: DeletionAction) -> dict:
        """Undoes a deletion
        1. Removes the id from eliminated_IDs
        2. Reinserts the node in the AVL and BST
        3. Updates the event index with the event
        4. Reinstates the old references
        """
        event = action.event
        event_id = event.event_id

        self.eliminated_IDs.discard(event_id)

        # Trees to the same shape before deletion: the original node goes back to its position
        # (it does not get reinserted as a leaf)
        self._restore_tree_checkpoint(action.tree_checkpoint, [event_id])

        for other_id, old_ref in action.old_references.items():
            self._assign_reference(self._find_any_event(other_id), old_ref)

        return {"undone": "deletion", "event_id": event_id}

    def _undo_attention_change(self, action: AttentionChangeAction) -> dict:
        """Restores only the old attention status."""
        event = self._find_any_event(action.event_id)
        event.attention_status = action.old_attention_status
        return {"undone": "attention_change", "event_id": action.event_id}

    def _undo_parameter_change(self, action: ParameterChangeAction) -> dict:
        """Restores the old value of each parameter changed by the action.
        If any was W or R, also restores the references that the change
        had recalculated."""
        for name, old_value in action.old_values.items():
            setattr(self, name, old_value)

        if action.old_references is not None:
            for event_id, old_ref in action.old_references.items():
                self._assign_reference(self._find_any_event(event_id), old_ref)

        return {"undone": "parameter_change", "parameter": action.parameter_name}

    def _undo_clock_advance(self, action: ClockAdvanceAction) -> dict:
        """Restores the simulation clock to the exact previous instant."""
        self.simulation_clock = action.old_clock
        return {"undone": "clock_advance"}

    def _undo_queue_step(self, action: QueueStepAction) -> dict:
        """Undoes a queue step.

        Order:
        1. Remove the confirmed station (if applicable), BEFORE reverting
           inner_action: if inner_action was a creation, the event
           disappears and we could no longer remove the station from it.
        2. Revert inner_action (if present) by calling the corresponding
           helper.
        3. Return the report to the queue in its original position.
        """
        # 1. Confirmed station.
        if action.confirmed_station_id is not None:
            station = self.stations.get(action.confirmed_station_id)
            if station is not None:
                try:
                    event = self._find_any_event(action.report.event_id)
                    event.stations.discard(station)
                except KeyError:
                    # The event no longer exists (for example, it was a creation
                    # and was not yet reverted). No station to remove.
                    pass

        # 2. Revert inner_action if present.
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

        # 3. Subtract step's own counters (conflict or discarded).
        # inner_action counters were already subtracted by its own _undo_*.
        self._revert_counters(action.counter_delta)

        # 4. Return the report to the queue.
        self.report_queue.insert_at(action.queue_position, action.report)

        return {"undone": "queue_step", "event_id": action.report.event_id}

    def _undo_mass_archive(self, action: MassArchiveAction) -> dict:
        """Undoes a mass archive.

        Steps:
        1. Reattach the detached subtree in its original position,
           going up the path to rebalance.
        2. Traverse the subtree nodes and return them to event_index and
           remove them from archived_history.
        3. Subtract rotation_delta from metrics.

        Associations are not touched: archiving did not change them.
        """
        # Trees to the exact shape from before archiving (branch hangs from
        # where it was and ascent rotations are undone);
        # also subtracts rotations added by archiving.
        self._restore_tree_checkpoint(action.tree_checkpoint, action.event_ids)

        for event_id in action.event_ids:
            if event_id in self.archived_history:
                del self.archived_history[event_id]

        self._revert_counters(action.counter_delta)

        return {"undone": "mass_archive", "root_id": action.archived_root.event.event_id}

    def _undo_global_recovery(self, action: GlobalRecoveryAction) -> dict:
        """Undoes a global recovery: restores AVL topology
        and rotation metrics, and returns to previous mode."""
        self.avl_tree.restore_topology(action.topology_snapshot)
        self.avl_tree.revert_rotation_metrics(action.rotation_delta)
        self.mode = action.previous_mode
        return {"undone": "global_recovery"}

    def _undo_load(self, action: LoadAction) -> dict:
        """Undoes the loading of a scenario by restoring the previous state.

        action.previous_state is the dict built by _snapshot_full_state()
        right before loading (see "FULL SCENARIO STATE"): the
        original objects of the previous scenario, intact, with the
        real AVL and BST topology. Reassigned to self.
        """
        self._restore_full_state(action.previous_state)
        return {"undone": "load"}

    def first_k_pending(self, k: int) -> tuple[list[Event], int]:
        """First k events pending attention, in descending order
        of K = (P, M, I).

        Section 11, first query: "The first k events pending
        attention in descending order of K. k is a positive integer; if there
        are fewer pending, all available ones are shown."

        Decisions:
        - k <= 0 → ValueError. The specification requires "positive integer", so
            0 and negatives are not allowed.
        - Reverse-inorder (right, node, left) with early stopping is used:
            as soon as k pending events are gathered, it stops without
            visiting more nodes.
        - Returns tuple (event_list, examined_nodes). The specification
            requires reporting the count of examined AVL nodes.
        """
        if k <= 0:
            raise ValueError("k must be a positive integer")

        result = []
        counter = [0]
        self._collect_k_pending(self.avl_tree.root, k, result, counter)
        return result, counter[0]

    

    def _collect_k_pending(self, node, k, result, counter):
        """HELPER: reverse-inorder with early stopping. First right (high K),
        then node, then left (low K). Stops as soon as result
        has k elements."""
        if node is None or len(result) >= k:
            return

        self._collect_k_pending(node.right_son, k, result, counter)
        if len(result) >= k:
            return

        counter[0] += 1
        if node.event.attention_status == AttentionStatus.PENDING:
            result.append(node.event)

        self._collect_k_pending(node.left_son, k, result, counter)

    def event_associations(self, event_id: int) -> dict:
        """Returns the full associations of an event: candidates,
        chosen reference, and who uses it as reference.

        Section 11, fourth query: "Candidates and chosen reference for
        an event, as well as events using it as a reference. Each result
        identifies whether it is active or archived."

        THREE blocks are returned, not two, because the relationship is
        bidirectional: knowing who this event points to (reference) and who
        could be its reference (candidates) is not enough. We also must
        know who points to it. Without that third part, the query would
        only provide half the association network: outgoing, but not incoming.
        Candidates and reference come from _build_associations (which get_event
        already uses). The third block comes from inverse index referenced_by,
        which exists specifically to answer "who has me as reference" without
        traversing all events.

        There are two methods (get_event and event_associations) because they serve
        two distinct purposes:
        - get_event returns EVERYTHING about an event: data, revision,
        stations, priority, status, depth, height, balance factor, and
        associations as one more block. It is the full view of an event.
        - event_associations focuses ONLY on the association network, and
        adds the "who uses me" block that get_event does not include. It is the
        specific view when frontend wants to show the aftershock network
        of an event without loading its full sheet.

        If id does not exist or is eliminated, raises ValueError: eliminated
        events are not part of system (only their id remains in
        eliminated_IDs), so querying their associations makes no sense.

        Returns a dict with:
            {
                "reference": {"event": Event, "status": "active"|"archived"} or None,
                "candidates": [{"event": Event, "status": ...}, ...],
                "used_as_reference_by": [{"event": Event, "status": ...}, ...],
            }
        `candidates` does not include reference (already in its own
        block). `used_as_reference_by` may be empty if nobody uses it
        as reference.

        Does not report examined nodes: other section 11 queries
        do because they directly navigate AVL; here only a dict is read
        (referenced_by) and candidate calculation is delegated to
        _build_associations, which is already a query in itself.
        """
        if event_id in self.eliminated_IDs:
            raise ValueError(f"El evento {event_id} está eliminado, no tiene asociaciones")
        if event_id not in self.event_index and event_id not in self.archived_history:
            raise ValueError(f"No existe un evento activo o archivado con id {event_id}")

        associations = self._build_associations(event_id)

        used_by_data = []
        for other_id in self.referenced_by.get(event_id, set()):
            other = self._find_any_event(other_id)
            used_by_data.append({
                "event": other,
                "status": self._event_status(other_id),
            })

        return {
            "reference": associations["reference"],
            "candidates": associations["candidates"],
            "used_as_reference_by": used_by_data,
        }

    def events_in_magnitude_range(self, min_mag: float, max_mag: float) -> tuple[list[Event], int]:
        """Active events with min_mag <= M <= max_mag (inclusive), in ascending
        order of K.

        Section 11, second query: "Events within an inclusive magnitude
        interval."

        Decisions:
        - min_mag > max_mag → ValueError. Invalid range.
        - The tree cannot be pruned: K orders by PRIORITY before
            magnitude, so a branch with low priority can contain
            any magnitude. The full tree is traversed (inorder).
        - Returns tuple (event_list, examined_nodes). The specification
            requires reporting the count of examined AVL nodes.
        """
        if min_mag > max_mag:
            raise ValueError("min_mag cannot be greater than max_mag")

        result = []
        counter = [0]
        self._collect_by_magnitude(self.avl_tree.root, min_mag, max_mag, result, counter)
        return result, counter[0]

    def _collect_by_magnitude(self, node, min_mag, max_mag, result, counter):
        """HELPER: full inorder traversal (left, node, right). Each non-empty
        node counts as examined."""
        if node is None:
            return
        counter[0] += 1
        self._collect_by_magnitude(node.left_son, min_mag, max_mag, result, counter)
        if min_mag <= node.event.magnitude <= max_mag:
            result.append(node.event)
        self._collect_by_magnitude(node.right_son, min_mag, max_mag, result, counter)

    def events_by_depth_and_date(self, max_depth: float, min_date: datetime, max_date: datetime) -> tuple[list[Event], int]:
        """Active events with depth <= max_depth AND min_date <= occurred_at <=
        max_date (both limits inclusive), in ascending order of K.

        Section 11, second query (second half): "events with hypocenter
        depth less than or equal to a limit within an inclusive date
        interval."

        Decisions:
        - min_date > max_date → ValueError. Same criterion as
        events_in_magnitude_range with min_mag > max_mag.
        - max_depth is not validated here (could be negative): data ranges
        are already validated by pydantic schema, same as the rest
        of Scenario.
        - The tree cannot be pruned: neither depth nor occurred_at are part of
        K = (P, M, I), not even secondarily (unlike magnitude,
        which is part of K though not the primary ordering). There is no
        relationship between node position and these two values.
        The full tree is traversed (inorder).
        - min_date/max_date are normalized with _as_utc before comparing,
        just as update_simulation_clock and _validate_report do with
        incoming timestamps: avoiding failures if timezone is missing
        or different from stored event.
        - Returns tuple (event_list, examined_nodes), same as other
        queries in this section (required by specification).
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
        """HELPER: full inorder traversal (left, node, right). Each non-empty
        node counts as examined."""
        if node is None:
            return
        counter[0] += 1
        self._collect_by_depth_and_date(node.left_son, max_depth, min_date, max_date, result, counter)
        event = node.event
        if event.depth <= max_depth and min_date <= event.occurred_at <= max_date:
            result.append(event)
        self._collect_by_depth_and_date(node.right_son, max_depth, min_date, max_date, result, counter)

    def costly_access_events(self) -> list[dict]:
        """Active high-priority events with costly access.

        Section 11, last query: "High-priority events with costly
        access, indicating node depth, limit, and number of nodes
        visited in their search by key."
        Section 9: a high-priority event (P = 3) has costly access
        when its depth in the AVL is STRICTLY greater than L.

        Wrapper around avl_tree.costly_access(L): the tree performs the
        traversal, but does not know L (only receives a number), so it
        cannot say which limit it compared against. Scenario does know it and
        adds it to each result.

        Returns a list of dicts, one per costly access event:
            {"event": Event, "depth": int, "visited": int, "limit": int}
        - depth: node depth (root = 0).
        - visited: nodes visited when searching by key = depth + 1.
        - limit: current L compared against.
        Empty list = no high-priority event exceeds L.

        self.L is read at query time, so if the user
        changes L (change_parameters) the next query uses the new one.
        Cost: O(n), traverses entire tree."""
        limit = self.L
        result = self.avl_tree.costly_access(limit)
        for item in result:
            item["limit"] = limit
        return result

    def verify_structure(self) -> dict:
        """Option "Verify structure" (section 14), available in both
        modes.

        Wrapper around avl_tree.audit(): the tree verifies EVERYTHING (global
        order by K against limits of all ancestors, uniqueness
        of ids, cycles or shared nodes, parent pointers, heights and
        balance factors recalculated against stored ones). What
        Scenario adds is current mode:
        - NORMAL mode → require_balance=True: a factor outside {-1, 0, 1}
          is an error.
        - STRESS mode → require_balance=False: imbalance is reported
          as "expected", distinct from order or metadata errors,
          as required by section 14.

        Returns a dict intended for direct frontend display:
            {
              "mode": "Normal" | "Stress",
              "checked_nodes": int,          # reviewed active events
              "is_valid": bool,              # True if no "error" exists
              "is_avl": bool,                # True if no imbalance exists
              "error_count": int,            # issues with severity "error"
              "expected_count": int,         # expected imbalances (stress)
              "inconsistent_event_ids": [int],  # one id per event with error
              "issues": [ {event_id, type, severity, detail}, ... ],
            }
        `issues` is the list returned by audit(); all its
        values are simple data (JSON ready). A single event can
        have multiple problems (e.g. height and factor), which is why
        inconsistent_event_ids groups them without duplicates.

        `is_valid` is what global recovery must check before
        returning to normal mode (section 8: "Return to normal mode only
        completes when audit confirms balance"): at that
        moment is_valid and is_avl are required.
        Cost: O(n)."""
        require_balance = (self.mode == Mode.NORMAL)
        issues = self.avl_tree.audit(require_balance=require_balance)

        errors = [issue for issue in issues if issue["severity"] == "error"]
        expected = [issue for issue in issues if issue["severity"] == "expected"]

        # Ids of events with real errors, unique and in appearance order
        # (None = global problem, e.g. size).
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
    def count_events_by_priority(self) -> dict:
        """Count active and archived events by priority.

        Section 14 (Audit and indicators): "The interface shall keep visible
        or accessible the following indicators: ... Events by priority,
        pending attention, and events marked with costly access."

        Both active AND archived events are counted (both are part of the system
        and both can be references for other events per Section 7). Eliminated
        events are NOT counted: they are not in the system, only their id remains.

        Calculated ON THE FLY, not accumulated: an event's priority can change
        (correction increasing magnitude, change in populated zone), and
        maintaining an accumulated counter would require adjusting it on each of
        those operations. It is simpler and more consistent to recalculate each time.

        Returns:
            {"P1": n, "P2": n, "P3": n}

        Cost: O(n).
        """
        counts = {"P1": 0, "P2": 0, "P3": 0}
        for event in self._all_active_and_archived_events():
            counts[f"P{event.priority}"] += 1
        return counts

    def get_indicators(self) -> dict:
        """Section 14 indicators in a single dictionary, so the
        interface can keep them visible (GET /indicators):

        - Count of active, archived (historical), and eliminated events,
          height, leaves, and all four AVL traversals (as ids).
        - Counters: accepted corrections, discarded reports,
          conflicts, mass archives, and archived events (COUNTER_KEYS).
        - LL, RR, LR, RL cases and simple rotations (ROTATION_METRIC_KEYS).
        - Events by priority (active + archived), pending
          attention (active), and costly access events (with the current L).

        Read-only: does not modify anything or push actions. Cost: O(n + a)."""
        active_events = self.avl_tree.inorder()
        pending = sum(
            1 for event in active_events
            if event.attention_status == AttentionStatus.PENDING
        )
        return {
            "mode": self.mode.value,
            "L": self.L,
            "active_events": len(self.avl_tree),
            "archived_events": len(self.archived_history),
            "eliminated_events": len(self.eliminated_IDs),
            "height": self.avl_tree.height(),
            "leaves": self.avl_tree.count_leaves(),
            "traversals": self._traversal_ids(self.avl_tree),
            "counters": {k: self.metrics.get(k, 0) for k in COUNTER_KEYS},
            "rotations": {k: self.metrics.get(k, 0) for k in ROTATION_METRIC_KEYS},
            "events_by_priority": self.count_events_by_priority(),
            "pending_attention": pending,
            "costly_access": len(self.avl_tree.costly_access(self.L)),
        }

    def compare_avl_bst(self) -> dict:
        """Compare AVL vs BST: height, leaves, and comparisons when searching
        the same keys. Section 11, last block: "AVL and BST will be compared
        via height, leaves, and comparisons when searching the same keys."

        For each active event, its key is searched in both trees. search()
        already returns (node, visited_nodes), so they are simply summed.

        LIMITATION: both trees are synchronized in the current state,
        but not with the same historical insertion order. If the scenario
        was built in ascending order, the BST is degenerate and the difference
        is enormous; if the order was random, the difference is subtler.
        The "all in ascending order" case is tested with specific data,
        not with this query.

        Returns two comparable blocks (avl and bst), each with size,
        height, leaves, total_comparisons, max_single_search, and
        avg_comparisons, plus n_searches.
        """
        # Keys of all active events, in ascending order of K.
        keys = [event.key for event in self.avl_tree.inorder()]

        # Sum visited nodes when searching each key in each tree.
        # max_* tracks the worst single search (maximum depth + 1).
        avl_total = 0
        avl_max = 0
        for key in keys:
            _, visited = self.avl_tree.search(key)
            avl_total += visited
            if visited > avl_max:
                avl_max = visited

        bst_total = 0
        bst_max = 0
        for key in keys:
            _, visited = self.bst_tree.search(key)
            bst_total += visited
            if visited > bst_max:
                bst_max = visited

        n = len(keys)
        return {
            "avl": {
                "size": len(self.avl_tree),
                "height": self.avl_tree.height(),
                "leaves": self.avl_tree.count_leaves(),
                "total_comparisons": avl_total,
                "max_single_search": avl_max,
                "avg_comparisons": (avl_total / n) if n else 0.0,
            },
            "bst": {
                "size": len(self.bst_tree),
                "height": self.bst_tree.height(),
                "leaves": self.bst_tree.count_leaves(),
                "total_comparisons": bst_total,
                "max_single_search": bst_max,
                "avg_comparisons": (bst_total / n) if n else 0.0,
            },
            "n_searches": n,
        } 


    """==============================================="""
    """====FULL STATE AND LOAD (SECTIONS 12-13)======="""
    """==============================================="""

    # COMPLETE SCENARIO STATE
    #
    # Everything that a load replaces and that LoadAction saves in order
    # to undo it: AVL (real structure), BST (real structure),
    # event_index, archived_history, eliminated_IDs, referenced_by, zones,
    # stations, report_queue, clock, L, W, R, T, mode, and metrics.
    #
    # Decision: ORIGINAL OBJECTS are saved, not deep copies.
    # - Safe because a load NEVER modifies the old state: it constructs
    #   new objects and assigns them to self (_restore_full_state). The old
    #   state remains intact inside LoadAction, with its exact topology
    #   (they are the same nodes, with the same links and heights).
    # - Preserving identity is NECESSARY: actions pushed BEFORE
    #   the load hold references to real nodes and events (for instance,
    #   MassArchiveAction holds archived_root and former_parent, which are
    #   AVLNode instances from the tree). If a deep copy were restored, those nodes
    #   would no longer be in the restored tree and undoing the archive would
    #   break.
    # - Memory: O(1) for the snapshot (only references), instead of O(n).
    #
    # The clock is saved as a VALUE (self.simulation_clock at that moment)
    # and restored with the setter, just like ClockAdvanceAction.
    #
    # The undo stack is NOT part of the state: it is history. The
    # LoadAction is pushed on top of previous actions, and when undoing
    # the load those actions apply again on the restored state.

    def _snapshot_full_state(self) -> dict:
        """HELPER: snapshot of the complete operational state (see above)."""
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
        """HELPER: replaces the operational state with that of `state` (a
        dict with the shape of _snapshot_full_state). Used by load_scenario
        (to set the new state) and _undo_load (to return to the old state).
        Does not touch undo_stack. Maintains that self.metrics is the SAME dict
        used by self.avl_tree (a single source of truth for rotations)."""
        self.avl_tree = state["avl_tree"]
        self.bst_tree = state["bst_tree"]
        self.event_index = state["event_index"]
        self.archived_history = state["archived_history"]
        self.eliminated_IDs = state["eliminated_IDs"]
        self.referenced_by = state["referenced_by"]
        self.zones = state["zones"]
        self.stations = state["stations"]
        self.report_queue = state["report_queue"]
        self.simulation_clock = state["simulation_clock"]
        self.L = state["L"]
        self.W = state["W"]
        self.R = state["R"]
        self.T = state["T"]
        self.mode = state["mode"]
        self.metrics = state["metrics"]
        self.avl_tree.metrics = self.metrics

    @staticmethod
    def _export_datetime(value: datetime) -> str:
        return Scenario._as_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _export_stored_event(event: Event) -> dict:
        return {
            "event_id": event.event_id,
            "magnitude": event.magnitude,
            "depth": event.depth,
            "x": event.x,
            "y": event.y,
            "occurred_at": Scenario._export_datetime(event.occurred_at),
            "revision": event.revision,
            "stations": sorted(station.station_id for station in event.stations),
            "attention_status": event.attention_status.value,
            "reference_id": event.reference_id,
        }

    def _export_avl_nodes(self, node: Optional[AVLNode], nodes: list[dict]) -> None:
        if node is None:
            return

        item = self._export_stored_event(node.event)

        #As the event lacks some properties that are needed for the load by insertions,
        #we add the missing properties with item.update()

        item.update({
            "priority": node.event.priority,
            "height": node.height,
            "balance_factor": node.balance_factor,
            "left_id": node.left_son.event.event_id if node.left_son else None,
            "right_id": node.right_son.event.event_id if node.right_son else None,
        })
        nodes.append(item)
        self._export_avl_nodes(node.left_son, nodes)
        self._export_avl_nodes(node.right_son, nodes)

    def _export_insertion_events(self, node: Optional[AVLNode], events: list[dict]) -> None:
        if node is None:
            return

        event = node.event
        station_ids = sorted(station.station_id for station in event.stations)
        if not station_ids:
            raise ValueError(f"Event {event.event_id} has no station and cannot be exported as insertions")
        events.append({
            "event_id": event.event_id,
            "magnitude": event.magnitude,
            "depth": event.depth,
            "x": event.x,
            "y": event.y,
            "occurred_at": self._export_datetime(event.occurred_at),
            "station_id": station_ids[0],
        })
        self._export_insertion_events(node.left_son, events)
        self._export_insertion_events(node.right_son, events)

    def export_scenario(self, load_mode: str = "topology") -> dict:
        """Return the scenario in either insertion or exact-topology load format."""
        if load_mode not in ("insertions", "topology"):
            raise ValueError("load_mode must be 'insertions' or 'topology'")

        data = {
            "load_mode": load_mode,
            "simulation_clock": self._export_datetime(self.simulation_clock),
            "parameters": {name: getattr(self, name) for name in ("L", "W", "R", "T")},
            "zones": [
                {
                    "name": zone.name,
                    "x_min": zone.x_min,
                    "x_max": zone.x_max,
                    "y_min": zone.y_min,
                    "y_max": zone.y_max,
                    "is_populated": zone.is_populated,
                }
                for zone in self.zones
            ],
            "stations": [
                {"station_id": station.station_id, "x": station.x, "y": station.y}
                for station in sorted(self.stations.values(), key=lambda item: item.station_id)
            ],
        }

        if load_mode == "insertions":
            events: list[dict] = []
            self._export_insertion_events(self.avl_tree.root, events)
            data["events"] = events
            return data

        avl_nodes: list[dict] = []
        self._export_avl_nodes(self.avl_tree.root, avl_nodes)
        data.update({
            "avl": {
                "root_id": self.avl_tree.root.event.event_id if self.avl_tree.root else None,
                "nodes": avl_nodes,
            },
            "archived": [
                self._export_stored_event(event)
                for event in sorted(self.archived_history.values(), key=lambda item: item.event_id)
            ],
            "eliminated_ids": sorted(self.eliminated_IDs),
            "report_queue": [
                {
                    "event_id": report.event_id,
                    "revision_num": report.revision_num,
                    "station_id": report.station.station_id,
                    "magnitude": report.magnitude,
                    "depth": report.depth,
                    "x": report.x,
                    "y": report.y,
                    "occurred_at": self._export_datetime(report.occurred_at),
                }
                for report in self.report_queue.items()
            ],
            "mode": self.mode.value,
            "metrics": dict(self.metrics),
        })
        return data

    def load_scenario(self, data: dict, from_version: bool = False) -> dict:
        """Load a full scenario from a JSON-like dict, as an undoable action.

        Validates the input completely before touching the current state. If
        anything is wrong, raises ValueError with the exact location of the
        problem and the current scenario is left untouched. If everything is
        valid, replaces the operational state with the new one and pushes a
        LoadAction so the previous state can be restored with undo().

        Parameters
        ----------
        data : dict
            The archive content, already parsed from JSON. Must follow the
            schema described below.
        from_version : bool, default False
            True when the source is a saved version (self.versions), False
            when it is an arbitrary file. This only affects one rule: a
            version saved in Stress mode with an unbalanced topology can be
            restored as-is, while an arbitrary file with the same topology is
            rejected unless the current scenario is already in Stress mode.

        Returns
        -------
        dict
            A short summary of the loaded scenario:
            - load_mode, mode
            - active_events, archived_events, eliminated_ids, queued_reports
            - warnings: non-fatal messages (for example, unbalanced topology
            loaded in Stress mode)
            - inherited: names of the optional sections that were not present
            in the file and were taken from the current scenario
            - avl, bst: root_id, height, max_depth and leaves of each tree

        Raises
        ------
        ValueError
            If the archive is malformed, has inconsistent references, has
            duplicated ids, has invalid ranges/dates, or violates any
            structural rule. The message always starts with "Carga
            rechazada." and points to the exact section (for example
            "avl.nodes[3]") and the reason.

        Undo behaviour
        --------------
        Load is undoable as a single action. When it succeeds, it does:
            1. previous_state = self._snapshot_full_state()
            2. self._restore_full_state(new_state)
            3. self.undo_stack.push(LoadAction(previous_state))
        The previous state is kept by reference (not deep-copied), because
        the load never mutates it: it builds a brand-new state and assigns it
        to self. Actions pushed before the load (for example a
        MassArchiveAction) hold references to the real nodes of the old
        state, so preserving identity is required for those actions to still
        work after undoing the load.

        Archive schema
    --------------
        Common fields:
            load_mode        : "insertions" | "topology"  (required)
            simulation_clock : ISO 8601 with timezone, e.g. "2026-09-07T12:00:00Z"
            parameters       : {"L", "W", "R", "T"}
            zones            : [{"name", "x_min", "x_max", "y_min", "y_max",
                                "is_populated"}]
            stations         : [{"station_id", "x", "y"}]

        Every optional field that is omitted is inherited from the current
        scenario. The names of the inherited fields are reported in the
        result under "inherited". Inherited containers (zones, stations) are
        copied into NEW containers so they cannot be mutated by accident
        through the state saved in LoadAction.

        Mode "insertions"
        -----------------
            events : [{"event_id", "magnitude", "depth", "x", "y",
                    "occurred_at", "station_id"}, ...]

            Each event is inserted in order using create_event, which means
            the AVL rebalances and the BST follows. The resulting scenario
            stays in Normal mode and starts with:
            - revision 1, status pending, associations rebuilt
            - no archived events, no eliminated ids, no queued reports
            - metrics reset to zero plus the rotations produced by this load

        Mode "topology"
        ---------------
            avl : {
                "root_id": int | null,
                "nodes": [{
                    "event_id", "magnitude", "depth", "x", "y",
                    "occurred_at", "revision", "stations": [ids],
                    "attention_status": "pending" | "reviewed",
                    "priority", "height", "balance_factor",
                    "left_id": int | null,
                    "right_id": int | null,
                    "reference_id" (optional; if present, it is verified)
                }]
            }
            archived       : [event dict, same shape as a real event]
            eliminated_ids : [int]
            report_queue   : [{"event_id", "revision_num", "station_id",
                            "magnitude", "depth", "x", "y", "occurred_at"}]
            mode           : "Normal" | "Stress"
            metrics        : {"LL": 0, ...}

            The topology is restored without reinserting. The BST is rebuilt
            by inserting the AVL nodes in preorder, so it ends with the same
            shape as the loaded AVL. Stored priority, height, balance factor
            and (if present) reference_id are checked against the values
            computed from the file. Dates must be ISO 8601 with timezone,
            either as strings or as datetime objects.
        """

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
            new_state, warnings = self._build_state_from_topology(data, general, from_version)

        # Everything validated: now apply it.
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
    # ---------------- LOAD HELPERS ----------------

    _INSERTION_EVENT_FIELDS = ("event_id", "magnitude", "depth", "x", "y", "occurred_at", "station_id")
    _STORED_EVENT_FIELDS = ("event_id", "magnitude", "depth", "x", "y", "occurred_at",
                            "revision", "stations", "attention_status")
    _TOPOLOGY_NODE_FIELDS = _STORED_EVENT_FIELDS + ("priority", "height", "balance_factor", "left_id", "right_id")
    _REPORT_FIELDS = ("event_id", "revision_num", "station_id", "magnitude", "depth", "x", "y", "occurred_at")
    # Order in which audit errors are reported when loading
    # (first references and uniqueness, then order, then metadata).
    _AUDIT_ERROR_ORDER = ("reference", "uniqueness", "size", "order", "height", "balance_factor")

    @staticmethod
    def _load_error(where: str, message: str) -> ValueError:
        """HELPER: load error with the exact location of the issue."""
        return ValueError(f"Carga rechazada. {where}: {message}")

    @staticmethod
    def _load_tree_summary(tree) -> dict:
        """HELPER: root, height, maximum depth, and leaves (section 12).
        The maximum depth of a tree is its height (root = 0)."""
        height = tree.height()
        return {
            "root_id": tree.root.event.event_id if tree.root is not None else None,
            "height": height,
            "max_depth": height if height >= 0 else None,
            "leaves": tree.count_leaves(),
        }

    def _load_require(self, raw, fields, where: str) -> None:
        """HELPER: `raw` must be an object with all `fields`."""
        if not isinstance(raw, dict):
            raise self._load_error(where, "debe ser un objeto")
        missing = [field for field in fields if field not in raw]
        if missing:
            raise self._load_error(where, f"faltan campos obligatorios: {', '.join(missing)}")

    def _load_list(self, data: dict, key: str, required: bool = False) -> list:
        """HELPER: reads a list from the file ([] if optional and omitted)."""
        if key not in data:
            if required:
                raise self._load_error(key, "falta esta sección")
            return []
        value = data[key]
        if not isinstance(value, list):
            raise self._load_error(key, "debe ser una lista")
        return value

    def _load_number(self, value, where: str, field: str, low: float, high: float, one_decimal: bool = True) -> float:
        """HELPER: finite number in [low, high], with at most one decimal place
        (same criterion as _check_one_decimal in schemas/report.py)."""
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
        """HELPER: integer (not boolean) in [low, high]."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise self._load_error(where, f"{field} debe ser un entero (llegó {value!r})")
        if value < low or (high is not None and value > high):
            limit = f"[{low}, {high}]" if high is not None else f">= {low}"
            raise self._load_error(where, f"{field} = {value} fuera del rango {limit}")
        return value

    def _load_datetime(self, value, where: str, field: str) -> datetime:
        """HELPER: ISO 8601 datetime with timezone and seconds precision,
        normalized to UTC (same criterion as ReportCreate)."""
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
        """HELPER: station id, non-empty string (like StationCreate)."""
        if not isinstance(value, str) or not value:
            raise self._load_error(where, f"{field} debe ser un texto no vacío")
        return value

    def _load_event_values(self, raw: dict, where: str, clock: datetime) -> dict:
        """HELPER: physical data of an event (sections 3 and 12): id,
        magnitude, depth, epicenter, and date (not later than the clock)."""
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
        """HELPER: stored event (active or archived): physical data +
        revision, accepted stations, and attention status."""
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
        """HELPER: clock, parameters, zones, and stations from the file.
        Omitted fields are inherited from the current scenario (in NEW
        containers, avoiding shared lists/dicts with the old state saved
        in LoadAction)."""
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
        """HELPER: same rule as epicenter_in_populated_zone, but using
        the zones from the FILE (not those of the current scenario)."""
        return any(zone.contains(x, y) and zone.is_populated for zone in zones)

    def _build_state_from_insertions(self, data: dict, general: dict) -> tuple[dict, list]:
        """HELPER: mode 1, load by insertions. Validates in the agreed
        order (fields, ranges, and dates, unique ids, stations) and
        builds the new state in a TEMPORARY Scenario using
        create_event, reusing the exact same registration logic
        (populated zone, priority, balanced AVL, BST, event_index, and
        associations). self is not touched."""
        events = self._load_list(data, "events", required=True)

        # 1. Mandatory fields for all events.
        for i, raw in enumerate(events):
            self._load_require(raw, self._INSERTION_EVENT_FIELDS, f"events[{i}]")

        # 2. Ranges and dates (not after the clock).
        parsed = []
        for i, raw in enumerate(events):
            where = f"events[{i}]"
            values = self._load_event_values(raw, where, general["clock"])
            values["station_id"] = self._load_station_id(raw["station_id"], where, "station_id")
            parsed.append(values)

        # 3. Unique ids (a duplicate id invalidates the file, section 12).
        first_position = {}
        for i, values in enumerate(parsed):
            event_id = values["event_id"]
            if event_id in first_position:
                raise self._load_error(
                    f"events[{i}]", f"event_id {event_id} repetido (ya aparece en events[{first_position[event_id]}])"
                )
            first_position[event_id] = i

        # 4. Each event's station must exist.
        for i, values in enumerate(parsed):
            if values["station_id"] not in general["stations"]:
                raise self._load_error(f"events[{i}]", f"la estación {values['station_id']!r} no existe")

        # Construction: same comparator and same order in AVL (with balancing)
        # and BST (without balancing). Remains in NORMAL mode (section 12).
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

    def _build_state_from_topology(self, data: dict, general: dict,
                                   from_version: bool = False) -> tuple[dict, list]:
        """HELPER: mode 2, load by topology. In addition to mode 1 checks,
        validates topological consistency. Aborts on the first error.
        Builds everything in new objects; self is not touched."""
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

        # 1. Mandatory fields.
        for i, raw in enumerate(nodes_raw):
            self._load_require(raw, self._TOPOLOGY_NODE_FIELDS, f"avl.nodes[{i}]")
        for i, raw in enumerate(archived_raw):
            self._load_require(raw, self._STORED_EVENT_FIELDS, f"archived[{i}]")
        for i, raw in enumerate(queue_raw):
            self._load_require(raw, self._REPORT_FIELDS, f"report_queue[{i}]")

        # 2. Ranges, dates, and stored data for each event.
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

        # 3. Uniqueness: an id cannot be repeated nor be simultaneously active,
        #    archived, or eliminated.
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

        # 4. Referenced stations must exist.
        for values in nodes + archived:
            for station_id in values["station_ids"]:
                if station_id not in stations:
                    raise self._load_error(values["where"], f"la estación {station_id!r} no existe")

        # 5. Valid references: root_id and each left_id/right_id point to
        #    an active node in the file, or are null.
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

        # 6. Each node in a single position: an id cannot be a child of two
        #    parents (nor twice of the same), and the root cannot be a child.
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

        # 7. No cycles or disconnected nodes: all reachable from the root.
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

        # 8. Create events (new objects) and verify that the stored
        #    priority matches the one computed using the file's zones
        #    (section 4).
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

        # 9. Build the EXACT topology from the file (without reinserting) with
        #    AVLTree.restore_topology and inspect it with AVLTree.audit: global
        #    order by K against all ancestors (equivalent to inorder traversal
        #    being sorted), uniqueness, parent pointers, stored vs real heights.
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

        # 10. Stored vs real balance factor (heights were already verified
        #     in step 9, so node.balance_factor is the real one).
        for values in nodes:
            real = avl_nodes[values["event_id"]].balance_factor
            if values["balance_factor"] != real:
                raise self._load_error(
                    values["where"], f"factor de balance guardado {values['balance_factor']}, real {real}"
                )

        # 11. Balance and mode. Sorted and balanced: loaded (in the file's
        #     mode, or current if omitted). Sorted but unbalanced:
        #     only with STRESS mode ENABLED, issuing a warning.
        file_mode = None
        if "mode" in data:
            try:
                file_mode = Mode(data["mode"])
            except (ValueError, TypeError):
                raise self._load_error("mode", f"debe ser 'Normal' o 'Stress' (llegó {data['mode']!r})") from None
        unbalanced = [node.event.event_id for node in tree.unbalanced_nodes()]
        if unbalanced:
            # A version saved in stress mode brings its own mode: restoring
            # it recovers it as is (section 13), even if the current
            # scenario is in Normal. An arbitrary file still requires
            # stress mode to be enabled (section 12).
            stress_allowed = (
                self.mode == Mode.STRESS
                or (from_version and file_mode == Mode.STRESS)
            )
            if not stress_allowed:
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

        # 12. Report queue, in its original order.
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

        # Final construction in a TEMPORARY Scenario to rebuild
        # associations with the usual deterministic policy.
        # BST is built by inserting in AVL preorder: this preserves
        # the same shape as the loaded topology.
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

        # 13. If the file stored references, they must match the
        #     reconstructed ones (derived values are verified upon loading).
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
        """HELPER: accumulated metrics from the file (integers >= 0). Missing
        rotation metrics are filled with 0 by AVLTree."""
        metrics = data.get("metrics", {})
        if not isinstance(metrics, dict):
            raise self._load_error("metrics", "debe ser un objeto")
        loaded = {}
        for name, value in metrics.items():
            if not isinstance(name, str):
                raise self._load_error("metrics", "los nombres de las métricas deben ser texto")
            loaded[name] = self._load_int(value, "metrics", name, 0)
        return loaded

    """==============================================="""
    """============== VERSIONS (SECTION 13) =========="""
    """==============================================="""

    def save_version(self, name: str) -> dict:
        """Save the current scenario state under a name (section 13).

        The state is exported in the same "topology" format that
        load_scenario consumes, so restoring is just feeding it back.

        Not undoable: it does not change the scenario, it only adds an
        entry to self.versions. Section 13 does not list "save version"
        among the undoable actions.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Version name must be a non-empty string")

        name = name.strip()
        if name in self.versions:
            raise ValueError(f"A version named '{name}' already exists")

        self.versions[name] = self.export_scenario(load_mode="topology")
        return {"saved": name, "total_versions": len(self.versions)}

    def list_versions(self) -> list[str]:
        """Return the names of all saved versions, alphabetically."""
        return sorted(self.versions.keys())

    def restore_version(self, name: str) -> dict:
        """Restore a saved version (section 13).

        Reuses load_scenario, so the version data is validated the same
        way as any file load and a LoadAction is pushed (section 13:
        "restoring a version is an action that can be undone"). The
        versions themselves are not touched.
        """
        if name not in self.versions:
            raise KeyError(f"Version '{name}' was not found")

        result = self.load_scenario(self.versions[name], from_version=True)
        result["restored_version"] = name
        return result

    def delete_version(self, name: str) -> None:
        """Delete a saved version by name. Not undoable: section 13 does
        not list it among the undoable actions."""
        if name not in self.versions:
            raise KeyError(f"Version '{name}' was not found")
        del self.versions[name]

    def version_summaries(self) -> list[dict]:
        """Names of the saved versions with a few fields to tell them apart
        in the selection list (section 13: "restore by selection").
        Alphabetical order, same as list_versions."""
        summaries = []
        for name in self.list_versions():
            data = self.versions[name]
            summaries.append({
                "name": name,
                "simulation_clock": data.get("simulation_clock"),
                "mode": data.get("mode"),
                "active_events": len(data.get("avl", {}).get("nodes", [])),
                "archived_events": len(data.get("archived", [])),
                "queued_reports": len(data.get("report_queue", [])),
            })
        return summaries

    def export_versions(self) -> dict:
        """Shallow copy of all saved versions, for the router to write
        to disk. Shallow is enough: the router only serializes it."""
        return dict(self.versions)

    def import_versions(self, data: dict) -> None:
        """Load versions from disk (called by the router at startup)."""
        if not isinstance(data, dict):
            raise ValueError("Versions data must be a dict")
        self.versions = dict(data)
    
    """==============================================="""
    """============TREE STATE (VISTAS)================"""
    """==============================================="""

    # Read-only tree snapshots for the UI (AVL view, comparative view
    # with BST, sections 11 and 15). Returns dictionaries with simple
    # data (numbers, strings, lists, None), ready for JSON.
    #
    # FLAT topology: root_id + a list of nodes where each node references
    # its neighbors by id (left_id, right_id, parent_id). Same design as
    # the topology load schema (section 12), avoiding nested nodes.
    #
    # Each node carries only what is needed to render it; full event
    # details (stations, revision, associations) are requested via get_event(id).
    # Tree audit does NOT go here: it is a separate operation (avl_tree.audit()).

    def get_avl_state(self) -> dict:
        """Current state of the active AVL. Cost O(n)."""
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
            "counters": {k: self.metrics.get(k, 0) for k in COUNTER_KEYS},
        }

    def _collect_avl_rows(self, node, parent_id, depth, rows):
        """HELPER: recursive preorder building a row per AVL node.
        Depth is passed down as a parameter (O(1) per node), rather than
        calling depth_of() on each node (O(depth) each time).
        Height and balance factor are READ from the node: AVL stores them."""
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
            "search_cost": depth + 1,  # visited nodes when searching by key (section 9)
            "costly_access": node.event.priority == 3 and depth > self.L,
        })
        rows.append(row)
        self._collect_avl_rows(node.left_son, row["event_id"], depth + 1, rows)
        self._collect_avl_rows(node.right_son, row["event_id"], depth + 1, rows)

    def get_bst_state(self) -> dict:
        """Current state of the comparison BST, with the same shape as
        get_avl_state to render and compare them identically. BST does
        not store height or parent: calculated during traversal. Cost O(n)."""
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
        """HELPER: adds the row when DESCENDING (so the list is in preorder)
        and populates height and factor when RETURNING from children (like
        postorder). Returns subtree height (empty = -1)."""
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
        row["balance_factor"] = left_h - right_h  # informative: BST never rotates
        return row["height"]

    @staticmethod
    def _event_row(event) -> dict:
        """HELPER: event data needed to render its node."""
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
        """HELPER: tree traversals as lists of ids (not of Event)."""
        return {
            "inorder": [e.event_id for e in tree.inorder()],
            "preorder": [e.event_id for e in tree.preorder()],
            "postorder": [e.event_id for e in tree.postorder()],
            "level_order": [e.event_id for e in tree.level_order()],
        }
