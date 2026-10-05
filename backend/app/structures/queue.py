class Queue:

    """Es una fila. El primero que llega es el primero que sale. Aquí esperan los reportes hasta que Scenario los procesa.

    enqueue: mete un reporte al final.
    dequeue: saca el primero.
    peek: mira el primero sin sacarlo.
    is_empty: dice si está vacía.
    insert_at: mete un reporte en una posición exacta. Se usa al deshacer, para devolverlo a su lugar original.
    items: da una copia de la fila para mostrar el orden, sin dejar que nadie desordene la original."""
    def __init__(self):
        self._items = []

    def enqueue(self, item):
        self._items.append(item)

    def dequeue(self):
        return self._items.pop(0)

    def peek(self):
        return self._items[0]
    
    def replace_first(self, item):
        if self.is_empty():
            raise IndexError("Cannot replace the front of an empty queue")
        self._items[0] = item

    def is_empty(self):
        return len(self._items) == 0

    def insert_at(self, position, item):
        self._items.insert(position, item)

    def remove(self, item):
        """Remove the exact queued object, preserving all other order."""
        for index, queued_item in enumerate(self._items):
            if queued_item is item:
                return self._items.pop(index)
        raise ValueError("Item not found in queue")

    def items(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)

    def clear(self):
        """Vacía la cola y devuelve cuántos elementos tenía. O(1)."""
        removed = len(self._items)
        self._items = []
        return removed
