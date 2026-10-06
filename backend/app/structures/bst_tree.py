from app.structures.bst_node import BSTNode


class BSTTree:
    """Binary search tree WITHOUT balancing, used as comparison tree
    against the AVL (sections 11 and 12).

    Design decision: this tree is kept ALIVE and synchronized
    with the AVL throughout the simulation. Every time Scenario inserts an event
    in the AVL, it also inserts it here; every time it removes it from the AVL
    (deletion, correction changing key, massive archive), it also removes it here.
    This way both trees always contain the same set of active events.

    The only difference with the AVL is that this NEVER rotates.

    Key comparison: `Event.key` is the tuple K = (P, M, I). Python compares
    tuples lexicographically.

    Recursive implementation: each recursive function receives the root of a subtree
    and, when modifying the tree, returns the (possibly new) root of that subtree.
    """

    def __init__(self):
        self.root = None   # Root (BSTNode) or None if tree is empty.
        self._size = 0     # Number of nodes, maintained in insert/delete.

    # ------------------------------------------------------------------
    # Consultas básicas
    # ------------------------------------------------------------------

    def __len__(self):
        """Number of events in the tree. O(1)."""
        return self._size

    def is_empty(self):
        return self.root is None

    def clear(self):
        """Empties the tree. Used when replacing the complete scenario
        (loading file, restoring version): the BST is not part
        of the exported state, so it is reconstructed with clear() + insert()."""
        self.root = None
        self._size = 0

    # ------------------------------------------------------------------
    # Inserción
    # ------------------------------------------------------------------

    def insert(self, event):
        """Inserts `event` according to its current key `event.key`: smaller key
        to the left, larger to the right, until finding a gap (None).
        No rebalancing.

        Raises ValueError if a node with the same key already exists.

        Cost: O(h), with h being the current height.
        """
        self.root = self._insert(self.root, event)
        self._size += 1

    def _insert(self, node, event):
        """Inserts into the `node` subtree and returns the subtree root."""
        if node is None:
            return BSTNode(event)   # gap found: the new node is a leaf

        key = event.key
        node_key = node.event.key
        if key < node_key:
            node.left_son = self._insert(node.left_son, event)
        elif key > node_key:
            node.right_son = self._insert(node.right_son, event)
        else:
            raise ValueError(f"An event with key {key} already exists in the BST")
        return node

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------

    def search(self, key):
        """Searches for the node with exact `key` = (P, M, I).
        Returns (node_or_None, visited_nodes).

        `visited_nodes` is the data from section 11 to compare search cost
        between AVL and BST. Cost: O(h).
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
        """Removes the event located with `key` and returns it.
        Raises KeyError if not found (tree is not modified).

        IMPORTANT: `key` is the key with which the event was INSERTED.
        In a correction, the Event is modified and `event.key` returns the new key,
        but the node is still located by the old one. We navigate with `key` and 
        recognize it by ID (key[2]).

        Cost: O(h).
        """
        new_root, removed = self._delete(self.root, key)
        if removed is None:
            raise KeyError(f"An event with key {key} does not exist in the BST")
        self.root = new_root
        self._size -= 1
        return removed.event

    def _delete(self, node, key):
        """Deletes in the `node` subtree. Returns a tuple
        (new_subtree_root, removed_node_or_None).

        Three classic cases:
        1. Leaf: subtree becomes empty (returns None).
        2. One child: that child takes the node's place.
        3. Two children: inorder successor takes the node's place.
        """
        if node is None:
            return None, None   # not found

        if node.event.event_id != key[2]:
            # Not the node yet: go down according to the key.
            if key < node.event.key:
                node.left_son, removed = self._delete(node.left_son, key)
            else:
                node.right_son, removed = self._delete(node.right_son, key)
            return node, removed

        # Found the node to remove.
        if node.left_son is None:          # cases 1 and 2 (no left child)
            replacement = node.right_son
        elif node.right_son is None:       # case 2 (only left child)
            replacement = node.left_son
        else:                              # case 3: two children
            new_right, successor = self._detach_minimum(node.right_son)
            successor.left_son = node.left_son
            successor.right_son = new_right
            replacement = successor

        # Release links from removed node.
        node.left_son = None
        node.right_son = None
        return replacement, node

    def _detach_minimum(self, node):
        """Separates the minimum node from the `node` subtree.
        Returns (new_subtree_root, minimum_node)."""
        if node.left_son is None:
            return node.right_son, node
        node.left_son, minimum = self._detach_minimum(node.left_son)
        return node, minimum

    # ------------------------------------------------------------------
    # Copia de la topología (para deshacer, sección 13)
    # ------------------------------------------------------------------

    def snapshot_topology(self):
        """Topology snapshot of the BST. Returns (root, size, links)."""
        links = []
        self._collect_links(self.root, links)
        return (self.root, self._size, links)

    def _collect_links(self, node, links):
        if node is None:
            return
        links.append((node, node.left_son, node.right_son))
        self._collect_links(node.left_son, links)
        self._collect_links(node.right_son, links)

    def restore_topology(self, snapshot):
        """Restores the BST exactly to the `snapshot` shape. O(n)."""
        root, size, links = snapshot
        for node, left_son, right_son in links:
            node.left_son = left_son
            node.right_son = right_son
        self.root = root
        self._size = size

    # ------------------------------------------------------------------
    # Métricas estructurales para la comparación con el AVL
    # ------------------------------------------------------------------

    def height(self):
        """Height of the tree: empty = -1, leaf = 0. Calculated on demand: O(n)."""
        return self._height(self.root)

    def _height(self, node):
        if node is None:
            return -1
        return 1 + max(self._height(node.left_son), self._height(node.right_son))

    def count_leaves(self):
        """Number of leaves (nodes without children). O(n)."""
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
        """Left, root, right: events in ASCENDING order of K."""
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
        """Root, left, right."""
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
        """Left, right, root."""
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
        """Level order traversal, top to bottom, left to right."""
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
