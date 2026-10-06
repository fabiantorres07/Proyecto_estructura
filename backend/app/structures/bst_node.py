class BSTNode:
    """Node of the comparison BST tree (without balancing).

    Keeps a reference to the SAME Event object used by the AVL (not a
    copy): this way both trees share the event's identity, as
    required by the prompt, and a correction applied to the Event looks the same
    from both trees.

    Does not keep `parent` or `height`:
    - `parent` is not needed because in a BST without balancing no
      operation needs to "go up" after finishing: insert and
      delete are a single downward traversal, and the parent is carried in
      a local variable during that traversal (see BSTTree.delete).
    - `height` is not needed because no algorithm of this tree queries it
      in the middle of an operation (there is no balance factor or
      rotations). The height is calculated on demand in BSTTree.height().
    """

    def __init__(self, event, left_son=None, right_son=None):
        self.event = event          # Stored Event (same instance as in the AVL).
        self.left_son = left_son    # Left subtree: smaller keys (BSTNode or None).
        self.right_son = right_son  # Right subtree: larger keys (BSTNode or None).
