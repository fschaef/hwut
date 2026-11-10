"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FOREST OF THE FEATURES, 'hwut-feature-forest.csv', read
         (spec 43 section 1; intend/43 T-a, T-b, T-i, T-o). ONE file beside
         the 'hwut-root.conf' that begins the features of a tree:

    # comment
    gateway    : forwarding, buses
    forwarding : fwd, keeporder, dropunknown

    read_forest(top)            -> CForest | None
    forest_of_text(text, file)  -> CForest          (raises ForestFault)
    id_valid_f(text)            -> bool

A LINE is '<feature-id> : <child-feature-id> [, <child-feature-id>]*'.
Whitespace around ':' and ',' is insignificant; '#' comments and blank
lines are dropped. A ROOT is an id that stands as no child: roots are not
declared, they are what is left.

A FEATURE ID is '[A-Za-z0-9_-]+' (base64url), case kept and compared
(T-i, t-10). An id holding '.', ':', '/' or a glob character is no id
(t-8): one refusal, not three.

CHECKED HERE AND NOWHERE ELSE (t-3): an id under two parents, a circle,
an id standing twice on one line's right side, a left side standing
twice, a line naming no child. Each is a FAULT naming the file and the
line; a forest that cannot be read is the tree's fault and no face runs.

A PROTOTYPE (intend/44 P-a..P-d) is declared by a line whose left side
begins with '+'; its right side names its MEMBERS and the prototypes it
aggregates ('+<id>'). A feature line's right side may aggregate one too:

    +cover         : +cover-compare, cover-exact
    +cover-compare : cover-numeric-ratio
    demo-rust      : +cover

A prototype is no feature. Where a feature aggregates it, its INSTANCE
stands: '<owner>+<prototype>' as the owner's child, each member as
'<owner>+<member>' below it, each prototype aggregated within as
'<owner>+<prototype>' -- two-part names (P-c), the place from the
prototypes. The forest the faces read is the EXPANDED one; '+' lies
outside the id alphabet, so no written id collides with a composed one.
Also checked here: a prototype declared twice or aggregated undeclared, a
member or prototype under two prototypes, a member or prototype id that
is also a feature's, a circle among prototypes, and an owner reaching
one prototype twice (p-2).
______________________________________________________________________________
"""
import os
import re
from   dataclasses import dataclass, field

from .finder import FOREST_FILE_NAME

ID_RE = re.compile(r"[A-Za-z0-9_\-]+\Z")


class ForestFault(Exception):
    """The forest cannot be read. The text names the file, the line and
    what is wrong."""


def id_valid_f(text):
    """RETURN: True, 'text' is a feature id: base64url letters, one at
    least; False else -- an empty text, a dot, a colon, a slash, a blank
    or a glob character make it none."""
    return isinstance(text, str) and ID_RE.match(text) is not None


@dataclass(frozen=True)
class CForest:
    """What the forest states. 'children_of' holds every id that stands
    on a left side, its children in line order; 'parent_of' every child.
    'root_tuple' the ids standing as no child, in file order; 'id_set'
    every id of a line, either side; 'line_of' where an id first stands."""
    children_of: dict = field(default_factory=dict)   # id -> tuple of id
    parent_of:   dict = field(default_factory=dict)   # id -> id
    root_tuple:  tuple = ()
    id_set:      frozenset = frozenset()
    line_of:     dict = field(default_factory=dict)   # id -> line number
    file:        str = FOREST_FILE_NAME
    #  THE PROTOTYPES as declared: prototype id -> its right side, member
    #  ids and '+<prototype>' entries in line order; where each member and
    #  each inner prototype stands (id -> its prototype).
    prototype_db:  dict = field(default_factory=dict)
    member_of:     dict = field(default_factory=dict)

    def prototype_f(self, feature_id):
        """RETURN: True, 'feature_id' names a prototype or a member of one
        -- no feature, the stuff instances are made of; False else."""
        return feature_id in self.prototype_db or feature_id in self.member_of

    def subtree_tuple(self, feature_id):
        """RETURN: tuple of str, 'feature_id' and every id below it, the
        parent before its children, in line order."""
        result, stack = [], [feature_id]
        while stack:
            here = stack.pop()
            result.append(here)
            stack.extend(reversed(self.children_of.get(here, ())))
        return tuple(result)

    def ancestor_tuple(self, feature_id):
        """RETURN: tuple of str, the ids above 'feature_id', its root
        first; empty for a root or an id the forest does not hold."""
        result, here = [], self.parent_of.get(feature_id)
        while here is not None:
            result.append(here)
            here = self.parent_of.get(here)
        return tuple(reversed(result))


def read_forest(top):
    """
    RETURN: CForest, what 'top/hwut-feature-forest.csv' states
            None, no such file stands
    RAISES: ForestFault, where it cannot be read or states a fault.
    """
    path = os.path.join(top, FOREST_FILE_NAME)
    if not os.path.isfile(path): return None
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ForestFault("%s: cannot be read (%s)"
                          % (FOREST_FILE_NAME, error)) from error
    return forest_of_text(text, FOREST_FILE_NAME)


def _fault(file, line_n, message):
    """RETURN: ForestFault, 'FAULT: <file>:<line>: <message>'."""
    return ForestFault("FAULT: %s:%i: %s" % (file, line_n, message))


def forest_of_text(text, file=FOREST_FILE_NAME):
    """
    RETURN: CForest, what 'text' states as a forest, its prototypes
            expanded into instances (see the module purpose).
    RAISES: ForestFault, at the first fault in line order -- a line
            without ':', a left side or child that is no id, a line naming
            no child, a left side standing twice, a child standing twice
            or under two parents -- and, after every line is read, for a
            circle, and for what the prototypes may not do.
    """
    children_of, parent_of, line_of, order = {}, {}, {}, []
    prototype_db, member_of, use_list = {}, {}, []
    for line_n, line in enumerate(text.splitlines(), start=1):
        line = line.split("#", 1)[0].strip()
        if not line: continue
        if ":" not in line:
            raise _fault(file, line_n, "'%s' is no forest line -- "
                         "'<feature-id> : <child-id>, ...'" % line)
        head, _, tail = line.partition(":")
        head = head.strip()
        prototype_f = head.startswith("+")
        name = head[1:] if prototype_f else head
        if not id_valid_f(name):
            raise _fault(file, line_n, "'%s' is no feature id -- "
                         "'[A-Za-z0-9_-]+'" % head)
        child_list = [each.strip() for each in tail.split(",")]
        if child_list == [""]:
            raise _fault(file, line_n, "'%s' names no child -- a feature "
                         "with no children stands in no line's left side"
                         % head)
        if (name in children_of) != (name in prototype_db) \
           and prototype_f == (name in children_of):
            raise _fault(file, line_n, "'+%s' is a prototype and a feature "
                         "(line %i) -- one name, one thing"
                         % (name, line_of[name]))
        if name in children_of or name in prototype_db:
            raise _fault(file, line_n, "'%s' stands twice on a left side "
                         "(line %i) -- one line per feature"
                         % (head, line_of[name]))
        seen = set()
        for child in child_list:
            word = child[1:] if child.startswith("+") else child
            if not id_valid_f(word):
                raise _fault(file, line_n, "'%s' is no feature id -- "
                             "'[A-Za-z0-9_-]+'" % child)
            if child in seen:
                raise _fault(file, line_n, "'%s' stands twice under '%s'"
                             % (child, head))
            seen.add(child)
            if prototype_f:
                #  A MEMBER OR AN INNER PROTOTYPE HAS ONE PROTOTYPE (p-3).
                if word in member_of:
                    raise _fault(file, line_n, "'%s' stands under two "
                                 "prototypes: '+%s', '+%s' -- one"
                                 % (child, member_of[word], name))
                member_of[word] = name
            elif child.startswith("+"):
                use_list.append((name, word, line_n))
            else:
                if child in parent_of:
                    raise _fault(file, line_n, "'%s' stands under two "
                                 "parents: '%s', '%s' -- a feature has one "
                                 "parent" % (child, parent_of[child], name))
                parent_of[child] = name
        if prototype_f:
            prototype_db[name] = tuple(child_list)
            line_of.setdefault(name, line_n)
            continue
        children_of[name] = tuple(each for each in child_list
                                  if not each.startswith("+"))
        if not children_of[name]: del children_of[name]
        for each in [name] + [c for c in child_list if not c.startswith("+")]:
            if each not in line_of:
                line_of[each] = line_n
                order.append(each)
        if name not in line_of:
            line_of[name] = line_n
    _circle_checked(children_of, parent_of, line_of, file)
    _prototype_checked(prototype_db, member_of, set(order) | set(children_of),
                       line_of, file)
    #  THE INSTANCES, in the order the lines aggregate them.
    for owner, prototype, line_n in use_list:
        if prototype not in prototype_db:
            raise _fault(file, line_n, "'+%s' is aggregated and declared "
                         "nowhere -- '+%s : <member>, ...'"
                         % (prototype, prototype))
        if owner not in line_of:
            line_of[owner] = line_n
            order.append(owner)
        reached = set()
        _instance_expanded(owner, prototype, owner, prototype_db,
                           children_of, parent_of, line_of, order, line_n,
                           reached, file)
    return CForest(children_of, parent_of,
                   tuple(each for each in order if each not in parent_of),
                   frozenset(order), line_of, file, prototype_db, member_of)


def _instance_expanded(owner, prototype, parent, prototype_db, children_of,
                       parent_of, line_of, order, line_n, reached, file):
    """RETURN: None. The instance '<owner>+<prototype>' entered below
    'parent' -- its members and inner instances below it, recursively.
    RAISES: ForestFault where 'owner' reaches one prototype twice (p-2)."""
    name = "%s+%s" % (owner, prototype)
    if prototype in reached or name in parent_of:
        raise _fault(file, line_n, "'%s' reaches '+%s' twice -- one name, "
                     "one place" % (owner, prototype))
    reached.add(prototype)
    children_of[parent] = children_of.get(parent, ()) + (name,)
    parent_of[name] = parent
    line_of[name] = line_n
    order.append(name)
    for entry in prototype_db[prototype]:
        if entry.startswith("+"):
            _instance_expanded(owner, entry[1:], name, prototype_db,
                               children_of, parent_of, line_of, order,
                               line_n, reached, file)
            continue
        member = "%s+%s" % (owner, entry)
        children_of[name] = children_of.get(name, ()) + (member,)
        parent_of[member] = name
        line_of[member] = line_n
        order.append(member)


def _prototype_checked(prototype_db, member_of, feature_set, line_of, file):
    """RETURN: None. RAISES: ForestFault where an inner '+<id>' names no
    prototype, a member or prototype id is a feature's too, or the
    prototypes close a circle."""
    for name, entry_tuple in prototype_db.items():
        for entry in entry_tuple:
            word = entry[1:] if entry.startswith("+") else entry
            if entry.startswith("+") and word not in prototype_db:
                raise _fault(file, line_of[name], "'%s' is aggregated by "
                             "'+%s' and declared nowhere" % (entry, name))
            if not entry.startswith("+") and word in prototype_db:
                raise _fault(file, line_of[name], "'%s' is a prototype -- "
                             "aggregated as '+%s'" % (word, word))
            if word in feature_set:
                raise _fault(file, line_of[name], "'%s' is a feature and "
                             "stands in '+%s' -- a member's id is its own"
                             % (word, name))
        if name in feature_set:
            raise _fault(file, line_of[name], "'+%s' is a prototype and a "
                         "feature -- one name, one thing" % name)
    for start in prototype_db:
        path, here = [], start
        while here is not None:
            if here in path:
                circle = path[path.index(here):] + [here]
                raise _fault(file, line_of[here], "the prototypes close a "
                             "circle: %s" % " -> ".join(
                                 "+" + each for each in reversed(circle)))
            path.append(here)
            here = member_of.get(here)


def _circle_checked(children_of, parent_of, line_of, file):
    """RETURN: None. RAISES: ForestFault, naming the circle as it runs,
    where the parents of an id lead back to it."""
    done = set()
    for start in sorted(children_of, key=lambda each: line_of[each]):
        path, here = [], start
        while here is not None and here not in done:
            if here in path:
                circle = path[path.index(here):] + [here]
                raise _fault(file, line_of[here], "the forest closes a "
                             "circle: %s" % " -> ".join(reversed(circle)))
            path.append(here)
            here = parent_of.get(here)
        done.update(path)


def forest_text(children_of_list, head_comment=()):
    """RETURN: str, a forest file stating the lines of 'children_of_list'
    -- (id, tuple of child ids), in order -- after 'head_comment' (lines,
    '# ' prefixed), one line per feature, the colons aligned."""
    width = max([len(each) for each, _ in children_of_list] + [1])
    return "".join(["# %s\n" % each if each else "#\n"
                    for each in head_comment]
                   + ["%-*s : %s\n" % (width, each, ", ".join(child_tuple))
                      for each, child_tuple in children_of_list])
