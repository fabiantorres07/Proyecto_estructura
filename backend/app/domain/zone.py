class Zone:
    """A rectangular area of the map, used to decide if an epicenter is in a
    populated area.

    A zone is a rectangle defined by its bounds (x_min, x_max, y_min, y_max)
    plus two pieces of metadata: a name and a populated flag. It is a
    pure geometric value object. It does not decide which zone an epicenter
    belongs to, nor what to do when the epicenter sits on the border shared
    by two zones. That decision belongs to Scenario, not here.

    Why Zone is so small
    --------------------
    Zones are fixed during a scenario (section 1: "the geometry remains
    fixed during the scenario"). Once there are events, add/update/delete
    are blocked by Scenario, so Zone itself does not need any state-machine
    logic. It just stores the rectangle and answers point-in-rectangle.

    Invariants (enforced in __init__)
    ---------------------------------
    - name must be a non-empty string.
    - All four bounds must be in [0, 1000].
    - All four bounds must have at most one decimal digit.
    - x_min <= x_max and y_min <= y_max.

    Attributes
    ----------
    name : str
        Human-readable name of the zone. Must be unique among the zones of
        a scenario (Scenario enforces this, not Zone).
    x_min, x_max : float
        Horizontal bounds of the rectangle, inclusive.
    y_min, y_max : float
        Vertical bounds of the rectangle, inclusive.
    is_populated : bool
        Whether the zone counts as populated. Used by Scenario to compute
        `event.is_in_populated_zone` (section 3).
    """

    def __init__(self, name, x_min, x_max, y_min, y_max, is_populated):
        self.name = name
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.is_populated = is_populated

        if not name:
            raise ValueError("Zone name cannot be empty")

        if (x_min < 0 or x_min > 1000 or y_min < 0 or y_min > 1000
                or x_max < 0 or x_max > 1000 or y_max < 0 or y_max > 1000):
            raise ValueError("The zone's numbers must be between 0 and 1000")

        if any(coord * 10 != int(coord * 10) for coord in [x_min, y_min, x_max, y_max]):
            raise ValueError("The coordinates can't contain more than one decimal value")

        if x_min > x_max or y_min > y_max:
            raise ValueError("The min values of x and y can't exceed their max counterparts")

    def contains(self, x, y):
        """Return True if (x, y) is inside the rectangle or on its border.

        Both ends are inclusive (>= and <=), because the statement says
        an epicenter belongs to a zone when it is inside it OR on its
        border. Scenario uses this to test the epicenter against every
        zone; if the point sits on the border shared by two zones, it
        will match both, and Scenario decides which one wins (populated
        if any of them is populated).
        """
        if x >= self.x_min and x <= self.x_max:
            if y >= self.y_min and y <= self.y_max:
                return True
            else:
                return False
        return False