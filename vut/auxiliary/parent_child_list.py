class ParentChildTreeList:
    """
    An immutable linked-list node that behaves like a sequence.
    Adding elements returns a NEW node pointing to the OLD node (Parent).
    Iteration yields elements in chronological order (Root -> ... -> Head).
    """
    __slots__ = ('_chunk', '_parent', '_length', '_last_item')

    def __init__(self, chunk=None, parent=None):
        # We store 'chunks' (lists of items) to reduce recursion depth 
        # vs storing 1 item per node.
        self._chunk = chunk if chunk else []
        self._parent = parent
        
        # Cache length for O(1) access
        prev_len = parent._length if parent else 0
        self._length = len(self._chunk) + prev_len
        
        # Cache last item for O(1) access
        if self._chunk:
            self._last_item = self._chunk[-1]
        elif parent:
            self._last_item = parent._last_item
        else:
            self._last_item = None

    def add(self, item):
        """Returns a NEW ParentChildTreeList with 'item' appended."""
        # Wrap single item in a list to allow consistent chunk handling
        return ParentChildTreeList([item], parent=self)

    def extend(self, items):
        """Returns a NEW ParentChildTreeList with a list of items appended."""
        if not items:
            return self
        return ParentChildTreeList(list(items), parent=self)

    def last(self):
        """Returns the very last element added (or None)."""
        return self._last_item

    def __len__(self):
        return self._length

    def __iter__(self):
        """Yields elements from oldest to newest."""
        # 1. Collect path backwards: Current -> Parent -> Grandparent
        path = []
        curr = self
        while curr:
            if curr._chunk:
                path.append(curr._chunk)
            curr = curr._parent
        
        # 2. Iterate forwards
        while path:
            yield from path.pop()

    def __repr__(self):
        return f"ParentChildTreeList(len={self._length})"
