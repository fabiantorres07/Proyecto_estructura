class BSTNode:
    """Nodo del árbol BST de comparación (sin balanceo).

    Guarda una referencia al MISMO objeto Event que usa el AVL (no una
    copia): así los dos árboles comparten la identidad del evento, como
    exige el enunciado, y una corrección aplicada al Event se ve igual
    desde ambos árboles.

    No guarda `parent` ni `height`:
    - `parent` no hace falta porque en un BST sin balanceo ninguna
      operación necesita "subir" después de terminar: insertar y
      eliminar son un único recorrido de bajada, y el padre se lleva en
      una variable local durante ese recorrido (ver BSTTree.delete).
    - `height` no hace falta porque ningún algoritmo de este árbol la
      consulta a mitad de una operación (no hay factor de balance ni
      rotaciones). La altura se calcula bajo demanda en BSTTree.height().
    """

    def __init__(self, event, left_son=None, right_son=None):
        self.event = event          # Event almacenado (misma instancia que en el AVL).
        self.left_son = left_son    # Subárbol izquierdo: claves menores (BSTNode o None).
        self.right_son = right_son  # Subárbol derecho: claves mayores (BSTNode o None).
