from app.domain.event import Event


class AVLNode:
    """Nodo del árbol AVL de eventos activos.

    - event: el Event almacenado. Es la MISMA instancia que usa el resto
      del sistema (índice por id, BST de comparación, histórico): las
      rotaciones mueven nodos, nunca copian ni modifican los datos del
      evento.
    - left_son / right_son: hijos (AVLNode o None).
    - parent: padre del nodo (None en la raíz). Permite calcular la
      profundidad subiendo hasta la raíz y saber de quién cuelga un nodo
      (por ejemplo, para el archivo masivo) sin volver a buscarlo.
    - height: altura del subárbol que empieza en este nodo. Convención
      del enunciado (sección 14): hoja = 0, subárbol vacío = -1.
    """

    def __init__(self, event: Event, left_son=None, right_son=None, height=0, parent=None):
        self.event = event
        self.left_son = left_son
        self.right_son = right_son
        self.height = height
        self.parent = parent

    @property
    def balance_factor(self):
        """Altura izquierda menos altura derecha. Un hijo que no existe
        cuenta con altura -1. Se calcula siempre a partir de las alturas
        guardadas en los hijos, así que nunca queda desactualizado respecto
        a ellas."""
        left_height = self.left_son.height if self.left_son is not None else -1
        right_height = self.right_son.height if self.right_son is not None else -1
        return left_height - right_height
