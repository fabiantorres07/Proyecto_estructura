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
    GlobalRecoveryAction, LoadAction, ReactivationAction
)
from app.structures.avl_tree import AVLTree, ROTATION_METRIC_KEYS, AVLTopologySnapshot
from app.structures.avl_node import AVLNode
from app.structures.bst_node import BSTNode
from app.structures.bst_tree import BSTTree

"""==========================================================================================
INFRASTRUCTURE: Methods that are important for the project but are not specific to any class
============================================================================================="""

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

        W and R together. If changes = {"W": 24, "R": 50} and both change:
        W is applied first, references are recalculated, action is pushed
        with old_refs (before W). Then R, references are recalculated again,
        action is pushed with old_refs (which already reflects the W change).
        When undoing, R is reverted first (going back to old R and restoring
        the references from after W), then W.
        It works, even though it recalculates twice.
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

        # 3. Apply only those that truly change.
        changed = {}

        for name, new_value in changes.items():
            old_value = getattr(self, name)
            if old_value == new_value:
                continue

            # Snapshot of references before touching the parameter, only if
            # applicable.
            old_refs = None
            if name in ("W", "R"):
                old_refs = {
                    event.event_id: event.reference_id
                    for event in self._all_active_and_archived_events()
                }

            # Apply the change.
            setattr(self, name, new_value)

            # Recalculate all references if W or R changed.
            if name in ("W", "R"):
                for event in self._all_active_and_archived_events():
                    self._recalculate_reference(event)

            # Push the action with the old value and (if applicable) the
            # previous snapshot.
            self.undo_stack.push(
                ParameterChangeAction(name, old_value, old_refs)
            )
            changed[name] = new_value

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

        self.zones.append(zone)
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
        return updated_zone

    def delete_zone(self, zone_name: str) -> None:
        """Delete a zone. Only allowed while the scenario has no events
        (see _check_zones_and_stations_are_fixed)."""
        self._check_zones_and_stations_are_fixed()

        zone = self.get_zone(zone_name)
        self.zones.remove(zone)


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

        self.stations[station.station_id] = station
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

        updated_station = Station(**updated_values)
        if updated_station.station_id != station_id:
            del self.stations[station_id]
        self.stations[updated_station.station_id] = updated_station
        return updated_station

    def delete_station(self, station_id: str) -> None:
        """Delete a station. Only allowed while the scenario has no
        events (see _check_zones_and_stations_are_fixed)."""
        self._check_zones_and_stations_are_fixed()

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

        Team decision (documented): this operation is NOT recorded on the
        undo stack.

        Why: section 13 lists the actions that must be undoable (create,
        correct, delete, mass archive, parameter change, clock advance,
        attention change, load, global recovery and each queue step).
        "Clear the queue" is NOT in that list. The statement also says
        the queue is part of the recoverable state, but only in the
        context of saving/restoring versions, not as a standalone
        undoable action.

        So we follow the explicit list in section 13. The state changes
        (the queue is emptied), but there is no way back via undo(); the
        user would have to use a saved version if they want the reports
        back.

        If the queue is already empty, nothing happens (returns 0)."""
        return self.report_queue.clear()


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
                revision=report.revision_num,    # the first revision can be > 1
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
                # Confirmation or conflict on an archived event: does not
                # reactivate it.
                case = "archived_not_reactivated"
            else:
                case = "old"

        # Case: active id.
        else:
            event = self.event_index[event_id].event

            if report.revision_num > event.revision:
                # Greater revision → correct.
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
        ))

        # 6. Return info about the step, so the frontend can show what
        # happened.
        return {
            "case": case,
            "event_id": event_id,
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

        is_populated = self.epicenter_in_populated_zone(x, y)

        # Here the new event is born (we call it B).
        event = Event(
            event_id=event_id, magnitude=magnitude, depth=depth,
            x=x, y=y, occurred_at=occurred_at, revision=revision,
            stations=stations, is_in_populated_zone=is_populated,
        )

        balance = (self.mode == Mode.NORMAL)

        node = self.avl_tree.insert(event, balance=balance)
        self.bst_tree.insert(event)
        self.event_index[event_id] = node

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
        self.undo_stack.push(CreationAction(event_id, old_references))

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
        # Archived
        if event_id in self.archived_history:
            return {
                "status": "archived",
                "event_id": event_id,
                "event": None,
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
                is_in_populated_zone=is_in_populated_zone,
            )

            # 5-6. If the key changed (priority went up/down, or M changed), it
            # must be removed from the trees with the old key and reinserted with
            # the new one. event_index is updated with the NEW node.
            balance = (self.mode == Mode.NORMAL)

            if old_key != new_key:
                self.avl_tree.delete(old_key, balance=balance)
                self.bst_tree.delete(old_key)
                new_node = self.avl_tree.insert(event, balance=balance)
                self.bst_tree.insert(event)
                self.event_index[event_id] = new_node

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
            self.avl_tree.delete(key, balance=balance)
            self.bst_tree.delete(key)
            del self.event_index[event_id]

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
            self.undo_stack.push(DeletionAction(event, old_references))

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
        node = self.avl_tree.insert(event, balance=balance)
        self.bst_tree.insert(event)
        self.event_index[event_id] = node

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
            }

        winner = matches[0]
        node = winner["root"]

        # 2. Freeze ids BEFORE touching the tree.
        event_ids = self.avl_tree.subtree_event_ids(node)

        # 3. Detach. In normal mode it rotates; in stress mode, it does not.
        balance = (self.mode == Mode.NORMAL)
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

        # 6. Push the action (a single one for the whole archive).
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
        else:
            # Unknown action: push it back so it is not lost.
            self.undo_stack.push(action)
            raise NotImplementedError(
                f"undo() no sabe deshacer {type(action).__name__}"
            )


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
            self.bst_tree.insert(node.event)
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

    def event_associations(self, event_id: int) -> dict:
        """Devuelve las asociaciones completas de un evento: candidatos,
        referencia elegida, y quiénes lo usan como referencia.

        Sección 11, cuarta consulta: "Candidatos y referencia elegida para
        un evento, así como los eventos que lo utilizan como referencia. Se
        identifica si cada resultado está activo o archivado."

        Se devuelven TRES bloques, no dos, porque la relación es
        bidireccional: no basta con saber a quién apunta este evento
        (referencia) ni quiénes podrían ser su referencia (candidatos).
        También hay que saber quiénes apuntan a él. Sin esa tercera parte,
        la consulta solo daría la mitad de la red de asociaciones: las
        salientes pero no las entrantes. Los candidatos y la referencia
        salen de _build_associations (que ya usa get_event). El tercer
        bloque sale del índice inverso referenced_by, que existe justo
        para responder "quién me tiene como referencia" sin recorrer todos
        los eventos.

        Hay dos métodos (get_event y event_associations) porque sirven a
        dos propósitos distintos:
        - get_event devuelve TODO sobre un evento: datos, revisión,
        estaciones, prioridad, estado, profundidad, altura, factor de
        balance, y las asociaciones como un bloque más. Es la vista
        completa de un evento.
        - event_associations se enfoca SOLO en la red de asociaciones, y
        agrega el bloque de "quién me usa" que get_event no trae. Es la
        vista específica para cuando el frontend quiere mostrar la red
        de réplicas de un evento sin cargar toda su ficha.

        Si el id no existe o está eliminado, lanza ValueError: los
        eliminados no forman parte del sistema (solo queda su id en
        eliminated_IDs), así que no tiene sentido pedir sus asociaciones.

        Devuelve un dict con:
            {
                "reference": {"event": Event, "status": "active"|"archived"} o None,
                "candidates": [{"event": Event, "status": ...}, ...],
                "used_as_reference_by": [{"event": Event, "status": ...}, ...],
            }
        `candidates` no incluye la referencia (ya viene en su propio
        bloque). `used_as_reference_by` puede estar vacío si nadie lo usa
        como referencia.

        No reporta nodos examinados: las otras consultas de la sección 11
        sí lo hacen porque navegan el AVL directamente; aquí solo se lee
        un dict (referenced_by) y se delega el cálculo de candidatos a
        _build_associations, que ya es una consulta en sí misma.
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
    def count_events_by_priority(self) -> dict:
        """Cuenta eventos activos y archivados por prioridad.

        Sección 14 (Auditoría e indicadores): "La interfaz mantendrá visibles
        o accesibles los siguientes indicadores: ... Eventos por prioridad,
        pendientes de atención y eventos marcados con acceso costoso."

        Se cuentan activos Y archivados (los dos forman parte del sistema y
        ambos pueden ser referencia de otros eventos según la sección 7). Los
        eliminados NO se cuentan: no están en el sistema, solo queda su id.

        Se calcula AL VUELO, no acumulado: la prioridad de un evento puede
        cambiar (corrección que suba la magnitud, cambio de zona poblada), y
        mantener un contador acumulado obligaría a ajustarlo en cada una de
        esas operaciones. Es más simple y consistente recalcularlo cada vez.

        Devuelve:
            {"P1": n, "P2": n, "P3": n}

        Costo: O(n).
        """
        counts = {"P1": 0, "P2": 0, "P3": 0}
        for event in self._all_active_and_archived_events():
            counts[f"P{event.priority}"] += 1
        return counts

    def compare_avl_bst(self) -> dict:
        """Compara AVL vs BST: altura, hojas y comparaciones al buscar las
        mismas claves. Sección 11, último bloque: "Se compararán AVL y BST
        mediante altura, hojas y comparaciones al buscar las mismas claves."

        Para cada evento activo se busca su clave en ambos árboles. search()
        ya devuelve (nodo, nodos_visitados), así que solo se suman.

        LIMITACIÓN: los dos árboles están sincronizados en el estado actual,
        pero no con el mismo orden de inserción histórico. Si el escenario
        se armó en orden ascendente, el BST está degenerado y la diferencia
        es enorme; si el orden fue aleatorio, la diferencia es más sutil.
        El caso "todo en orden ascendente" se prueba con datos específicos,
        no con esta consulta.

        Devuelve dos bloques comparables (avl y bst), cada uno con size,
        height, leaves, total_comparisons, max_single_search y
        avg_comparisons, más n_searches.
        """
        # Claves de todos los eventos activos, en orden ascendente de K.
        keys = [event.key for event in self.avl_tree.inorder()]

        # Sumar nodos visitados al buscar cada clave en cada árbol.
        # max_* guarda la peor búsqueda individual (profundidad máxima + 1).
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
