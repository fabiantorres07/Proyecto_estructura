from enum import Enum
from app.domain.station import Station

class Event:

    """EVENT CLASS"""
    """Represents an earthquake: its physical data and nothing more.
    The data: id, magnitude, depth, epicenter (x, y), date and time.
    The current revision and reporting stations.
    Whether it is in a populated zone. Event does not know about zones, so whoever creates it (Scenario) tells it the value.
    Attention status. Always starts as pending."""

    def __init__(self,event_id, magnitude, depth, x, y, occurred_at,  revision, stations : set["Station"], is_in_populated_zone):

        self.event_id = event_id
        self.magnitude = magnitude
        self.depth = depth

        # These data represent the epicenter
        self.x = x
        self.y = y

        self.occurred_at = occurred_at

        # Current revision
        self.revision = revision

        # Stations with accepted reports
        self.stations = stations

        self.attention_status = AttentionStatus.PENDING

        self.is_in_populated_zone = is_in_populated_zone

        # NEEDED TO CALCULATE ASSOCIATIONS IN SCENARIO (system state attribute, only stored here)
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
        """Applies a correction to the event.

        - Changes incoming fields (fields left as None are not touched).
        - `occurred_at` is NOT in the key K = (P, M, I), but it DOES affect
        associations (section 7): W hours, temporal order of
        references. A date change can change which events are
        candidates for each other without changing the key.
        - `revision`: if provided, that value is used (correction from a
        report, section 6: "substitute the current data" with the
        report's revision). If not provided, it is incremented by 1
        (manual correction, section 6: "r + 1").
        - Returns (old_key, new_key) so Scenario knows if trees must be
        reorganized.
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
    
    def mark_as_reviewed(self):
        self.attention_status = AttentionStatus.REVIEWED

# The following enum is used to define the attention status of the event
class AttentionStatus(Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
