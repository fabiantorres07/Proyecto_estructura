from app.domain.station import Station
class Report:

    def __init__(self, event_id, revision_num, station : Station, magnitude, depth, x, y, occurred_at):

        self.event_id = event_id
        self.revision_num = revision_num
        self.station = station
        self.magnitude = magnitude
        self.depth = depth
        self.x = x
        self.y = y
        self.occurred_at = occurred_at
        