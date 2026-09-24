from app.domain.event import Event

class AVLNode:

    def __init__(self, event : Event, left_son = None, right_son = None, height = 0, parent = None):

        self.event = event
        self.left_son = left_son
        self.right_son = right_son
        self.height = height
        self.parent = parent

    @property
    def balance_factor(self):
        left_height = self.left_son.height if self.left_son is not None else -1
        right_height = self.right_son.height if self.right_son is not None else -1
        return left_height - right_height

