from app.domain.station import Station
class Report:
    """A report is a raw notice sent by a station about a possible earthquake.

    This is a DATA-ONLY container. It has no logic of its own: it does not
    decide whether it creates, corrects, confirms, or conflicts with an
    event. That decision belongs to Scenario, which compares the report
    against the current state when the report is processed.

    Why this is a separate class from Event
    ---------------------------------------
    A report is not an event. An event is a confirmed earthquake stored in
    the AVL/BST and in event_index. A report is an incoming claim that may
    or may not match an existing event. Keeping them separate prevents
    unvalidated data from leaking into the confirmed structures.

    Why the report does NOT carry `is_in_populated_zone`
    ----------------------------------------------------
    Because the populated zone depends on the scenario's zones at the
    moment of processing, not at the moment the report was created. The
    schema validates ranges; Scenario computes the populated flag when it
    decides what to do with the report.

    Lifecycle
    ---------
    1. Created by the router from a validated payload (schema ReportCreate).
    2. Enqueued in Scenario.report_queue (FIFO).
    3. Dequeued by Scenario.process_next_report(), which decides its case
       against the current event (create / correct / confirm / conflict /
       old / eliminated) and pushes the corresponding action.

    Attributes
    ----------
    event_id : int
        Identifier of the earthquake the report talks about. Not unique per
        report: several reports can share the same event_id (confirmations,
        corrections). The pair (event_id, revision_num) identifies a report.
    revision_num : int
        Revision the station claims. Compared against the current event's
        revision to decide the case (greater = correction, equal = confirm
        or conflict, lower = old).
    station : Station
        Station that emitted the report. The station's identity matters for
        validation (it must be registered in Scenario.stations) and for
        accepting it later as a confirming station of the event.
    magnitude : float
    depth : float
    x : float
    y : float
        Physical data of the claimed epicenter and hypocenter.
    occurred_at : datetime
        When the earthquake occurred, per the station. Must include a
        timezone and cannot be later than the simulation clock.
    """

    def __init__(self, event_id, revision_num, station: Station, magnitude, depth, x, y, occurred_at):
        self.event_id = event_id
        self.revision_num = revision_num
        self.station = station
        self.magnitude = magnitude
        self.depth = depth
        self.x = x
        self.y = y
        self.occurred_at = occurred_at
        