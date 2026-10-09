class Station:
    """A station is the record of a sensor that reports earthquakes.

    It stores only two facts: its identifier (station_id) and its fixed
    position on the plane (x, y). No behaviour, no metrics, no state
    transitions.

    Why __eq__ and __hash__ are overridden
    ---------------------------------------
    A station's identity is its station_id, not its coordinates. Two
    Station objects created from two different payloads with the same id
    must be treated as the SAME station. This matters because:

    - Reports carry a Station reconstructed from the payload, never the
      exact instance stored in Scenario.stations. When a report is
      accepted, the event stores the report's station object inside its
      `stations` set. Later checks such as `report.station not in
      event.stations` rely on equality by id, not on object identity.
    - Events keep their `stations` as a set, and sets use __hash__ and
      __eq__ to detect duplicates. Without these overrides, two equal
      station_ids would count as two different members.

    Invariants (enforced in __init__)
    ---------------------------------
    - station_id must not be None.
    - x and y must be in [0, 1000].
    - x and y must have at most one decimal digit.

    Attributes
    ----------
    station_id : str
        Unique identifier of the station. This is what makes two stations
        the same (see __eq__ / __hash__).
    x : float
        Horizontal coordinate of the station, in [0, 1000], one decimal.
    y : float
        Vertical coordinate of the station, in [0, 1000], one decimal.
    """

    def __init__(self, station_id: str, x: float, y: float):
        self.station_id = station_id
        self.x = x
        self.y = y

        if station_id is None:
            raise ValueError("The station must contain an id to identify it")

        if x < 0 or x > 1000 or y < 0 or y > 1000:
            raise ValueError("The station's coordinates must be between 0 and 1000")

        if any(coord * 10 != int(coord * 10) for coord in [x, y]):
            raise ValueError("The coordinates can't contain more than one decimal value")

    def __eq__(self, other):
        if not isinstance(other, Station):
            return NotImplemented
        return self.station_id == other.station_id

    def __hash__(self):
        return hash(self.station_id)