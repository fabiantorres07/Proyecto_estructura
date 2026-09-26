from app.structures.bst_node import BSTNode


class BSTTree:
    """Árbol binario de búsqueda SIN balanceo, usado como árbol de
    comparación frente al AVL (secciones 11 y 12 del enunciado).

    Decisión de diseño (acordada con el equipo): este árbol se mantiene
    VIVO y sincronizado con el AVL durante toda la simulación. Cada vez que
    Scenario inserta un evento en el AVL, también lo inserta aquí; cada vez
    que lo retira del AVL (eliminación, corrección que cambia la clave,
    archivo masivo), también lo retira aquí. Así ambos árboles contienen
    siempre el mismo conjunto de eventos activos y la comparación de
    altura, hojas y comparaciones de búsqueda vale en cualquier momento.

    La única diferencia con el AVL es que aquí NUNCA se rota: la forma del
    árbol depende solo del orden de las operaciones. Eso es lo que se mide.

    Comparación de claves: `Event.key` es la tupla K = (P, M, I). Python
    compara tuplas de forma lexicográfica (primero P, luego M, luego I),
    que es exactamente la regla de la sección 5.

    Implementación recursiva (pedida por el profesor): cada función
    recursiva recibe la raíz de un subárbol y, cuando modifica el árbol,
    devuelve la raíz (posiblemente nueva) de ese subárbol para que quien la
    llamó la vuelva a enganchar. Límite conocido: si el árbol degenera en
    una "lista" (inserciones en orden ascendente), la profundidad de la
    recursión es igual a la cantidad de nodos; Python permite unos 1000
    niveles, y el proyecto no espera más de ~100 eventos, así que no hay
    riesgo. Conviene mencionarlo en el análisis de costos del manual.
    """

    def __init__(self):
        self.root = None   # Raíz (BSTNode) o None si el árbol está vacío.
        self._size = 0     # Cantidad de nodos, mantenida en insert/delete.

    # ------------------------------------------------------------------
    # Consultas básicas
    # ------------------------------------------------------------------

    def __len__(self):
        """Cantidad de eventos en el árbol. O(1)."""
        return self._size

    def is_empty(self):
        return self.root is None

    def clear(self):
        """Vacía el árbol. Se usa cuando se reemplaza el escenario completo
        (carga de archivo, restauración de versión): el BST no forma parte
        del estado exportado (la sección 12 solo pide la topología del AVL),
        así que en esos casos se reconstruye con clear() + insert()."""
        self.root = None
        self._size = 0

    # ------------------------------------------------------------------
    # Inserción
    # ------------------------------------------------------------------

    def insert(self, event):
        """Inserta `event` según su clave actual `event.key`: clave menor a
        la izquierda, mayor a la derecha, hasta llegar a un hueco (None).
        No hay rebalanceo.

        Lanza ValueError si ya existe un nodo con la misma clave (solo puede
        pasar si se inserta dos veces el mismo evento, porque el id forma
        parte de K); en ese caso el árbol no se modifica.

        Costo: O(h), con h la altura actual (O(n) en el peor caso).
        """
        self.root = self._insert(self.root, event)
        self._size += 1

    def _insert(self, node, event):
        """Inserta en el subárbol `node` y devuelve la raíz del subárbol."""
        if node is None:
            return BSTNode(event)   # hueco encontrado: el nuevo nodo es una hoja

        key = event.key
        node_key = node.event.key
        if key < node_key:
            node.left_son = self._insert(node.left_son, event)
        elif key > node_key:
            node.right_son = self._insert(node.right_son, event)
        else:
            raise ValueError(f"Ya existe un evento con la clave {key} en el BST")
        return node

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------

    def search(self, key):
        """Busca el nodo con clave exactamente `key` = (P, M, I).
        Devuelve (nodo_o_None, nodos_visitados).

        `nodos_visitados` es el dato de la sección 11 para comparar el costo
        de búsqueda entre AVL y BST: cada nodo contra el que se compara la
        clave cuenta como una visita. Si el evento existe, es igual a su
        profundidad + 1. Costo: O(h).
        """
        return self._search(self.root, key, 0)

    def _search(self, node, key, visited):
        if node is None:
            return None, visited
        visited += 1
        node_key = node.event.key
        if key == node_key:
            return node, visited
        if key < node_key:
            return self._search(node.left_son, key, visited)
        return self._search(node.right_son, key, visited)

    # ------------------------------------------------------------------
    # Eliminación
    # ------------------------------------------------------------------

    def delete(self, key):
        """Retira el evento ubicado con la clave `key` y lo devuelve.
        Lanza KeyError si no está (y el árbol no se modifica).

        IMPORTANTE: `key` es la clave con la que el evento fue INSERTADO.
        En una corrección, el Event se modifica en el mismo objeto y su
        `event.key` ya devuelve la clave nueva, pero el nodo sigue ubicado
        según la vieja. Por eso se navega con `key` y el nodo buscado se
        reconoce por su identificador (key[2]), que nunca cambia.
        Flujo esperado en Scenario para una corrección:
            old_key, new_key = event.apply_correction(...)
            bst_tree.delete(old_key)
            bst_tree.insert(event)      # se reubica con la clave nueva

        Costo: O(h).
        """
        new_root, removed = self._delete(self.root, key)
        if removed is None:
            raise KeyError(f"No existe en el BST un evento con la clave {key}")
        self.root = new_root
        self._size -= 1
        return removed.event

    def _delete(self, node, key):
        """Elimina en el subárbol `node`. Devuelve una tupla
        (nueva_raíz_del_subárbol, nodo_retirado_o_None).

        Los tres casos clásicos:
        1. Hoja: el subárbol queda vacío (se devuelve None).
        2. Un solo hijo: ese hijo ocupa el lugar del nodo.
        3. Dos hijos: el sucesor inorden (mínimo del subárbol derecho) ocupa
           el lugar del nodo. Se mueve el NODO sucesor completo en vez de
           copiar su evento, para que cada evento siga en su propio nodo.
        """
        if node is None:
            return None, None   # no se encontró

        if node.event.event_id != key[2]:
            # Todavía no es el nodo buscado: bajar por el lado que indica la clave.
            if key < node.event.key:
                node.left_son, removed = self._delete(node.left_son, key)
            else:
                node.right_son, removed = self._delete(node.right_son, key)
            return node, removed

        # Se encontró el nodo a retirar.
        if node.left_son is None:          # casos 1 y 2 (sin hijo izquierdo)
            replacement = node.right_son
        elif node.right_son is None:       # caso 2 (solo hijo izquierdo)
            replacement = node.left_son
        else:                              # caso 3: dos hijos
            new_right, successor = self._detach_minimum(node.right_son)
            successor.left_son = node.left_son
            successor.right_son = new_right
            replacement = successor

        # Soltar los enlaces del nodo retirado.
        node.left_son = None
        node.right_son = None
        return replacement, node

    def _detach_minimum(self, node):
        """Separa el nodo mínimo (el de más a la izquierda) del subárbol
        `node`. Devuelve (nueva_raíz_del_subárbol, nodo_mínimo).
        El mínimo nunca tiene hijo izquierdo, así que su hijo derecho sube
        a ocupar su lugar."""
        if node.left_son is None:
            return node.right_son, node
        node.left_son, minimum = self._detach_minimum(node.left_son)
        return node, minimum

    # ------------------------------------------------------------------
    # Métricas estructurales para la comparación con el AVL
    # ------------------------------------------------------------------

    def height(self):
        """Altura del árbol con la convención de la sección 14: vacío = -1,
        hoja = 0. Coincide con la profundidad máxima que pide mostrar la
        sección 12. Se calcula bajo demanda: O(n)."""
        return self._height(self.root)

    def _height(self, node):
        if node is None:
            return -1
        return 1 + max(self._height(node.left_son), self._height(node.right_son))

    def count_leaves(self):
        """Cantidad de hojas (nodos sin hijos). O(n)."""
        return self._count_leaves(self.root)

    def _count_leaves(self, node):
        if node is None:
            return 0
        if node.left_son is None and node.right_son is None:
            return 1
        return self._count_leaves(node.left_son) + self._count_leaves(node.right_son)

    # ------------------------------------------------------------------
    # Recorridos (vista comparativa de la sección 15 y auditoría del orden).
    # Todos devuelven listas de Event. Costo: O(n).
    # ------------------------------------------------------------------

    def inorder(self):
        """Izquierda, raíz, derecha: eventos en orden ASCENDENTE de K. Si el
        árbol está bien construido, esta lista siempre sale ordenada."""
        result = []
        self._inorder(self.root, result)
        return result

    def _inorder(self, node, result):
        if node is None:
            return
        self._inorder(node.left_son, result)
        result.append(node.event)
        self._inorder(node.right_son, result)

    def preorder(self):
        """Raíz, izquierda, derecha."""
        result = []
        self._preorder(self.root, result)
        return result

    def _preorder(self, node, result):
        if node is None:
            return
        result.append(node.event)
        self._preorder(node.left_son, result)
        self._preorder(node.right_son, result)

    def postorder(self):
        """Izquierda, derecha, raíz."""
        result = []
        self._postorder(self.root, result)
        return result

    def _postorder(self, node, result):
        if node is None:
            return
        self._postorder(node.left_son, result)
        self._postorder(node.right_son, result)
        result.append(node.event)

    def level_order(self):
        """Por niveles, de arriba hacia abajo y de izquierda a derecha.
        Versión recursiva: un recorrido preorden que guarda cada nodo en la
        lista de su nivel; como el preorden visita la izquierda antes que la
        derecha, cada nivel queda de izquierda a derecha."""
        levels = []
        self._collect_levels(self.root, 0, levels)
        return [event for level in levels for event in level]

    def _collect_levels(self, node, depth, levels):
        if node is None:
            return
        if depth == len(levels):
            levels.append([])
        levels[depth].append(node.event)
        self._collect_levels(node.left_son, depth + 1, levels)
        self._collect_levels(node.right_son, depth + 1, levels)
