class Zone:

    def __init__(self, x_min, x_max, y_min, y_max, is_populated):
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.is_populated =  is_populated

    def contains(self, x, y):
        if x >= self.x_min and x <= self.x_max:
            if y >= self.y_min and y <= self.y_max:
                return True
            else:
                return False
        return False