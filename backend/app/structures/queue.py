class Queue:
    def __init__(self):
        self._items = []

    def enqueue(self, item):
        self._items.append(item)

    def dequeue(self):
        return self._items.pop(0)

    def peek(self):
        return self._items[0]

    def is_empty(self):
        return len(self._items) == 0

    def insert_at(self, position, item):
        self._items.insert(position, item)

    def items(self):
        return list(self._items)