from app.domain.station import Station

"""Solo transporta datos, no tiene lógica.

Es una clase aparte de Event porque un reporte no es un evento. Es un aviso que todavía hay que evaluar: 
puede crear un evento, corregirlo, confirmarlo, ser antiguo o generar un conflicto. Esa decisión la toma Scenario,
 comparando el reporte con el evento vigente. Por eso el reporte no trae la zona poblada: Scenario la calcula al procesarlo.
Los reportes esperan en la cola hasta que Scenario los procesa."""
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
        