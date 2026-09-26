from app.structures.avl_node import AVLNode

# Claves de las métricas de rotación que exige la sección 14 del enunciado.
# Son las mismas claves que usa Scenario.metrics.
ROTATION_METRIC_KEYS = ("LL", "RR", "LR", "RL", "simple_left", "simple_right")


class AVLTopologySnapshot:
    """Copia de la FORMA del árbol en un momento dado, para poder
    deshacer una acción que la cambió (sección 13: al deshacer se recupera
    el estado exacto, incluida la topología).

    No copia eventos ni crea nodos nuevos: guarda, para cada nodo que
    existía, a qué nodos apuntaban sus enlaces y cuál era su altura. Como
    se conservan los mismos objetos AVLNode, Scenario.event_index (id ->
    AVLNode) sigue siendo válido después de restaurar.

    - root: nodo que era la raíz (o None si el árbol estaba vacío).
    - size: cantidad de nodos en ese momento.
    - links: lista de tuplas (nodo, left_son, right_son, parent, height).

    Memoria: O(n) referencias (5 por nodo), no copias de eventos.
    """

    def __init__(self, root, size, links):
        self.root = root
        self.size = size
        self.links = links


class AVLTree:
    """Árbol AVL de eventos activos, ordenado por la clave K = (P, M, I).

    Comparación de claves: `Event.key` es la tupla (prioridad, magnitud,
    identificador). Python compara tuplas de forma lexicográfica, que es
    exactamente la regla de la sección 5, así que se usa `<` / `>` directo.

    Implementación recursiva: cada función recursiva recibe la raíz de un
    subárbol y DEVUELVE la raíz (posiblemente nueva, si hubo rotación) de
    ese subárbol; quien la llamó la vuelve a enganchar como hijo. Además se
    mantiene el puntero `parent` de cada nodo con `_set_left`/`_set_right`,
    para poder calcular profundidades y saber de quién cuelga cada nodo.

    Modo normal / modo estrés: el árbol no guarda el modo (eso vive en
    Scenario.mode, para no duplicar estado). Las operaciones reciben el
    parámetro `balance`: con True se rota como en un AVL normal; con False
    (modo estrés) se conserva el orden BST y se actualizan las alturas,
    pero no se rota. Después, `recover_balance()` repara el árbol.

    Métricas de rotación: el árbol recibe el diccionario de métricas de
    Scenario (el mismo objeto, no una copia) y suma ahí directamente, así
    que hay una sola fuente de verdad. Además, cada operación pública deja
    en `last_rotations` el detalle de las rotaciones que produjo, para
    mostrarlas en la interfaz (sección 8) y para poder revertir las
    métricas al deshacer esa acción (sección 14).
    """

    def __init__(self, metrics=None):
        self.root = None
        self._size = 0
        # Si Scenario pasa su diccionario, se comparte; si no, se crea uno propio.
        self.metrics = metrics if metrics is not None else {}
        for metric_key in ROTATION_METRIC_KEYS:
            self.metrics.setdefault(metric_key, 0)
        # Rotaciones de la última operación pública (insert, recover_balance...).
        self.last_rotations = []

    # ==================================================================
    # Utilidades básicas
    # ==================================================================

    def __len__(self):
        """Cantidad de eventos activos en el árbol. O(1)."""
        return self._size

    def is_empty(self):
        return self.root is None

    def clear(self):
        """Vacía el árbol (por ejemplo, antes de cargar un escenario nuevo).
        No toca las métricas: eso lo decide Scenario."""
        self.root = None
        self._size = 0
        self.last_rotations = []

    @staticmethod
    def _height(node):
        """Altura de un subárbol: -1 si está vacío (sección 14)."""
        return node.height if node is not None else -1

    def _update_height(self, node):
        """Recalcula la altura de `node` a partir de la de sus hijos.
        Solo es correcta si las alturas de los hijos ya están al día."""
        node.height = 1 + max(self._height(node.left_son), self._height(node.right_son))

    @staticmethod
    def _set_left(parent, child):
        """Engancha `child` como hijo izquierdo de `parent` y actualiza el
        puntero `parent` del hijo. Usar SIEMPRE esto (y _set_right) en vez
        de asignar left_son directamente, para no desincronizar `parent`."""
        parent.left_son = child
        if child is not None:
            child.parent = parent

    @staticmethod
    def _set_right(parent, child):
        """Igual que _set_left, para el hijo derecho."""
        parent.right_son = child
        if child is not None:
            child.parent = parent

    def _set_root(self, node):
        """Fija la raíz del árbol; la raíz nunca tiene padre."""
        self.root = node
        if node is not None:
            node.parent = None

    # ==================================================================
    # Rotaciones
    # ==================================================================

    def _rotate_right(self, node):
        """Giro simple a la derecha sobre `node` (resuelve el caso LL).

                node                pivot
               /    \\              /     \\
            pivot    C    ->      A      node
            /   \\                        /    \\
           A     B                      B      C

        Devuelve `pivot`, la nueva raíz del subárbol. El orden inorden
        (A, pivot, B, node, C) no cambia, por eso la rotación conserva el
        orden BST. Suma 1 a la métrica `simple_right`.
        """
        pivot = node.left_son
        old_parent = node.parent

        self._set_left(node, pivot.right_son)   # B pasa a ser hijo izquierdo de node
        self._set_right(pivot, node)            # node baja a la derecha de pivot
        pivot.parent = old_parent               # pivot ocupa el lugar que tenía node

        # Primero node (ahora está más abajo) y luego pivot.
        self._update_height(node)
        self._update_height(pivot)

        self.metrics["simple_right"] += 1
        return pivot

    def _rotate_left(self, node):
        """Giro simple a la izquierda sobre `node` (resuelve el caso RR).
        Es el espejo de _rotate_right. Suma 1 a `simple_left`."""
        pivot = node.right_son
        old_parent = node.parent

        self._set_right(node, pivot.left_son)
        self._set_left(pivot, node)
        pivot.parent = old_parent

        self._update_height(node)
        self._update_height(pivot)

        self.metrics["simple_left"] += 1
        return pivot

    def _rebalance(self, node):
        """Si `node` está desbalanceado (|factor| > 1), aplica el caso que
        corresponde y devuelve la nueva raíz del subárbol. Si no lo está,
        devuelve `node` sin tocar nada.

        El caso se decide con los factores de balance (no comparando claves),
        así sirve igual para inserción, eliminación y recuperación global:
        - factor > 1 y factor del hijo izquierdo >= 0  -> caso LL (giro derecha)
        - factor > 1 y factor del hijo izquierdo < 0   -> caso LR (giro izquierda en el hijo + giro derecha)
        - factor < -1 y factor del hijo derecho <= 0   -> caso RR (giro izquierda)
        - factor < -1 y factor del hijo derecho > 0    -> caso RL (giro derecha en el hijo + giro izquierda)

        Métricas (sección 14): un caso simple suma 1 al caso y 1 giro
        elemental; un caso doble suma 1 al caso (LR o RL) y 2 giros
        elementales. Cada caso atendido queda registrado en last_rotations.

        NOTA para la eliminación: después de retirar un nodo, basta con
        actualizar la altura y llamar a este método en cada nodo del camino
        de regreso (igual que hace _insert).
        """
        balance = node.balance_factor
        event_id = node.event.event_id

        if balance > 1:
            if node.left_son.balance_factor >= 0:
                case, rotations = "LL", ["right"]
                new_root = self._rotate_right(node)
            else:
                case, rotations = "LR", ["left", "right"]
                self._set_left(node, self._rotate_left(node.left_son))
                new_root = self._rotate_right(node)
        elif balance < -1:
            if node.right_son.balance_factor <= 0:
                case, rotations = "RR", ["left"]
                new_root = self._rotate_left(node)
            else:
                case, rotations = "RL", ["right", "left"]
                self._set_right(node, self._rotate_right(node.right_son))
                new_root = self._rotate_left(node)
        else:
            return node

        self.metrics[case] += 1
        self.last_rotations.append({
            "case": case,                 # LL, RR, LR o RL
            "event_id": event_id,         # evento del nodo que estaba desbalanceado
            "balance_factor": balance,    # factor que tenía antes de rotar
            "rotations": rotations,       # giros elementales aplicados, en orden
        })
        return new_root

    def last_rotation_delta(self):
        """Resume `last_rotations` en cuánto sumó la última operación a cada
        métrica de rotación. Scenario puede guardar este diccionario en la
        acción de la pila para restarlo al deshacer (pendiente #8)."""
        delta = {metric_key: 0 for metric_key in ROTATION_METRIC_KEYS}
        for entry in self.last_rotations:
            delta[entry["case"]] += 1
            for rotation in entry["rotations"]:
                delta["simple_" + rotation] += 1
        return delta

    def revert_rotation_metrics(self, delta):
        """Resta un delta obtenido con last_rotation_delta(). Se usa al
        deshacer una acción, para que las métricas vuelvan a su valor
        anterior (la sección 14 exige que los contadores sean restaurables)."""
        for metric_key, amount in delta.items():
            self.metrics[metric_key] -= amount

    # ==================================================================
    # Inserción
    # ==================================================================

    def insert(self, event, balance=True):
        """Inserta `event` según su clave actual `event.key` y devuelve el
        AVLNode creado (para guardarlo en Scenario.event_index).

        - balance=True  (modo normal): se rota donde haga falta; el árbol
          termina siendo un AVL válido.
        - balance=False (modo estrés): se conserva el orden BST y se
          actualizan alturas, pero no se rota.

        Lanza ValueError si ya hay un nodo con exactamente la misma clave;
        en ese caso el árbol no se modifica. OJO: el árbol solo puede
        detectar claves repetidas. Comprobar que el IDENTIFICADOR no exista
        (activo, archivado o eliminado) le toca a Scenario ANTES de llamar
        aquí, porque el mismo id podría llegar con otra clave (sección 5).

        Costo: O(log n) en modo normal; O(h) en modo estrés.
        """
        self.last_rotations = []
        new_node = AVLNode(event)
        self._set_root(self._insert(self.root, new_node, balance))
        self._size += 1
        return new_node

    def _insert(self, node, new_node, balance):
        """Inserción recursiva en el subárbol `node`. Devuelve la raíz
        (posiblemente nueva) de ese subárbol."""
        if node is None:
            return new_node   # se encontró el hueco: el nodo nuevo es una hoja

        new_key = new_node.event.key
        node_key = node.event.key

        if new_key < node_key:
            self._set_left(node, self._insert(node.left_son, new_node, balance))
        elif new_key > node_key:
            self._set_right(node, self._insert(node.right_son, new_node, balance))
        else:
            # Se lanza antes de modificar nada: ningún ancestro alcanza a
            # re-enganchar hijos ni a cambiar alturas.
            raise ValueError(f"Ya existe un evento con la clave {new_key} en el AVL")

        # De regreso hacia la raíz: actualizar altura y, si toca, rebalancear.
        self._update_height(node)
        if balance:
            return self._rebalance(node)
        return node

    # ==================================================================
    # Eliminación  (PENDIENTE)
    # ==================================================================

    def minimum(self, node):
        """Devuelve el nodo con la clave mínima del subárbol `node`: el que
        está más a la izquierda. Para la eliminación con dos hijos se llama
        sobre node.right_son para obtener el sucesor inorden."""
        while node.left_son is not None:
            node = node.left_son
        return node

    # TODO (VALERY) - Lista de ajustes para terminar `elimination` y
    # que encaje con el resto del árbol y con Scenario:
    #  1. Usar los nombres del nodo: event, left_son, right_son (no value/left/right).
    #  2. Navegar con la clave `key` recibida, pero reconocer el nodo buscado por
    #     node.event.event_id == key[2]. En una corrección el Event ya fue
    #     modificado y event.key devuelve la clave nueva, mientras el nodo sigue
    #     ubicado con la vieja: Scenario llamará delete(old_key).
    #  3. Usar elif / else y DEVOLVER `node` también cuando se baja por la
    #     izquierda o por la derecha (hoy devuelve None y borra subárboles).
    #  4. Caso dos hijos: mover el NODO sucesor a la posición del eliminado
    #     (re-enganchando punteros), NO copiar su evento. Scenario.event_index
    #     guarda id -> AVLNode; si se copian eventos, el índice queda apuntando
    #     al nodo equivocado. (En BSTTree.delete hay un ejemplo recursivo.)
    #  5. Enganchar hijos siempre con self._set_left / self._set_right, para
    #     mantener `parent` correcto.
    #  6. En el camino de regreso: self._update_height(node) y, si balance es
    #     True, return self._rebalance(node) (así se cuentan las rotaciones).
    #  7. Método público: delete(self, key, balance=True) que haga
    #     self.last_rotations = [], self._set_root(...), self._size -= 1,
    #     lance KeyError si no existe y devuelva el Event retirado.

    def elimination(self, node, value):
        if node is None:
            return None

        #se mueve al subarbol izquierdo
        if value<node.value:
            node.left= self.elimination(node.left, value)

        #se mueve al subarbol derecho
        if value>node.value:
            node.right = (self.elimination(node.right, value))

        #node found
        if value == node.value:
            #leaf case
            if node.left==None and node.right==None:
                return None

            #one child case
            #if the evaluated node son is none it means the other son will
            #be in the eliminated node position
            if node.left is None:
                return node.right
            if node.right == None:
                return node.left

            #two child case
            if node.left!= None and node.right != None:{}

    # ==================================================================
    # Búsqueda y profundidad
    # ==================================================================

    def search(self, key):
        """Busca el nodo con clave exactamente `key` = (P, M, I).
        Devuelve (nodo_o_None, nodos_visitados).

        `nodos_visitados` es el costo simulado de la sección 9: para un
        evento existente es su profundidad + 1. También sirve para la
        comparación con el BST (sección 11).
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

    def depth_of(self, node):
        """Profundidad del nodo (sección 9): raíz = 0, hijo = padre + 1.
        Sube por los punteros `parent`. Costo: O(profundidad)."""
        if node.parent is None:
            return 0
        return 1 + self.depth_of(node.parent)

    def costly_access(self, limit):
        """Eventos de prioridad alta (P = 3) cuya profundidad es
        estrictamente mayor que el límite L (sección 9 y consulta de la
        sección 11). Devuelve una lista de diccionarios con el evento, su
        profundidad y los nodos que se visitan al buscarlo por clave
        (profundidad + 1). Costo: O(n)."""
        result = []
        self._collect_costly(self.root, 0, limit, result)
        return result

    def _collect_costly(self, node, depth, limit, result):
        if node is None:
            return
        if node.event.priority == 3 and depth > limit:
            result.append({"event": node.event, "depth": depth, "visited": depth + 1})
        self._collect_costly(node.left_son, depth + 1, limit, result)
        self._collect_costly(node.right_son, depth + 1, limit, result)

    # ==================================================================
    # Métricas estructurales (secciones 11, 12 y 14)
    # ==================================================================

    def height(self):
        """Altura del árbol completo (vacío = -1). Es la altura guardada en
        la raíz, O(1). La auditoría comprueba que coincida con la real."""
        return self._height(self.root)

    def count_leaves(self):
        """Cantidad de hojas. Costo: O(n)."""
        return self._count_leaves(self.root)

    def _count_leaves(self, node):
        if node is None:
            return 0
        if node.left_son is None and node.right_son is None:
            return 1
        return self._count_leaves(node.left_son) + self._count_leaves(node.right_son)

    # ==================================================================
    # Recorridos (sección 14). Todos devuelven listas de Event. O(n).
    # ==================================================================

    def inorder(self):
        """Izquierda, raíz, derecha: claves ASCENDENTES."""
        result = []
        self._inorder(self.root, result)
        return result

    def _inorder(self, node, result):
        if node is None:
            return
        self._inorder(node.left_son, result)
        result.append(node.event)
        self._inorder(node.right_son, result)

    def reverse_inorder(self):
        """Derecha, raíz, izquierda: claves DESCENDENTES. Es el recorrido
        base para "los primeros k pendientes en orden descendente de K"
        (sección 11)."""
        result = []
        self._reverse_inorder(self.root, result)
        return result

    def _reverse_inorder(self, node, result):
        if node is None:
            return
        self._reverse_inorder(node.right_son, result)
        result.append(node.event)
        self._reverse_inorder(node.left_son, result)

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
        Versión recursiva: un recorrido preorden que va guardando cada nodo
        en la lista de su nivel. Como el preorden visita siempre la
        izquierda antes que la derecha, cada nivel queda de izquierda a
        derecha. Luego se concatenan los niveles."""
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

    # ==================================================================
    # Modo estrés: detección de desbalance y recuperación global (sección 8)
    # ==================================================================

    def unbalanced_nodes(self):
        """Nodos cuyo factor de balance está fuera de {-1, 0, 1}. En modo
        estrés sirve para que la interfaz indique que el árbol dejó de
        cumplir la condición AVL. Costo: O(n)."""
        result = []
        self._collect_unbalanced(self.root, result)
        return result

    def _collect_unbalanced(self, node, result):
        if node is None:
            return
        if abs(node.balance_factor) > 1:
            result.append(node)
        self._collect_unbalanced(node.left_son, result)
        self._collect_unbalanced(node.right_son, result)

    def is_avl(self):
        """True si ningún nodo está desbalanceado (según alturas guardadas)."""
        return len(self.unbalanced_nodes()) == 0

    def recover_balance(self):
        """Recuperación global: restablece la propiedad AVL SOLO con
        rotaciones, sin vaciar ni reconstruir el árbol (lo prohíbe la
        sección 8). Funciona aunque haya diferencias de altura mayores que 2.
        Devuelve la lista de rotaciones aplicadas (también queda en
        last_rotations), que es el "costo" que se muestra en la interfaz.

        Procedimiento (_recover), de abajo hacia arriba:
          1. Recuperar primero los dos subárboles (quedan AVL).
          2. Mientras el nodo actual tenga |factor| > 1, aplicar el caso que
             toca (_rebalance) y recuperar el subárbol del nodo que bajó,
             porque puede haber quedado desbalanceado.

        Por qué conserva el orden: solo se usan rotaciones, y una rotación
        no cambia el recorrido inorden.

        Por qué termina (para sustentar en el manual técnico):
          - Cada llamada recursiva trabaja sobre un subárbol con menos nodos
            que el actual, así que la recursión no es infinita.
          - Una rotación aplicada a un nodo con |factor| >= 2 (con hijos ya
            AVL) nunca aumenta la altura de ese subárbol; por inducción,
            recuperar un subárbol tampoco aumenta su altura.
          - Si el nodo está cargado a la izquierda (factor >= 2), después de
            cada caso la altura del lado izquierdo baja exactamente en 1, y
            el lado derecho no puede superar esa nueva altura en más de 1,
            así que el desbalance nunca "salta" al otro lado. Como la altura
            izquierda no puede bajar indefinidamente, el ciclo termina en a
            lo sumo tantas vueltas como la altura inicial. El caso derecho
            es simétrico.

        Costo: O(n) para recorrer el árbol más el trabajo de las rotaciones.
        """
        self.last_rotations = []
        self._set_root(self._recover(self.root))
        return list(self.last_rotations)

    def _recover(self, node):
        if node is None:
            return None

        # 1. Primero los hijos (recorrido postorden).
        self._set_left(node, self._recover(node.left_son))
        self._set_right(node, self._recover(node.right_son))
        self._update_height(node)

        # 2. Rotar en este nodo hasta que quede balanceado.
        while abs(node.balance_factor) > 1:
            left_heavy = node.balance_factor > 1
            node = self._rebalance(node)
            # El nodo desbalanceado bajó hacia el lado liviano: ese subárbol
            # es el único que puede haber quedado desbalanceado.
            if left_heavy:
                self._set_right(node, self._recover(node.right_son))
            else:
                self._set_left(node, self._recover(node.left_son))
            self._update_height(node)

        return node

    # ==================================================================
    # Copia de la topología (para deshacer, sección 13)
    # ==================================================================

    def snapshot_topology(self):
        """Toma una copia de la forma actual del árbol (ver
        AVLTopologySnapshot). Se llama ANTES de una acción que reorganiza
        el árbol, por ejemplo la recuperación global, y la copia se guarda
        en la acción de la pila de deshacer. Costo: O(n)."""
        links = []
        self._collect_links(self.root, links)
        return AVLTopologySnapshot(self.root, self._size, links)

    def _collect_links(self, node, links):
        """Recorre el árbol en preorden guardando los enlaces y la altura
        de cada nodo tal como están ahora."""
        if node is None:
            return
        links.append((node, node.left_son, node.right_son, node.parent, node.height))
        self._collect_links(node.left_son, links)
        self._collect_links(node.right_son, links)

    def restore_topology(self, snapshot):
        """Devuelve el árbol exactamente a la forma guardada en `snapshot`:
        vuelve a poner en cada nodo los enlaces y la altura que tenía, y
        restaura la raíz y el tamaño. Costo: O(n).

        Solo es correcto si, desde que se tomó la copia, no entraron ni
        salieron nodos del árbol. La pila de deshacer lo garantiza: al
        deshacer una acción, todas las acciones posteriores ya se
        deshicieron antes (orden LIFO).

        No toca las métricas: Scenario las revierte aparte con
        revert_rotation_metrics(delta)."""
        for node, left_son, right_son, parent, height in snapshot.links:
            node.left_son = left_son
            node.right_son = right_son
            node.parent = parent
            node.height = height
        self.root = snapshot.root
        self._size = snapshot.size
        self.last_rotations = []

    # ==================================================================
    # Auditoría: "Verificar estructura" (sección 14)
    # ==================================================================

    def audit(self, require_balance=True):
        """Revisa TODO el árbol y devuelve una lista de problemas, uno por
        evento inconsistente. Lista vacía = estructura correcta.

        Comprueba:
          - orden GLOBAL por K: cada nodo debe estar dentro del rango
            (mínimo, máximo) que le imponen TODOS sus ancestros, no solo su
            padre inmediato;
          - unicidad de identificadores y que ningún nodo aparezca dos veces
            (lo que indicaría un ciclo o un nodo compartido);
          - referencias: el `parent` de cada hijo apunta a su padre real;
          - alturas guardadas contra alturas recalculadas;
          - factores de balance.

        require_balance=True (modo normal): un factor fuera de {-1, 0, 1} es
        un error. require_balance=False (modo estrés): se informa como
        desbalance "esperado", distinto de los errores de orden o metadatos.

        Cada problema es un dict: {"event_id", "type", "severity", "detail"}.
        """
        issues = []
        seen_ids = set()
        seen_nodes = set()
        if self.root is not None and self.root.parent is not None:
            issues.append(self._issue(self.root, "reference", "error", "La raíz tiene padre"))
        self._audit(self.root, None, None, None, require_balance, issues, seen_ids, seen_nodes)
        if len(seen_nodes) != self._size:
            issues.append({
                "event_id": None, "type": "size", "severity": "error",
                "detail": f"El contador dice {self._size} nodos pero hay {len(seen_nodes)}",
            })
        return issues

    @staticmethod
    def _issue(node, issue_type, severity, detail):
        return {"event_id": node.event.event_id, "type": issue_type, "severity": severity, "detail": detail}

    def _audit(self, node, expected_parent, low, high, require_balance, issues, seen_ids, seen_nodes):
        """Revisa el subárbol `node` y devuelve su altura REAL (recalculada)."""
        if node is None:
            return -1

        if id(node) in seen_nodes:
            issues.append(self._issue(node, "reference", "error", "El nodo aparece dos veces (ciclo o nodo compartido)"))
            return -1   # no se sigue bajando, para no entrar en un ciclo
        seen_nodes.add(id(node))

        event_id = node.event.event_id
        if event_id in seen_ids:
            issues.append(self._issue(node, "uniqueness", "error", "Identificador repetido en el árbol"))
        seen_ids.add(event_id)

        if node.parent is not expected_parent and expected_parent is not None:
            issues.append(self._issue(node, "reference", "error", "El puntero parent no apunta a su padre real"))

        key = node.event.key
        if low is not None and not key > low:
            issues.append(self._issue(node, "order", "error", f"Clave {key} debería ser mayor que {low}"))
        if high is not None and not key < high:
            issues.append(self._issue(node, "order", "error", f"Clave {key} debería ser menor que {high}"))

        left_height = self._audit(node.left_son, node, low, key, require_balance, issues, seen_ids, seen_nodes)
        right_height = self._audit(node.right_son, node, key, high, require_balance, issues, seen_ids, seen_nodes)

        real_height = 1 + max(left_height, right_height)
        if node.height != real_height:
            issues.append(self._issue(node, "height", "error", f"Altura guardada {node.height}, altura real {real_height}"))

        real_balance = left_height - right_height
        if node.balance_factor != real_balance:
            issues.append(self._issue(node, "balance_factor", "error", f"Factor guardado {node.balance_factor}, factor real {real_balance}"))
        if abs(real_balance) > 1:
            severity = "error" if require_balance else "expected"
            issues.append(self._issue(node, "imbalance", severity, f"Factor de balance {real_balance}"))

        return real_height
