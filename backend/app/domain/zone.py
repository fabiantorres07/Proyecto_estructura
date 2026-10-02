class Zone:
    """Es un rectángulo del mapa. Guarda su nombre, sus límites (x mínima y máxima, y mínima y máxima) y si es poblada o no.

    contains(x, y): responde si un punto está dentro de la zona. Los bordes cuentan como dentro, como pide el enunciado.
    Al crearse revisa que el nombre no esté vacío y que los números estén entre 0 y 1000.
    
    Decidir a qué zona pertenece un evento, y qué pasa en el borde compartido entre dos zonas, lo hace Scenario, no Zone."""
    def __init__(self,name,  x_min, x_max, y_min, y_max, is_populated):

        self.name = name
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.is_populated =  is_populated

        if not name:
            raise ValueError("Zone name cannot be empty")
        
        if (x_min < 0 or x_min > 1000 or y_min < 0 or y_min > 1000 or x_max < 0 or x_max > 1000 or y_max<0 or y_max>1000):
            raise ValueError("The zone's numbers must be between 0 and 1000")
        
        if any(coord * 10 != int(coord * 10) for coord in [x_min, y_min, x_max, y_max]):
            raise ValueError("The coordinates can't contain more than one decimal value")
        
        if x_min > x_max or y_min > y_max:
            raise ValueError("The min values of x and y can't exceed their max counterparts")

    def contains(self, x, y):
        if x >= self.x_min and x <= self.x_max:
            if y >= self.y_min and y <= self.y_max:
                return True
            else:
                return False
        return False