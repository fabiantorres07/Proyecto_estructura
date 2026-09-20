class Station:

    def __init__(self, station_id, x, y):
        self.station_id = station_id
        self.x = x
        self.y = y

    def __eq__(self, other):
        if not isinstance(other, Station):
            return NotImplemented
        return self.station_id == other.station_id

    def __hash__(self):
        return hash(self.station_id)
