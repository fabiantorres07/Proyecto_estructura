class Zone:

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

    def contains(self, x, y):
        if x >= self.x_min and x <= self.x_max:
            if y >= self.y_min and y <= self.y_max:
                return True
            else:
                return False
        return False