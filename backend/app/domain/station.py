"""Es la ficha de una estación que reporta sismos: su número (id) y su ubicación (x, y). No hace nada más que guardar eso.

Lo único especial son __eq__ y __hash__. Con ellos, dos estaciones con el mismo id cuentan como la misma."""

class Station:

    def __init__(self, station_id, x, y):
        self.station_id = station_id
        self.x = x
        self.y = y

        if station_id is None:
            raise ValueError("The station must contain an id to identify it")

        if x<0 or x>1000 or y<0 or y>1000:
            raise ValueError("The station's coordinates must be between 0 and 1000")
        
        if any(coord * 10 != int(coord * 10) for coord in [x, y]):
            raise ValueError("The coordinates can't contain more than one decimal value")


    def __eq__(self, other):
        if not isinstance(other, Station):
            return NotImplemented
        return self.station_id == other.station_id

    def __hash__(self):
        return hash(self.station_id)
