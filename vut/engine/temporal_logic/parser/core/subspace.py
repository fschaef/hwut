"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
================================================================================
                 GRAMMAR SUBSPACES AND PATH NAMESPACES (D-20, D-21)
================================================================================

A grammar VALUE is normally a pattern. It may instead be a SUBSPACE: a dict
whose TOP key holds the rule's own pattern and whose other keys are MEMBER rules
of that subspace.

    "algebr": {
        TOP:       ("<shift>",),         # algebr's own pattern
        "shift":   ("<add>", ...),       # algebr/shift -- short name, local
        "add":     ("<mul>", ...),
        ...
    }

PATH NAMESPACE (D-21). A subspace is a NAMESPACE node in a tree of rule names.
Every rule has a QUALIFIED NAME -- its path joined by '/': 'algebr/shift',
'cond/xor'. The flat rule map the engine compiles is keyed by these qualified
names; a root rule keeps its bare name ('top-level'). Two consequences:

  * NAME REUSE. Short names need only be distinct WITHIN a subspace, so the
    category prefix may drop ('cond-xor' -> 'cond/xor', written 'xor' inside the
    subspace). 'algebr/shift' and a hypothetical 'cond/shift' coexist.

  * REACH BY PATH FROM ANYWHERE. A reference '<algebr/shift>' resolves to that
    qualified name from any scope. A BARE reference '<xor>' is SCOPE-LOCAL: it
    resolves against the writing rule's subspace first, then walks up the
    enclosing subspaces, then the root. So 'xor' inside 'cond' finds 'cond/xor'
    with no prefix, while the same bare 'xor' written at the root does not see it
    -- privacy is now a RESOLUTION property, not a separate wall. To reach a
    subspace member from outside, spell its path.

Subspaces NEST arbitrarily; a path has arbitrary depth ('a/b/leaf').

WHAT THIS MODULE DOES (the engine compiles the flat qualified-named map)

  flatten()   lowers a possibly-nested grammar to the flat QUALIFIED-named rule
              map plus a scope map (qualified name -> path tuple). Qualified
              names are globally unique by construction (the path disambiguates);
              a literal duplicate qualified name is a load error.

  resolve()   the scope-aware resolver: given a reference name (bare or
              path-qualified) and the scope it is written in, returns the
              qualified name it binds to, or None if unresolved. The engine calls
              this when compiling each reference.

  subspace_report()  the namespace tree, for review.
================================================================================
"""
from .combinators import TOP, OR, _Combinator


SEP = "/"


# --- reference extraction ---------------------------------------------------

def _ref_name(element):
    """RETURN: str | None, the (possibly path-qualified) rule name a '<...>' /
               '<...(role)>' string names; None for a non-reference.

    Strips the angle brackets, then a parenthesised role suffix. The returned
    name may contain SEP (a path-qualified reference like 'algebr/shift'); the
    resolver, not this function, interprets the path.
    """
    if not isinstance(element, str):
        return None
    if len(element) > 2 and element[0] == "<" and element[-1] == ">":
        name = element[1:-1]
        if name.endswith(")") and "(" in name:
            name = name.partition("(")[0]
        return name
    return None


def references_of(pattern):
    """RETURN: set[str], every reference name (bare or qualified) a raw authored
               pattern contains.

    Walks the authored form (tuples, lists, combinators, strings) BEFORE
    compilation. Terminals and bare-string keywords contribute nothing.
    """
    out = set()

    def walk(node):
        if isinstance(node, _Combinator):
            for child in node.children:
                walk(child)
        elif isinstance(node, (tuple, list)):
            for child in node:
                walk(child)
        elif node is OR:
            pass
        else:
            name = _ref_name(node)
            if name is not None:
                out.add(name)

    walk(pattern)
    return out


# --- flattening -------------------------------------------------------------

class SubspaceError(Exception):
    """Raised when a subspace is structurally malformed (D-20/D-21).

    A TOP-dict without a TOP key, or two rules producing the same QUALIFIED name
    (only possible by a literal duplicate, since the path disambiguates). All
    faults are collected and raised together, each naming the rule. Encapsulation
    is no longer a separate gate -- it is a resolution property (a bare name does
    not resolve outside its scope); see resolve().
    """
    def __init__(self, violations):
        super().__init__("%d subspace violation(s)" % len(violations))
        self.violations = violations


def _qualify(path, name):
    """RETURN: str, the qualified name for 'name' at subspace 'path'."""
    return SEP.join(path + (name,)) if path else name


def flatten(grammar):
    """RETURN: (flat, scope_of), the grammar lowered to the flat QUALIFIED-named
               rule map plus each rule's BODY-RESOLUTION scope.

    'flat' maps every rule's QUALIFIED name (root rules keep their bare name) to
    its pattern; 'scope_of' maps that qualified name to the path its BODY resolves
    references at -- for a member, its own containing path; for a subspace's TOP
    rule, the member path (so the TOP reaches its members though its name lives
    one level up). Subspaces nest arbitrarily. Raises SubspaceError on a TOP-dict
    missing its TOP key or a literal duplicate qualified name.
    """
    flat = {}
    scope_of = {}
    violations = []

    def place(qname, pattern, path):
        if qname in flat:
            violations.append("rule %r defined twice" % qname)
            return
        flat[qname] = pattern
        scope_of[qname] = path

    def descend(name, value, path):
        if isinstance(value, dict):
            qname = _qualify(path, name)
            member_path = path + (name,)
            if TOP not in value:
                violations.append("subspace %r has no TOP key" % qname)
            else:
                # The TOP rule's name lives at 'path', but its BODY references the
                # subspace's members -- so it resolves at 'member_path', the same
                # scope its members resolve at. scope_of is the body-resolution
                # scope, not the name's location.
                place(qname, value[TOP], member_path)
            for k, v in value.items():
                if k is not TOP:
                    descend(k, v, member_path)
        else:
            place(_qualify(path, name), value, path)

    for name, value in grammar.items():
        descend(name, value, ())

    if violations:
        raise SubspaceError(sorted(set(violations)))
    return flat, scope_of


# --- scope-aware resolution -------------------------------------------------

def resolve(ref_name, from_path, flat):
    """RETURN: str | None, the qualified name 'ref_name' binds to when written in
               a rule whose subspace path is 'from_path', or None if unresolved.

    A PATH-QUALIFIED reference (containing SEP) is absolute: it binds to that
    exact qualified name if it exists. A BARE reference resolves SCOPE-LOCAL:
    'from_path' first, then each shorter enclosing path, then the root -- the
    first scope that defines a rule of that name wins. So a bare name reaches a
    sibling member or a public ancestor, but never a private member of an
    unrelated subspace; reaching one requires its path.
    """
    if SEP in ref_name:
        return ref_name if ref_name in flat else None
    path = from_path
    while True:
        candidate = _qualify(path, ref_name)
        if candidate in flat:
            return candidate
        if not path:
            return None
        path = path[:-1]


# --- report -----------------------------------------------------------------

def subspace_report(flat, scope_of):
    """RETURN: str, the namespace tree of qualified rule names, for review (D-21).

    One block per subspace path, root first; each lists its directly-owned rules
    by qualified name. The path is derived from the qualified NAME structure (the
    SEP-joined segments before the last), independent of the body-resolution
    'scope_of' map. Telegraphic.
    """
    by_path = {}
    for qname in flat:
        segments = qname.split(SEP)
        path = tuple(segments[:-1])
        by_path.setdefault(path, []).append(qname)
    lines = []
    for path in sorted(by_path, key=lambda p: (len(p), p)):
        label = SEP.join(path) if path else "<root>"
        lines.append("subspace %s  (%d rule(s))" % (label, len(by_path[path])))
        for qname in sorted(by_path[path]):
            lines.append("    %s" % qname)
    return "\n".join(lines)
