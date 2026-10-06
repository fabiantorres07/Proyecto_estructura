from datetime import timedelta
from app.structures.avl_node import AVLNode

# Keys of the rotation metrics required by section 14 of the specification.
# These are the same keys used by Scenario.metrics.
ROTATION_METRIC_KEYS = ("LL", "RR", "LR", "RL", "simple_left", "simple_right")


class AVLTopologySnapshot:
    """Snapshot of tree SHAPE at a given moment, to be able to
    undo an action that changed it (section 13: undo restores
    the exact state, including topology).

    Does not copy events or create new nodes: saves, for each node that
    existed, which nodes its links pointed to and what its height was. Since
    the same AVLNode objects are retained, Scenario.event_index (id ->
    AVLNode) remains valid after restoration.

    - root: node that was the root (or None if the tree was empty).
    - size: number of nodes at that moment.
    - links: list of tuples (node, left_son, right_son, parent, height).

    Memory: O(n) references (5 per node), no event copies.
    """

    def __init__(self, root, size, links):
        self.root = root
        self.size = size
        self.links = links


class AVLTree:
    """AVL tree of active events, ordered by key K = (P, M, I).

    Key comparison: `Event.key` is the tuple (priority, magnitude,
    identifier). Python compares tuples lexicographically, which is
    exactly the rule from section 5, so direct `<` / `>` is used.

    Recursive implementation: each recursive function receives the root of a
    subtree and RETURNS the (possibly new, if rotated) root of
    that subtree; the caller reattaches it as a child. Additionally,
    the `parent` pointer of each node is maintained with `_set_left`/`_set_right`,
    to compute depths and know which node each one hangs from.

    Normal mode / stress mode: the tree does not store the mode (that lives in
    Scenario.mode to avoid duplicating state). Operations receive the
    `balance` parameter: with True it rotates like a normal AVL; with False
    (stress mode) it preserves BST order and updates heights,
    but does not rotate. Afterward, `recover_balance()` repairs the tree.

    Rotation metrics: the tree receives Scenario's metrics dictionary
    (the same object, not a copy) and increments there directly, so
    there is a single source of truth. Furthermore, each public operation leaves
    the detail of rotations produced in `last_rotations`, to
    display them in the interface (section 8) and to be able to revert
    metrics when undoing that action (section 14).
    """

    def __init__(self, metrics=None):
        self.root = None
        self._size = 0
        # If Scenario passes its dictionary, it is shared; otherwise, a new one is created.
        self.metrics = metrics if metrics is not None else {}
        for metric_key in ROTATION_METRIC_KEYS:
            self.metrics.setdefault(metric_key, 0)
        # Rotations of the last public operation (insert, recover_balance...).
        self.last_rotations = []
        # Rotation journal for a COMPOSITE operation of Scenario (for
        # example a correction = delete + insert, and each resets
        # last_rotations). Scenario opens it with [] before the operation and
        # closes it with None afterward; while it is None nothing is recorded.
        self.rotation_journal = None

    # ==================================================================
    # Basic utilities
    # ==================================================================

    def __len__(self):
        """Number of active events in the tree. O(1)."""
        return self._size

    def is_empty(self):
        return self.root is None

    def clear(self):
        """Empties the tree (for example, before loading a new scenario).
        Does not touch metrics: Scenario decides that."""
        self.root = None
        self._size = 0
        self.last_rotations = []

    @staticmethod
    def _height(node):
        """Height of a subtree: -1 if empty (section 14)."""
        return node.height if node is not None else -1

    def _update_height(self, node):
        """Recalculates height of `node` from its children's heights.
        Only correct if children's heights are already up to date."""
        node.height = 1 + max(self._height(node.left_son), self._height(node.right_son))

    @staticmethod
    def _set_left(parent, child):
        """Attaches `child` as left child of `parent` and updates the
        `parent` pointer of the child. ALWAYS use this (and _set_right) instead
        of assigning left_son directly, to avoid desynchronizing `parent`."""
        parent.left_son = child
        if child is not None:
            child.parent = parent

    @staticmethod
    def _set_right(parent, child):
        """Same as _set_left, for the right child."""
        parent.right_son = child
        if child is not None:
            child.parent = parent

    def _set_root(self, node):
        """Sets tree root; root never has a parent."""
        self.root = node
        if node is not None:
            node.parent = None

    # ==================================================================
    # Rotations
    # ==================================================================

    def _rotate_right(self, node):
        """Single right rotation on `node` (solves the LL case).

                node                pivot
               /    \\              /     \\
            pivot    C    ->      A      node
            /   \\                        /    \\
           A     B                      B      C

        Returns `pivot`, the new root of the subtree. The inorder traversal
        (A, pivot, B, node, C) does not change, which is why rotation preserves
        BST order. Adds 1 to the `simple_right` metric.
        """
        pivot = node.left_son
        old_parent = node.parent

        self._set_left(node, pivot.right_son)   # B becomes left child of node
        self._set_right(pivot, node)            # node moves down to the right of pivot
        pivot.parent = old_parent               # pivot takes the place node had

        # First node (now lower down) and then pivot.
        self._update_height(node)
        self._update_height(pivot)

        self.metrics["simple_right"] += 1
        return pivot

    def _rotate_left(self, node):
        """Single left rotation on `node` (solves the RR case).
        Mirror of _rotate_right. Adds 1 to `simple_left`."""
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
        """If `node` is unbalanced (|factor| > 1), applies the corresponding
        case and returns the new subtree root. If not,
        returns `node` untouched.

        The case is decided with balance factors (not comparing keys),
        so it serves insertion, deletion, and global recovery equally:
        - factor > 1 and left child factor >= 0  -> LL case (right rotation)
        - factor > 1 and left child factor < 0   -> LR case (left rotation on child + right rotation)
        - factor < -1 and right child factor <= 0 -> RR case (left rotation)
        - factor < -1 and right child factor > 0  -> RL case (right rotation on child + left rotation)

        Metrics (section 14): a single case adds 1 to the case and 1 elementary
        rotation; a double case adds 1 to the case (LR or RL) and 2 elementary
        rotations. Each handled case is recorded in last_rotations.

        NOTE for deletion: after removing a node, it suffices to update
        the height and call this method on each node of the return path
        (just as _insert does).
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
        entry = {
            "case": case,                 # LL, RR, LR or RL
            "event_id": event_id,         # event of the node that was unbalanced
            "balance_factor": balance,    # factor it had before rotating
            "rotations": rotations,       # elementary rotations applied, in order
        }
        self.last_rotations.append(entry)
        if self.rotation_journal is not None:
            self.rotation_journal.append(entry)
        return new_root

    def last_rotation_delta(self):
        """Summarizes `last_rotations` as what the last operation added to each
        rotation metric. Scenario can store this dictionary in the stack
        action to subtract it on undo."""
        delta = {metric_key: 0 for metric_key in ROTATION_METRIC_KEYS}
        for entry in self.last_rotations:
            delta[entry["case"]] += 1
            for rotation in entry["rotations"]:
                delta["simple_" + rotation] += 1
        return delta

    def revert_rotation_metrics(self, delta):
        """Subtracts a delta obtained with last_rotation_delta(). Used when
        undoing an action, so metrics return to their previous
        value (section 14 requires counters to be restorable)."""
        for metric_key, amount in delta.items():
            self.metrics[metric_key] -= amount

    def _rebalance_until_stable(self, node):
        """Rebalance `node` until its balance factor is in {-1, 0, 1},
        even if the initial imbalance is more than 2.

        Standard insert/delete only need one rotation per node on the way
        up, because the imbalance there is at most 2. But detach_subtree
        removes an ENTIRE subtree at once, which can leave the parent
        with a much larger imbalance. A single rotation per level is not
        enough in that case.

        This helper loops: rotate until the node is balanced, and after
        each rotation recursively repair the subtree that dropped down
        (it may also be unbalanced). It mirrors what _recover does,
        restricted to a single subtree.

        Returns the new root of the balanced subtree.
        """
        self._update_height(node)
        while abs(node.balance_factor) > 1:
            left_heavy = node.balance_factor > 1
            node = self._rebalance(node)
            if left_heavy:
                self._set_right(node, self._recover(node.right_son))
            else:
                self._set_left(node, self._recover(node.left_son))
            self._update_height(node)
        return node

    # ==================================================================
    # Insertion
    # ==================================================================

    def insert(self, event, balance=True):
        """Inserts `event` according to its current key `event.key` and returns the
        created AVLNode (to store in Scenario.event_index).

        - balance=True  (normal mode): rotates where necessary; the tree
          ends up being a valid AVL.
        - balance=False (stress mode): preserves BST order and updates
          heights, but does not rotate.

        Raises ValueError if there is already a node with the exact same key;
        in that case the tree is not modified. NOTE: the tree can only
        detect duplicate keys. Checking that the IDENTIFIER does not exist
        (active, archived, or eliminated) is Scenario's responsibility BEFORE
        calling here, because the same id could arrive with another key (section 5).

        Cost: O(log n) in normal mode; O(h) in stress mode.
        """
        self.last_rotations = []
        new_node = AVLNode(event)
        self._set_root(self._insert(self.root, new_node, balance))
        self._size += 1
        return new_node

    def _insert(self, node, new_node, balance):
        """Recursive insertion in subtree `node`. Returns the root
        (possibly new) of that subtree."""
        if node is None:
            return new_node   # slot found: the new node is a leaf

        new_key = new_node.event.key
        node_key = node.event.key

        if new_key < node_key:
            self._set_left(node, self._insert(node.left_son, new_node, balance))
        elif new_key > node_key:
            self._set_right(node, self._insert(node.right_son, new_node, balance))
        else:
            # Raised before modifying anything: no ancestor has reattached
            # children or changed heights yet.
            raise ValueError(f"Ya existe un evento con la clave {new_key} en el AVL")

        # On the way back to root: update height and, if needed, rebalance.
        self._update_height(node)
        if balance:
            return self._rebalance(node)
        return node

    # ==================================================================
    # Deletion
    # ==================================================================

    def minimum(self, node):
        """Returns the node with minimum key in subtree `node`: the leftmost
        node. For deletion with two children, called on node.right_son
        to get the inorder successor."""
        while node.left_son is not None:
            node = node.left_son
        return node  

    def _delete_min(self, node, balance):
        """Removes node with minimum key from subtree `node` and returns it
        detached, along with the new root of that subtree.
        Used in two-children case to move the successor without copying it."""
        if node.left_son is None:
            return node.right_son, node

        new_left, minimum_node = self._delete_min(node.left_son, balance)
        self._set_left(node, new_left)
        self._update_height(node)
        if balance:
            node = self._rebalance(node)
        return node, minimum_node

    def delete(self, key, balance=True):
        """Public delete method, returns the removed Event.
        Raises KeyError if no event with that key exists
        (exception raised by `_delete` upon reaching an empty subtree).
        """
        self.last_rotations = []
        removed = []
        self._set_root(self._delete(self.root, key, balance, removed))
        self._size -= 1
        return removed[0]

    def _delete(self, node, key, balance, removed):
        """Deletes from this subtree the node whose identifier is key[2] and
        returns the new root of that subtree. When found, appends its
        Event to the `removed` list (so `delete` does not need to search
        again, working even if the event was corrected).

        The node is recognized by its identifier (key[2]), not by full key
        equality: if the event had a correction, node.event.key already
        returns the NEW key even though the node is still located according to the
        OLD key passed here (Scenario calls delete(old_key) in that case).
        """
        if node is None:
            raise KeyError(f"No existe un evento con identificador {key[2]} en el AVL")

        if node.event.event_id == key[2]:
            removed.append(node.event)

            # leaf case
            if node.left_son is None and node.right_son is None:
                return None

            # one child case
            if node.left_son is None:
                return node.right_son
            if node.right_son is None:
                return node.left_son

            # two child case
            new_right, successor = self._delete_min(node.right_son, balance)
            self._set_left(successor, node.left_son)
            self._set_right(successor, new_right)
            node = successor

        elif key < node.event.key:
            self._set_left(node, self._delete(node.left_son, key, balance, removed))
        else:
            self._set_right(node, self._delete(node.right_son, key, balance, removed))

        self._update_height(node)
        if balance:
            return self._rebalance(node)
        return node
    # ==================================================================
    # Search and depth
    # ==================================================================

    def search(self, key):
        """Searches for the node with key exactly `key` = (P, M, I).
        Returns (node_or_None, visited_nodes).

        `visited_nodes` is the simulated cost from section 9: for an
        existing event it is its depth + 1. Also serves for
        comparison with the BST (section 11).
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
        """Depth of node (section 9): root = 0, child = parent + 1.
        Ascends along `parent` pointers. Cost: O(depth)."""
        if node.parent is None:
            return 0
        return 1 + self.depth_of(node.parent)

    def costly_access(self, limit):
        """High-priority events (P = 3) whose depth is strictly greater
        than limit L (section 9 and query from section 11). Returns a
        list of dictionaries with the event, its depth, and the nodes
        visited when searching for it by key (depth + 1). Cost: O(n)."""
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
    # Structural metrics (sections 11, 12, and 14)
    # ==================================================================

    def height(self):
        """Height of full tree (empty = -1). Stored height at
        the root, O(1). Audit verifies it matches real height."""
        return self._height(self.root)

    def count_leaves(self):
        """Number of leaves. Cost: O(n)."""
        return self._count_leaves(self.root)

    def _count_leaves(self, node):
        if node is None:
            return 0
        if node.left_son is None and node.right_son is None:
            return 1
        return self._count_leaves(node.left_son) + self._count_leaves(node.right_son)

    # ==================================================================
    # Traversals (section 14). All return lists of Event. O(n).
    # ==================================================================

    def inorder(self):
        """Left, root, right: ASCENDING keys."""
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
        """Right, root, left: DESCENDING keys. Base traversal for
        "first k pending in descending order of K" (section 11)."""
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
        """Level order, top to bottom and left to right.
        Recursive version: a preorder traversal storing each node
        in its level list. Since preorder visits left before
        right, each level stays left to right. Then levels are concatenated."""
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
    # Stress mode: imbalance detection and global recovery (section 8)
    # ==================================================================

    def unbalanced_nodes(self):
        """Nodes whose balance factor is outside {-1, 0, 1}. In stress mode,
        serves to indicate in the interface that tree stopped satisfying
        the AVL condition. Cost: O(n)."""
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
        """True if no node is unbalanced (according to stored heights)."""
        return len(self.unbalanced_nodes()) == 0

    def recover_balance(self):
        """Global recovery: restores AVL property ONLY with
        rotations, without emptying or rebuilding the tree (forbidden by
        section 8). Works even with height differences greater than 2.
        Returns list of applied rotations (also recorded in
        last_rotations), which is the "cost" shown in the interface.

        Procedure (_recover), bottom-up:
          1. First recover both subtrees (becoming AVL).
          2. While current node has |factor| > 1, apply corresponding case
             (_rebalance) and recover the subtree of the demoted node,
             since it may have become unbalanced.

        Why it preserves order: only rotations are used, and a rotation
        does not change inorder traversal.

        Why it terminates (to support technical documentation):
          - Each recursive call operates on a subtree with fewer nodes
            than current, so recursion is not infinite.
          - A rotation applied to a node with |factor| >= 2 (with AVL children)
            never increases the height of that subtree; by induction,
            recovering a subtree never increases its height.
          - If the node is left-heavy (factor >= 2), after each case the
            left side's height decreases by exactly 1, and the right side
            cannot exceed that new height by more than 1, so imbalance never
            "jumps" to the other side. Since left height cannot decrease
            indefinitely, the loop terminates in at most as many iterations
            as the initial height. The right-heavy case is symmetric.

        Cost: O(n) to traverse the tree plus rotation work.
        """
        self.last_rotations = []
        self._set_root(self._recover(self.root))
        return list(self.last_rotations)

    def _recover(self, node):
        if node is None:
            return None

        # 1. First children (postorder traversal).
        self._set_left(node, self._recover(node.left_son))
        self._set_right(node, self._recover(node.right_son))
        self._update_height(node)

        # 2. Rotate at this node until balanced.
        while abs(node.balance_factor) > 1:
            left_heavy = node.balance_factor > 1
            node = self._rebalance(node)
            # The unbalanced node moved down toward the lighter side: that subtree
            # is the only one that could have become unbalanced.
            if left_heavy:
                self._set_right(node, self._recover(node.right_son))
            else:
                self._set_left(node, self._recover(node.left_son))
            self._update_height(node)

        return node

    # ==================================================================
    # Topology snapshot (for undo, section 13)
    # ==================================================================

    def snapshot_topology(self):
        """Takes a snapshot of current tree shape (see
        AVLTopologySnapshot). Called BEFORE an action reorganizing
        the tree, for example global recovery, and the snapshot is saved
        in the action on undo stack. Cost: O(n)."""
        links = []
        self._collect_links(self.root, links)
        return AVLTopologySnapshot(self.root, self._size, links)

    def _collect_links(self, node, links):
        """Traverses tree in preorder saving links and height
        of each node as they currently are."""
        if node is None:
            return
        links.append((node, node.left_son, node.right_son, node.parent, node.height))
        self._collect_links(node.left_son, links)
        self._collect_links(node.right_son, links)

    def restore_topology(self, snapshot):
        """Restores the tree exactly to the shape saved in `snapshot`:
        reinstates in each node the links and height it had, and
        restores the root and size. Cost: O(n).

        Only correct if no nodes were added or removed from tree since
        snapshot was taken. Undo stack guarantees this: when undoing an
        action, all subsequent actions were already undone (LIFO order).

        Does not touch metrics: Scenario reverts them separately with
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
    # Audit: "Verify structure" (section 14)
    # ==================================================================

    def audit(self, require_balance=True):
        """Inspects the ENTIRE tree and returns a list of issues, one per
        inconsistent event. Empty list = correct structure.

        Verifies:
          - GLOBAL order by K: each node must lie within the range
            (minimum, maximum) imposed by ALL ancestors, not just immediate
            parent;
          - uniqueness of identifiers and no node appearing twice
            (which would indicate a cycle or shared node);
          - references: each child's `parent` points to its real parent;
          - stored heights against recalculated heights;
          - balance factors.

        require_balance=True (normal mode): factor outside {-1, 0, 1} is
        an error. require_balance=False (stress mode): reported as
        "expected" imbalance, distinct from ordering or metadata errors.

        Each issue is a dict: {"event_id", "type", "severity", "detail"}.
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
        """Inspects subtree `node` and returns its REAL (recalculated) height."""
        if node is None:
            return -1

        if id(node) in seen_nodes:
            issues.append(self._issue(node, "reference", "error", "El nodo aparece dos veces (ciclo o nodo compartido)"))
            return -1   # stop descending to avoid infinite loop
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

    # ==================================================================
    # Mass archive: eligible subtrees (section 10)
    # ==================================================================

    def eligible_archive_subtrees(self, clock, T):
        """Returns ALL eligible subtrees for mass archiving.

        A subtree is eligible if all its events have low priority
        (P = 1) and age strictly greater than T hours, where
        age = clock - occurred_at. A leaf is also a subtree.

        The tree does not know clock or T (they live in Scenario), which is why
        it receives them as parameters, just like `balance` in insert/delete.

        Returns a list of dicts, one per eligible subtree:
            {"root": AVLNode, "root_id": int, "size": int, "depth": int}
        with everything needed for tie-breaking (size, root depth,
        root id), handled by Scenario. Empty list = no eligible branches.
        Also includes subtrees nested within another eligible one (in tie-breaking
        by size, a nested one never wins).
        Cost: O(n), single traversal."""
        result = []
        self._collect_eligible(self.root, 0, clock, timedelta(hours=T), result)
        return result

    def _collect_eligible(self, node, depth, clock, min_age, result):
        """POSTORDER traversal: first children, then node, because a
        node only knows if its subtree is eligible once it knows if its
        children's subtrees are. Returns (eligible_subtree, subtree_size).

        - An empty subtree counts as eligible ("all its events satisfy"
          is true if there are no events); thus a leaf is eligible
          if it satisfies the condition itself.
        - ALWAYS traverse both children even if this node does not qualify:
          within an ineligible branch there may be eligible subtrees."""
        if node is None:
            return True, 0

        left_ok, left_size = self._collect_eligible(node.left_son, depth + 1, clock, min_age, result)
        right_ok, right_size = self._collect_eligible(node.right_son, depth + 1, clock, min_age, result)

        event = node.event
        node_ok = event.priority == 1 and (clock - event.occurred_at) > min_age
        size = 1 + left_size + right_size
        eligible = node_ok and left_ok and right_ok

        if eligible:
            result.append({"root": node, "root_id": event.event_id, "size": size, "depth": depth})
        return eligible, size

    def subtree_event_ids(self, node):
        """Ids of all events in the subtree starting at `node`
        (inorder). Serves to fix the archive set BEFORE modifying
        the tree and displaying it to user. Cost: O(size)."""
        ids = []
        self._collect_subtree_ids(node, ids)
        return ids

    def _collect_subtree_ids(self, node, ids):
        if node is None:
            return
        self._collect_subtree_ids(node.left_son, ids)
        ids.append(node.event.event_id)
        self._collect_subtree_ids(node.right_son, ids)

    def _count_nodes(self, node):
        """Counts nodes of a subtree. O(n)."""
        if node is None:
            return 0
        return 1 + self._count_nodes(node.left_son) + self._count_nodes(node.right_son)

    def detach_subtree(self, node, balance=True):
        """Detach the subtree rooted at `node` from the tree, leaving the
        rest of the AVL balanced.

        The `balance` parameter makes it respect stress mode, same as
        insert and delete. In normal mode it rotates; in stress mode it
        does not. The caller (Scenario) decides.

        Returns (node, former_parent, was_left_child):
        - node: the root of the detached subtree (already without parent)
        - former_parent: the node it hung from, or None if `node` was the
          root of the tree
        - was_left_child: True if `node` was the left child of former_parent,
          False if it was the right one. If former_parent is None, the value
          does not matter (the tree is left empty).

        Steps:
        1. Save the position of the node (its parent and which side it
           hung from).
        2. Disconnect it: the parent loses that child, the node loses its
           parent.
        3. Subtract from _size the number of nodes of the detached subtree.
        4. Go up from former_parent to the root, updating heights and
           rebalancing AT EACH LEVEL UNTIL STABLE, because detaching an
           entire subtree can leave a node with an imbalance greater than 2.

        Stress mode: if `balance=False`, no rotation; only heights are
        updated. The tree keeps BST order but may end up unbalanced.

        Cost: O(log n) in normal mode, O(n) for `_count_nodes`.
        """
        # Reset the last-operation rotation log so the delta captured
        # AFTER this call reflects only the rotations produced HERE, not
        # the ones from whatever operation ran before.
        self.last_rotations = []

        former_parent = node.parent
        was_left_child = former_parent is not None and former_parent.left_son is node

        # 1. Disconnect from the parent (or remove it as root if it has none).
        if former_parent is None:
            self._set_root(None)
        elif was_left_child:
            former_parent.left_son = None
        else:
            former_parent.right_son = None

        # 2. Subtract from total size the nodes the subtree took with it.
        self._size -= self._count_nodes(node)

        # 3. The detached node is no longer in the tree.
        node.parent = None

        # 4. Go up from former_parent to the root, updating heights and
        # rebalancing. We save parent_of_current BEFORE rebalancing,
        # because _rebalance can rotate and change current.parent.
        current = former_parent
        while current is not None:
            parent_of_current = current.parent
            current_is_left = (
                parent_of_current is not None and parent_of_current.left_son is current
            )

            if balance:
                current = self._rebalance_until_stable(current)
            else:
                self._update_height(current)
            new_root = current

            # Reattach new_root to current's parent (if a rotation happened).
            if parent_of_current is None:
                self._set_root(new_root)
            elif current_is_left:
                self._set_left(parent_of_current, new_root)
            else:
                self._set_right(parent_of_current, new_root)

            current = parent_of_current

        return node, former_parent, was_left_child

    def subtree_events(self, node):
        """Events of subtree starting at `node`, in postorder.
        Cost: O(subtree size)."""
        events = []
        self._collect_subtree_events(node, events)
        return events

    def _collect_subtree_events(self, node, events):
        if node is None:
            return
        self._collect_subtree_events(node.left_son, events)
        self._collect_subtree_events(node.right_son, events)
        events.append(node.event)

    def attach_subtree(self, node, parent, was_left_child, balance=True):
        """Reattach a subtree detached with detach_subtree.

        It is the inverse: hangs `node` from `parent` (or sets it as root
        if parent is None) and goes up updating heights and rebalancing
        until each level is stable, because attaching an entire subtree
        can leave a node with an imbalance greater than 2.

        Increases _size by the number of nodes in the subtree.
        """
        if parent is None:
            self._set_root(node)
        elif was_left_child:
            self._set_left(parent, node)
        else:
            self._set_right(parent, node)

        self._size += self._count_nodes(node)

        current = parent
        while current is not None:
            parent_of_current = current.parent
            current_is_left = (
                parent_of_current is not None and parent_of_current.left_son is current
            )

            if balance:
                current = self._rebalance_until_stable(current)
            else:
                self._update_height(current)
            new_root = current

            if parent_of_current is None:
                self._set_root(new_root)
            elif current_is_left:
                self._set_left(parent_of_current, new_root)
            else:
                self._set_right(parent_of_current, new_root)

            current = parent_of_current

    def subtree_nodes(self, node):
        """List of nodes of the subtree starting at `node` (preorder).
        Analogous to subtree_events but returns AVLNode, not Event.
        Used in _undo_mass_archive to refill event_index."""
        nodes = []
        self._collect_subtree_nodes(node, nodes)
        return nodes

    def _collect_subtree_nodes(self, node, nodes):
        if node is None:
            return
        nodes.append(node)
        self._collect_subtree_nodes(node.left_son, nodes)
        self._collect_subtree_nodes(node.right_son, nodes)