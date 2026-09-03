#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE IMPORT GRAPH -- who depends on whom, at a stated DEPTH.

    adm/import_graph.py [<root>] [--depth=<n>] [--format=<name>]
                        [--exclude=<glob>]... [--shared[=<n>]]
                        [--check[=<file>]]

An IMPORT is a fact in the text: 'ast' reads it, and nothing here
guesses. That is the whole reason this tool is static while a CALL
graph could not be -- duck typing and dynamic dispatch mean a static
call graph invents edges, and an invented edge in an architecture
document is worse than no document.

THE DEPTH IS THE ZOOM. A module's component is its path, cut to
'depth' directories:

    --depth=1     engine -> services              the outer picture
    --depth=2     engine/orchestrator -> engine/compare
    --depth=0     module to module                everything

FORMATS: 'tree' (nested blocks and call arrows, for reading), 'svg'
(a picture, drawn HERE -- no graphviz, no browser, no dependency, AND
EDITABLE: every box is a group and every arrow an Inkscape connector
bound to two of them, so dragging a box re-routes its lines),
'dot' (graphviz), 'mermaid' (renders in a browser with nothing
installed), 'edges' (one edge per line, for grep and for diff).

'--shared[=<n>]' ANSWERS A DIFFERENT QUESTION: which NAMES do <n> or
more components import? A name that three components reach for is not
a part of whichever one happens to hold it -- it is CONTRACT MATERIAL,
and where it lives inside one of its own readers it holds a cycle
shut. This is the measurement behind 'a shared vocabulary belongs
where all its readers sit above it'.

'--check' READS A LAYERING DECLARATION and answers 0 where every edge
obeys it, 1 where one does not -- each violation named, both ends. The
architecture is then EXECUTABLE: drift is a red test, not a stale
document.

THE DECLARATION HAS TWO LINE SHAPES:

    <from> -> <to>      a permitted DIRECTION between two components,
                        judged at the '--depth' asked for
    SEALED <glob>       a component that IMPORTS NOTHING of this tree,
                        judged at MODULE depth and therefore true at
                        every '--depth'
    DOOR <module>       a component that NOTHING OUTSIDE MAY REACH
                        PAST: the module named is its one entrance, and
                        an import from outside of anything else beneath
                        its directory is a violation. Judged at MODULE
                        depth, like a seal.

A DIRECTION is about a pair and can only be read where both are named.
A SEAL and a DOOR are about one component, so a contract can be
enforced without declaring the whole tree at its depth. A seal says
NOTHING LEAVES; a door says NOTHING ENTERS BUT HERE.
______________________________________________________________________________
"""
import ast
import fnmatch
import os
import sys


#  Directories no import graph is about.
SKIP_TUPLE = ("__pycache__", ".git", "GOOD", "OUT", "TMP")

#  What a component is called when a module sits at the root itself.
ROOT_NAME = "."


def module_tuple(root, exclude_tuple=()):
    """
    RETURN: tuple[str], every Python module below 'root', as paths
            RELATIVE to it, '/'-separated, sorted.

    A path matching any glob of 'exclude_tuple' is left out, and so is
    anything under a directory of 'SKIP_TUPLE' -- a GOOD file is not a
    module, and a cache is not a fact about the tree.
    """
    found = []
    for where, dir_list, file_list in os.walk(root):
        dir_list[:] = [d for d in dir_list if d not in SKIP_TUPLE]
        for name in file_list:
            if not name.endswith(".py"): continue
            path = os.path.relpath(os.path.join(where, name), root)
            path = path.replace(os.sep, "/")
            if any(fnmatch.fnmatch(path, glob)
                   for glob in exclude_tuple): continue
            found.append(path)
    return tuple(sorted(found))


def imported_tuple(root, module_path):
    """
    RETURN: [0] tuple[str], every module this one imports, as DOTTED
                names -- 'vut.engine.orchestrator.plan.wish' and the
                like, absolute and relative alike, the relative ones
                resolved against the importing module's own package.
            [1] str | None, why the module could not be read, where it
                could not be: a syntax error names itself, and a
                module that cannot be parsed is REPORTED, never
                silently dropped.
    """
    whole = os.path.join(root, module_path)
    try:
        with open(whole, "r", encoding="utf-8") as file_handle:
            tree = ast.parse(file_handle.read(), filename=whole)
    except (SyntaxError, UnicodeDecodeError, OSError) as error:
        return (), "%s: %s" % (module_path, error)

    package = module_path.rsplit("/", 1)[0] if "/" in module_path \
              else ""
    name_list = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            name_list.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolved(node, package)
            #  'from X import Y' IS AMBIGUOUS, relative or absolute
            #  alike: 'Y' may be an ATTRIBUTE defined inside module X
            #  (the edge is to X, and 'resolved' alone is it), or 'Y'
            #  may be a SUBMODULE of package X (the edge is to X.Y,
            #  which 'resolved' alone never names -- 'from . import
            #  finder' and 'from vut.engine...exploration import
            #  selection' are the bare and the absolute shape of the
            #  same gap). Both candidates are offered per name; '_
            #  matched's tail search harmlessly finds nothing for
            #  whichever guess is wrong.
            if resolved:
                name_list.append(resolved)
                name_list.extend("%s.%s" % (resolved, alias.name)
                                 for alias in node.names)
    return tuple(name for name in name_list if name), None


def _resolved(node, package):
    """
    RETURN: str, the dotted name an 'from ... import ...' names --
            a relative one ('from .label import') resolved against
            'package', the importing module's own place.
            "" where the relative level climbs above the root, which
            no module of this tree does.
    """
    if not node.level:
        return node.module or ""
    part_list = package.split("/") if package else []
    climb     = node.level - 1
    if climb > len(part_list): return ""
    base = part_list[:len(part_list) - climb] if climb else part_list
    if node.module: base = base + node.module.split(".")
    return ".".join(base)


def component_of(module_path, depth):
    """
    RETURN: str, the component a module belongs to: its path cut to
            'depth' directories. Depth 0 means THE MODULE ITSELF --
            the finest zoom, where every module is its own component.

        depth 1   'engine/orchestrator/plan/wish.py'  -> 'engine'
        depth 2                                       -> 'engine/orchestrator'
        depth 0                                       -> the whole path
    """
    if depth <= 0: return module_path
    part_list = module_path.split("/")
    if len(part_list) == 1: return ROOT_NAME
    return "/".join(part_list[:min(depth, len(part_list) - 1)])


def edge_db_of(root, depth, exclude_tuple=()):
    """
    RETURN: [0] dict, component -> set of components it imports, SELF
                EXCLUDED: a component importing itself is not an edge,
                it is a component.
            [1] dict, component -> sorted tuple of its modules -- what
                the nested picture needs to show what a block holds.
            [2] tuple[str], every module that could not be read.

    A dotted import name is matched back to a module of this tree by
    its TAIL: 'vut.engine.plan.wish' finds 'engine/plan/wish.py'
    whatever the package is called on the importing side. An import of
    something outside the tree names no module here and is no edge --
    this graph is about THIS TREE's shape, and the standard library is
    not part of it.
    """
    path_tuple = module_tuple(root, exclude_tuple)
    by_dotted  = {}
    for path in path_tuple:
        dotted = path[:-len(".py")].replace("/", ".")
        by_dotted.setdefault(dotted, path)
        if dotted.endswith(".__init__"):
            by_dotted.setdefault(dotted[:-len(".__init__")], path)

    edge_db   = {}
    member_db = {}
    fault_list = []
    for path in path_tuple:
        here = component_of(path, depth)
        member_db.setdefault(here, []).append(path)
        edge_db.setdefault(here, set())
        name_tuple, fault = imported_tuple(root, path)
        if fault is not None: fault_list.append(fault)
        for dotted in name_tuple:
            target = _matched(dotted, by_dotted)
            if target is None: continue
            there = component_of(target, depth)
            if there != here: edge_db[here].add(there)
    return (edge_db,
            {name: tuple(sorted(part_list))
             for name, part_list in member_db.items()},
            tuple(fault_list))


def _matched(dotted, by_dotted):
    """
    RETURN: str | None, the module of this tree a dotted import names
            -- matched by the longest TAIL of the dotted name that is
            a module here, so the package's outer name does not have
            to be known.
    """
    part_list = dotted.split(".")
    for start in range(len(part_list)):
        tail = ".".join(part_list[start:])
        if tail in by_dotted: return by_dotted[tail]
    return None


def tree_text(edge_db, member_db, depth, module_max_n=6):
    """
    RETURN: str, the picture as NESTED BLOCKS AND CALL ARROWS: each
            component a block naming what it holds, and beneath it the
            components it imports.

        engine/orchestrator {
            9 module(s): adapter.py, determine.py, ...
            --> engine/bookkeeper
            --> engine/compare
        }

    A block importing nothing says so: 'imports nothing' is a fact
    about a component and one of the better ones.
    """
    line_list = []
    for name in sorted(edge_db):
        member_tuple = member_db.get(name, ())
        line_list.append("%s {" % name)
        if member_tuple:
            shown = ", ".join(part.rsplit("/", 1)[-1]
                              for part in member_tuple[:module_max_n])
            if len(member_tuple) > module_max_n:
                shown += ", ... (%d more)" \
                         % (len(member_tuple) - module_max_n)
            line_list.append("    %d module(s): %s"
                             % (len(member_tuple), shown))
        target_tuple = tuple(sorted(edge_db[name]))
        if not target_tuple:
            line_list.append("    imports nothing of this tree")
        for target in target_tuple:
            line_list.append("    --> %s" % target)
        line_list.append("}")
    return "\n".join(line_list)


def _rank_db(edge_db):
    """
    RETURN: dict, component -> its ROW in the picture: 0 for one that
            nothing imports, and one more than the deepest importer
            otherwise.

    A CYCLE HAS NO ORDER, so a component already being ranked keeps
    the rank it had -- the walk does not chase its own tail, and the
    picture stays drawable where the graph is not a DAG.
    """
    rank_db = {}
    busy    = set()

    def rank_of(name):
        if name in rank_db: return rank_db[name]
        if name in busy:    return 0        # a cycle: stop here
        busy.add(name)
        target_tuple = tuple(edge_db.get(name, ()))
        rank_db[name] = 1 + max((rank_of(t) for t in target_tuple),
                                default=-1)
        busy.discard(name)
        return rank_db[name]

    for name in sorted(edge_db): rank_of(name)
    return rank_db


def svg_text(edge_db, member_db):
    """
    RETURN: str, the graph as an SVG document -- DRAWN HERE, with no
            graphviz and no browser: a picture that needs a tool the
            reader has not got is a picture nobody looks at.

    The components are laid out in ROWS by rank, the importers above
    what they import, and a MUTUAL pair is drawn with a head at both
    ends -- the one thing a reader most wants to see.
    """
    rank_db = _rank_db(edge_db)
    by_rank = {}
    for name in sorted(edge_db):
        by_rank.setdefault(rank_db[name], []).append(name)
    deepest = max(by_rank) if by_rank else 0

    BOX_W, BOX_H, GAP_X, GAP_Y, PAD = 190, 46, 24, 96, 30
    widest = max((len(v) for v in by_rank.values()), default=1)
    width  = PAD * 2 + widest * BOX_W + (widest - 1) * GAP_X
    height = PAD * 2 + (deepest + 1) * BOX_H + deepest * GAP_Y

    place = {}
    for rank, name_list in by_rank.items():
        row_w = len(name_list) * BOX_W + (len(name_list) - 1) * GAP_X
        x0    = (width - row_w) / 2
        #  THE DEEPEST RANK SITS AT THE BOTTOM: what everything rests
        #  on is drawn where a reader looks for a foundation.
        y     = PAD + (deepest - rank) * (BOX_H + GAP_Y)
        for i, name in enumerate(sorted(name_list)):
            place[name] = (x0 + i * (BOX_W + GAP_X), y)

    #  THE PICTURE IS EDITABLE. Every box is a GROUP with an id, and
    #  every arrow is an INKSCAPE CONNECTOR bound to two of those ids
    #  -- so dragging a box in Inkscape re-routes its lines instead of
    #  leaving them behind. The 'd' attribute is drawn anyway, because
    #  a browser knows nothing of connectors and must still see a
    #  line; Inkscape recomputes it the moment anything moves.
    line_list = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/'
        'sodipodi-0.dtd" '
        'viewBox="0 0 %d %d" width="%d" height="%d" '
        'font-family="monospace">' % (width, height, width, height),
        ('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
         'markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
         '<path d="M1 1L9 5L1 9" fill="none" stroke="#555" '
         'stroke-width="1.6"/></marker></defs>'),
        '<rect width="100%" height="100%" fill="#fdfdfc"/>']

    drawn = set()
    for name in sorted(edge_db):
        for target in sorted(edge_db[name]):
            if target not in place: continue
            mutual_f = name in edge_db.get(target, ())
            if mutual_f and (target, name) in drawn: continue
            drawn.add((name, target))
            x0, y0 = place[name]
            x1, y1 = place[target]
            line_list.append(
                '<path d="M%.1f %.1f L%.1f %.1f" stroke="%s" '
                'stroke-width="%s" fill="none" marker-end="url(#a)"%s '
                'inkscape:connector-type="polyline" '
                'inkscape:connector-curvature="0" '
                'inkscape:connection-start="#%s" '
                'inkscape:connection-end="#%s"/>'
                % (x0 + BOX_W / 2, y0 + BOX_H, x1 + BOX_W / 2, y1,
                   "#b45309" if mutual_f else "#8a8a85",
                   "1.8" if mutual_f else "1.1",
                   ' marker-start="url(#a)"' if mutual_f else "",
                   _tag(name), _tag(target)))

    for name in sorted(place):
        x, y = place[name]
        count = len(member_db.get(name, ()))
        #  THE BOX AND ITS WORDS ARE ONE GROUP, so dragging takes the
        #  label along -- and a connector may bind to a group.
        #  'connector-avoid' makes the lines route AROUND the boxes
        #  rather than through them.
        line_list.append(
            '<g id="%s" inkscape:label="%s" '
            'inkscape:connector-avoid="true">' % (_tag(name),
                                                  _escaped(name)))
        line_list.append(
            '<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="7" '
            'fill="#ffffff" stroke="#333" stroke-width="1"/>'
            % (x, y, BOX_W, BOX_H))
        line_list.append(
            '<text x="%.1f" y="%.1f" text-anchor="middle" '
            'font-size="12" fill="#111">%s</text>'
            % (x + BOX_W / 2, y + 19, _escaped(name)))
        line_list.append(
            '<text x="%.1f" y="%.1f" text-anchor="middle" '
            'font-size="10" fill="#777">%d module(s)</text>'
            % (x + BOX_W / 2, y + 35, count))
        line_list.append("</g>")
    line_list.append("</svg>")
    return "\n".join(line_list)


def _tag(name):
    """
    RETURN: str, the component's name as an XML id may carry it --
            what a connector binds to, and what a person sees in
            Inkscape's XML editor.
    """
    fresh = name.replace("/", "_").replace(".", "_").replace("-", "_")
    return "n_%s" % fresh


def _escaped(text):
    """
    RETURN: str, the text as SVG may carry it.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;") \
               .replace(">", "&gt;")


def shared_text(root, depth, exclude_tuple, least_n):
    """
    RETURN: str, every NAME that 'least_n' or more components import,
            with the components that import it -- most-shared first,
            then by name.

    CONTRACT MATERIAL. A name three components reach for is no part of
    whichever one happens to hold it, and where it lives inside one of
    its own readers it holds a cycle shut. What this answers is not
    'is there a cycle' but 'WHAT WOULD MOVING ONE NAME DO'.
    """
    path_tuple = module_tuple(root, exclude_tuple)
    by_dotted  = {}
    for path in path_tuple:
        dotted = path[:-len(".py")].replace("/", ".")
        by_dotted.setdefault(dotted, path)
        if dotted.endswith(".__init__"):
            by_dotted.setdefault(dotted[:-len(".__init__")], path)

    reader_db = {}          # name -> set of components importing it
    home_db   = {}          # name -> component it is imported FROM
    for path in path_tuple:
        here = component_of(path, depth)
        try:
            with open(os.path.join(root, path), "r",
                         encoding="utf-8") as file_handle:
                tree = ast.parse(file_handle.read())
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        package = path.rsplit("/", 1)[0] if "/" in path else ""
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom): continue
            dotted = _resolved(node, package)
            target = _matched(dotted, by_dotted) if dotted else None
            if target is None: continue
            there = component_of(target, depth)
            if there == here: continue
            for alias in node.names:
                reader_db.setdefault(alias.name, set()).add(here)
                home_db[alias.name] = there

    line_list = []
    for name, reader_set in sorted(
            reader_db.items(),
            key=lambda pair: (-len(pair[1]), pair[0])):
        if len(reader_set) < least_n: continue
        line_list.append("%-28s from %-24s read by %d: %s"
                         % (name, home_db.get(name, "?"),
                            len(reader_set),
                            ", ".join(sorted(reader_set))))
    if not line_list:
        return "no name is imported by %d or more components" % least_n
    return "\n".join(line_list)


def dot_text(edge_db):
    """
    RETURN: str, the graph in graphviz's language.
    """
    line_list = ["digraph imports {", "    rankdir=LR;",
                 '    node [shape=box, fontname="monospace"];']
    for name in sorted(edge_db):
        for target in sorted(edge_db[name]):
            line_list.append('    "%s" -> "%s";' % (name, target))
    line_list.append("}")
    return "\n".join(line_list)


def mermaid_text(edge_db):
    """
    RETURN: str, the graph in mermaid's language -- which renders in a
            browser and in most markdown viewers WITH NOTHING
            INSTALLED, and so is the format that works on the morning
            graphviz does not.
    """
    def tag(name):
        return name.replace("/", "_").replace(".", "_").replace("-", "_")

    line_list = ["graph LR"]
    for name in sorted(edge_db):
        line_list.append('    %s["%s"]' % (tag(name), name))
    for name in sorted(edge_db):
        for target in sorted(edge_db[name]):
            line_list.append("    %s --> %s" % (tag(name), tag(target)))
    return "\n".join(line_list)


def edges_text(edge_db):
    """
    RETURN: str, one edge per line, 'A -> B', sorted -- the form that
            greps, diffs, and makes a GOOD file worth reading.
    """
    return "\n".join("%s -> %s" % (name, target)
                     for name in sorted(edge_db)
                     for target in sorted(edge_db[name]))


def violation_tuple(edge_db, rule_tuple):
    """
    RETURN: tuple[str], every edge that no rule permits, each naming
            both ends.

    A RULE IS A PERMITTED DIRECTION, '<from-glob> -> <to-glob>'. An
    edge permitted by no rule is a violation: the declaration says
    what MAY happen, and everything else is drift.
    """
    found = []
    for name in sorted(edge_db):
        for target in sorted(edge_db[name]):
            if any(fnmatch.fnmatch(name, left)
                   and fnmatch.fnmatch(target, right)
                   for left, right in rule_tuple): continue
            found.append("%s -> %s" % (name, target))
    return tuple(found)


def rule_tuple_of(path):
    """
    RETURN: [0] tuple[(str, str)], the permitted DIRECTIONS -- lines
                reading '<from> -> <to>', globs allowed either side.
            [1] tuple[str], the SEALED components -- lines reading
                'SEALED <glob>'.
            [2] tuple[str], the DOOR modules -- lines reading
                'DOOR <module>', each the one entrance of the component
                that holds it.

    '#' to end of line is a comment; blank lines are nothing.

    Raises ValueError, naming file and line, where a line is neither
    -- a layering nobody can read is a layering nobody enforces.

    TWO LINE SHAPES, BECAUSE THERE ARE TWO KINDS OF LAW. A DIRECTION
    is about a PAIR and can only be judged at the depth the pair is
    named at. 'SEALED' is about ONE COMPONENT and is judged at MODULE
    depth, so it holds however coarsely the rest is declared -- which
    is what a contract needs, its whole claim being 'nothing leaves
    here'.
    """
    rule_list  = []
    sealed_list = []
    door_list   = []
    with open(path, "r", encoding="utf-8") as file_handle:
        for number, line in enumerate(file_handle, start=1):
            text = line.split("#", 1)[0].strip()
            if not text: continue
            if text.startswith("SEALED "):
                sealed_list.append(text[len("SEALED "):].strip())
                continue
            if text.startswith("DOOR "):
                door_list.append(text[len("DOOR "):].strip())
                continue
            left, arrow, right = text.partition("->")
            if not arrow:
                raise ValueError("%s:%d: a rule reads "
                                 "'<from> -> <to>', 'SEALED <glob>' "
                                 "or 'DOOR <module>', and '%s' is "
                                 "none of them"
                                 % (path, number, text))
            rule_list.append((left.strip(), right.strip()))
    return tuple(rule_list), tuple(sealed_list), tuple(door_list)


def seal_violation_tuple(root, exclude_tuple, sealed_tuple):
    """
    RETURN: tuple[str], every import by which a SEALED component
            reaches out of itself -- the importing MODULE named, and
            the module it reached for.

    A SEALED COMPONENT IMPORTS NOTHING OF THIS TREE. That is the whole
    property of a contract: every party sits above it, so no party can
    be made to wait on another, and a shape stored there can never
    hold a cycle shut.

    JUDGED AT MODULE DEPTH, always. A direction between two components
    can only be read at the depth those components are named at; a
    seal is about ONE component and needs no depth at all, so it holds
    whatever '--depth' the rest of the declaration was written for.
    """
    if not sealed_tuple: return ()
    path_tuple = module_tuple(root, exclude_tuple)
    by_dotted  = {}
    for path in path_tuple:
        dotted = path[:-len(".py")].replace("/", ".")
        by_dotted.setdefault(dotted, path)
        if dotted.endswith(".__init__"):
            by_dotted.setdefault(dotted[:-len(".__init__")], path)

    def sealed_f(path):
        where = path.rsplit("/", 1)[0] if "/" in path else ""
        return any(fnmatch.fnmatch(where, glob)
                   for glob in sealed_tuple)

    found = []
    for path in path_tuple:
        if not sealed_f(path):    continue
        name_tuple, _ = imported_tuple(root, path)
        for dotted in name_tuple:
            target = _matched(dotted, by_dotted)
            if target is None:    continue
            #  A SEAL DOES NOT FORBID A COMPONENT ITS OWN MEMBERS: the
            #  contract's modules may speak among themselves, and the
            #  pair that results is INSIDE the seal, where nothing
            #  outside can be made to wait on it.
            if sealed_f(target):  continue
            found.append("%s -> %s" % (path, target))
    return tuple(sorted(found))


def door_violation_tuple(root, exclude_tuple, door_tuple):
    """
    RETURN: tuple[str], every import by which a module OUTSIDE a
            component reaches past its door -- the importing module
            named, and the module it reached for.

    A DOOR IS THE ONE ENTRANCE. 'DOOR engine/compare/api' says: a
    module outside 'engine/compare' may import 'engine/compare/api'
    and nothing else beneath 'engine/compare'. The component's own
    modules are unaffected -- a door is for callers, and a component's
    parts are not callers.

    JUDGED AT MODULE DEPTH, like a seal: the claim is about one
    component and needs no depth at all.
    """
    if not door_tuple: return ()
    path_tuple = module_tuple(root, exclude_tuple)
    by_dotted  = {}
    for path in path_tuple:
        dotted = path[:-len(".py")].replace("/", ".")
        by_dotted.setdefault(dotted, path)
        if dotted.endswith(".__init__"):
            by_dotted.setdefault(dotted[:-len(".__init__")], path)

    #  The door's own directory is the wall it stands in.
    wall_db = {door: door.rsplit("/", 1)[0] for door in door_tuple}

    found = []
    for path in path_tuple:
        name_tuple, _ = imported_tuple(root, path)
        for dotted in name_tuple:
            target = _matched(dotted, by_dotted)
            if target is None: continue
            stem = target[:-len(".py")] if target.endswith(".py") else target
            for door, wall in wall_db.items():
                if not stem.startswith(wall + "/"): continue
                if stem == door:                    continue
                #  INSIDE THE WALL IS NOT A CALLER.
                if path.startswith(wall + "/"):     continue
                found.append("%s -> %s (past the door '%s')"
                             % (path, target, door))
    return tuple(sorted(found))


def main(argv=None, write=None):
    """
    RETURN: int, 0 where the graph was produced (and, under '--check',
            every edge obeyed the declaration); 1 where an edge did
            not, or a module could not be read; 2 where the command
            line cannot be read.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        write(__doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip())
        return 0

    root      = "."
    depth     = 1
    form      = "tree"
    check     = None
    shared_n  = None
    exclude   = []
    for argument in argv:
        if   argument.startswith("--depth="):
            depth = int(argument[len("--depth="):])
        elif argument.startswith("--format="):
            form = argument[len("--format="):]
        elif argument.startswith("--exclude="):
            exclude.append(argument[len("--exclude="):])
        elif argument == "--shared":
            shared_n = 3
        elif argument.startswith("--shared="):
            shared_n = int(argument[len("--shared="):])
        elif argument == "--check":
            check = "adm/LAYERING.txt"
        elif argument.startswith("--check="):
            check = argument[len("--check="):]
        elif argument.startswith("-"):
            write("REFUSED: 'import_graph' does not take: %s"
                  % argument)
            return 2
        else:
            root = argument

    if form not in ("tree", "svg", "dot", "mermaid", "edges"):
        write("REFUSED: no format '%s'; there is: tree, svg, dot, "
              "mermaid, edges" % form)
        return 2

    if shared_n is not None:
        write(shared_text(root, depth, tuple(exclude), shared_n))
        return 0

    edge_db, member_db, fault_tuple = edge_db_of(root, depth,
                                                 tuple(exclude))
    for fault in fault_tuple: write("FAULT: %s" % fault)

    if check is not None:
        try:
            rule_tuple, sealed_tuple, door_tuple = rule_tuple_of(check)
        except ValueError as error:
            write("REFUSED: %s" % error)
            return 2
        except OSError:
            write("REFUSED: no layering declaration at '%s' -- "
                  "'--check' needs one, and this tool writes none"
                  % check)
            return 2
        violation = violation_tuple(edge_db, rule_tuple)
        broken    = seal_violation_tuple(root, tuple(exclude),
                                         sealed_tuple)
        entered   = door_violation_tuple(root, tuple(exclude),
                                         door_tuple)
        if not violation and not broken and not entered:
            write("LAYERING: every edge obeys '%s' (%d component(s), "
                  "%d edge(s))" % (check, len(edge_db),
                                   sum(len(v) for v in edge_db.values())))
            if sealed_tuple:
                write("SEALED: %s -- nothing leaves"
                      % ", ".join(sealed_tuple))
            if door_tuple:
                write("DOORS: %s -- nothing enters but here"
                      % ", ".join(door_tuple))
            return 1 if fault_tuple else 0
        if violation:
            write("LAYERING VIOLATED -- %d edge(s) no rule permits:"
                  % len(violation))
            for text in violation: write("    %s" % text)
        if broken:
            write("SEAL BROKEN -- %d import(s) leave a sealed "
                  "component:" % len(broken))
            for text in broken: write("    %s" % text)
        if entered:
            write("DOOR PASSED -- %d import(s) reach into a component "
                  "past its door:" % len(entered))
            for text in entered: write("    %s" % text)
        return 1

    write({"tree":    lambda: tree_text(edge_db, member_db, depth),
           "svg":     lambda: svg_text(edge_db, member_db),
           "dot":     lambda: dot_text(edge_db),
           "mermaid": lambda: mermaid_text(edge_db),
           "edges":   lambda: edges_text(edge_db)}[form]())
    return 1 if fault_tuple else 0


if __name__ == "__main__":
    sys.exit(main())
