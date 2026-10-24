"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

A SYSTEM OF PYPE SCRIPTS (the book's RQ-2, ruled 2026-10-24): a file with
the extension '.pypes' wires scripts into a directed graph, and
'hwut.pype SYSTEM.pypes' runs them as ONE filter over stdin.

    --> a.pype              a reads stdin
    --> q.pype              q reads stdin too
    a.pype --> b.pype       a pipes to b
    : --> c.pype            ':' = the previous line's source (here: a)
    q.pype --> b.pype       fan-in: b reads a and q

One edge per line; '#' starts a comment, blank lines are free. A script
path is read relative to the '.pypes' file; one path is one script, however
often it is named.

THE FLOW. What a script prints -- 'print(...)', '=> flush;' -- goes to its
successors, and ONLY there; a script with no successor (a SINK) writes to
stdout. The order is deterministic: a stdin line goes to the sources in
the order their '-->' lines stand; a line a script emits is handed on at
once, DEPTH-FIRST, to its successors in the order their edges stand -- it
has passed through the whole system below before the script's next
statement runs.

THE ENDS. A script receives '<eof>' once every one of its predecessors
has ended (stdin counts as one); its end, in turn, counts for its
successors. A '<hwut-end>' line any script emits is SWALLOWED; the system
prints exactly one, at the very end. Scripts start sinks first, so what a
'<bof>' or '<entry>' prints finds its successors ready.

THE REFUSALS, when the file is read: an edge that cannot be read, ':'
with no previous line, a script that does not parse, a cycle, an edge
written twice, a script that nothing feeds, an empty system.

TICKS ('tick:', RQ-3) run in each script on its own clock; they stop at
the end of stdin.

'hwut.pype --draw SYSTEM.pypes' draws the graph as ASCII; '--draw --svg'
as SVG, on stdout.
______________________________________________________________________________
"""
import os
import re
import sys

#  THE INTERPRETER'S MODULE, bound by 'bind' -- not imported: 'hwut_pype'
#  also runs as a plain script ('__main__'), and its PypeError must be
#  the one this module raises.
_core = None


def bind(core_module):
    """RETURN: None. Makes 'core_module' (hwut_pype, however it was
                     loaded) the interpreter this module drives."""
    global _core
    _core = core_module

SYSTEM_EXTENSION = ".pypes"
STDIN_NAME       = "<stdin>"
STDOUT_NAME      = "<stdout>"
END_TOKEN        = "<hwut-end>"

RE_EDGE = re.compile(r"^(\S*)\s*-->\s*(\S+)\s*$")


def system_f(path):
    """RETURN: bool, True where 'path' names a system file ('.pypes')."""
    return path.endswith(SYSTEM_EXTENSION)


class CSystem:
    """RETURN: --. A system as read: its scripts and its edges.

    'node_list'  the script names, in the order first named
    'edge_list'  (source, target) pairs in the order written; a source
                 is a script name or STDIN_NAME
    'path_db'    script name -> path of the script file
    'where_db'   script name -> 'file:line' where it was first named
    """
    def __init__(self, file_name):
        self.file_name = file_name
        self.node_list = []
        self.edge_list = []
        self.path_db   = {}
        self.where_db  = {}

    def successor_list(self, name):
        """RETURN: list, the targets of 'name', in edge order."""
        return [t for s, t in self.edge_list if s == name]

    def predecessor_list(self, name):
        """RETURN: list, the sources of 'name' (STDIN_NAME included), in
                         edge order."""
        return [s for s, t in self.edge_list if t == name]

    def source_list(self):
        """RETURN: list, the scripts that read stdin, in edge order."""
        return self.successor_list(STDIN_NAME)

    def depth_db(self):
        """RETURN: dict, script name -> the length of the longest path
                         from stdin to it (a source: 1) -- the column a
                         drawing places it in.
        """
        depth = {}
        for name in self.topological_list():
            depth[name] = 1 + max([depth.get(p, 0)
                                   for p in self.predecessor_list(name)])
        return depth

    def topological_list(self):
        """RETURN: list, every script after all its predecessors -- among
                         equals in the order first named.
        """
        pending = dict((n, len([p for p in self.predecessor_list(n)
                                if p != STDIN_NAME]))
                       for n in self.node_list)
        done = []
        while len(done) < len(self.node_list):
            ready = [n for n in self.node_list
                     if n not in done and pending[n] == 0]
            if not ready: break                          # a cycle: read() refuses
            done.append(ready[0])
            for t in self.successor_list(ready[0]):
                pending[t] -= 1
        return done


def read(file_name):
    """RETURN: CSystem, the system the file describes if success.
               Raises PypeError naming 'file:line', else -- see the
               module's REFUSALS.
    """
    with open(file_name, "r") as fh:
        line_list = fh.read().splitlines()
    system   = CSystem(file_name)
    base_dir = os.path.dirname(file_name)        # paths said as the user said them
    previous = None
    seen     = set()

    def node_of(word, where):
        path = os.path.normpath(os.path.join(base_dir, word))
        for name, known in system.path_db.items():
            if known == path: return name
        system.node_list.append(word)
        system.path_db[word]  = path
        system.where_db[word] = where
        return word

    for i, raw in enumerate(line_list):
        where = "%s:%d" % (file_name, i + 1)
        text  = raw.split("#", 1)[0].strip()
        if not text: continue
        match = RE_EDGE.match(text)
        if match is None:
            raise _core.PypeError("%s: an edge reads '[<source>|:] --> <script>', "
                            "not '%s'" % (where, text))
        left, right = match.group(1), match.group(2)
        if   left == "":  source = STDIN_NAME
        elif left == ":":
            if previous is None:
                raise _core.PypeError("%s: ':' stands for the previous line's "
                                "source, and there is none" % where)
            source = previous
        else:             source = node_of(left, where)
        target = node_of(right, where)
        if (source, target) in seen:
            raise _core.PypeError("%s: the edge '%s --> %s' stands twice"
                            % (where, source, target))
        seen.add((source, target))
        system.edge_list.append((source, target))
        previous = source

    if not system.edge_list:
        raise _core.PypeError("%s: the system holds no edge" % file_name)
    for name in system.node_list:
        if not system.predecessor_list(name):
            raise _core.PypeError("%s: nothing feeds '%s' -- '--> %s' reads stdin"
                            % (system.where_db[name], name, name))
    if len(system.topological_list()) < len(system.node_list):
        rest = [n for n in system.node_list
                if n not in system.topological_list()]
        raise _core.PypeError("%s: the system holds a cycle through %s"
                        % (file_name, ", ".join("'%s'" % n for n in rest)))
    return system


class _Writer:
    """RETURN: --. What 'sys.stdout' is while a script of a system runs:
                   it cuts the text into lines and hands each to its
                   node, at once.
    """
    def __init__(self, node):
        self._node   = node
        self._buffer = ""

    def write(self, text):
        """RETURN: int, the length of 'text'; every complete line handed
                        on (depth-first) before the return."""
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._node.emit(line)
        return len(text)

    def flush(self):
        """RETURN: None. Lines are handed on as they complete; nothing
                         waits."""
        return None

    def rest(self):
        """RETURN: None. Hands on what follows the last newline, if
                         anything -- at the script's end."""
        if self._buffer:
            line, self._buffer = self._buffer, ""
            self._node.emit(line)


class _Node:
    """RETURN: --. One script of a running system: its interpreter, its
                   successors, its output writer, and how many of its
                   predecessors are still running.
    """
    def __init__(self, name, interpreter, tick_list, out):
        self.name           = name
        self.interpreter    = interpreter
        self.tick_list      = tick_list
        self.successor_list = []
        self.pending_n      = 0
        self.ended_f        = False
        self.writer         = _Writer(self)
        self._out           = out

    def call(self, function, *argument_tuple):
        """RETURN: what 'function(*argument_tuple)' returns, run with
                   'sys.stdout' bound to this script's writer -- and
                   restored afterwards, whatever happens."""
        saved, sys.stdout = sys.stdout, self.writer
        try:
            return function(*argument_tuple)
        finally:
            sys.stdout = saved

    def emit(self, line):
        """RETURN: None. A line this script printed: swallowed where it is
                         '<hwut-end>'; else given to every successor in
                         edge order, or -- a sink -- to stdout."""
        if line.strip() == END_TOKEN: return
        if not self.successor_list:
            self._out.write(line + "\n")
            return
        for successor in self.successor_list:
            successor.receive(line)

    def receive(self, line):
        """RETURN: None. One line from a predecessor, dispatched."""
        self.call(self.interpreter.take, line)

    def tick(self, text):
        """RETURN: None. One tick of this script (RQ-3), dispatched."""
        self.call(self.interpreter.tick, text)

    def end(self):
        """RETURN: None. '<eof>' of this script -- what it prints flows
                         on -- then, depth-first, the end of every
                         successor whose last predecessor this was."""
        self.call(self.interpreter.finish)
        self.writer.rest()
        self.ended_f = True
        for successor in self.successor_list:
            successor.pending_n -= 1
            if successor.pending_n == 0:
                successor.end()


def built(system, search_dir_list=None, trace_style=None, out=None):
    """RETURN: dict, script name -> _Node, every script parsed and wired,
                     if success.
               Raises PypeError naming the script, else (a parse error).
    """
    out     = out if out is not None else sys.stdout
    node_db = {}
    for name in system.node_list:
        path = system.path_db[name]
        try:
            with open(path, "r") as fh:
                source_txt = fh.read()
        except (IOError, OSError) as error:
            raise _core.PypeError("%s: the script '%s' cannot be read: %s"
                            % (system.where_db[name], name, error))
        source_db = {}
        tick_list = []
        mode_db, start_mode_name = _core.parse(source_txt, path,
                                         search_dir_list=search_dir_list,
                                         source_db=source_db,
                                         tick_list=tick_list)
        interpreter = _core.Interpreter(mode_db, start_mode_name, path,
                                  trace_style=trace_style,
                                  source_db=source_db, tick_list=tick_list)
        interpreter.input_name = name
        node_db[name] = _Node(name, interpreter, tick_list, out)
    for name in system.node_list:
        node = node_db[name]
        node.successor_list = [node_db[t]
                               for t in system.successor_list(name)]
        node.pending_n      = len(system.predecessor_list(name))
    return node_db


def run(system, line_iterable, search_dir_list=None, trace_style=None,
        out=None):
    """RETURN: None, once the system has run over 'line_iterable': every
                     script started (sinks first), every line given to
                     the sources, every script ended in turn, and one
                     '<hwut-end>' written.
               Raises PypeError, else.
    """
    out     = out if out is not None else sys.stdout
    node_db = built(system, search_dir_list, trace_style, out)
    source_list = [node_db[n] for n in system.source_list()]
    start_time  = _core._monotonic()
    for name in reversed(system.topological_list()):
        node_db[name].call(node_db[name].interpreter.start)
        node_db[name].interpreter.start_time = start_time

    def take(line):
        for node in source_list:
            node.receive(line)

    tick_entry_list = [(tick, node_db[name].tick)
                       for name in system.node_list
                       for tick in node_db[name].tick_list]
    _core.drive(line_iterable, take, tick_entry_list, start_time)
    for node in source_list:
        node.pending_n -= 1
        if node.pending_n == 0: node.end()
    out.write(END_TOKEN + "\n")
    out.flush()


# -- THE DRAWING ---------------------------------------------------------------
def drawn_ascii(system):
    """RETURN: str, the system as an ASCII tree from stdin: each script
                    below its first source; met again (fan-in), it is
                    named with '(^ above)' and not repeated; a sink ends
                    in '--> <stdout>'.

        <stdin>
         +--> a.pype
         |     +--> b.pype --> <stdout>
         |     +--> c.pype --> <stdout>
         +--> q.pype
               +--> b.pype  (^ above)
    """
    line_list = [STDIN_NAME]
    shown_set = set()

    def walk(name, prefix, last_f):
        branch = prefix + (" +--> ")
        if name in shown_set:
            line_list.append(branch + name + "  (^ above)")
            return
        shown_set.add(name)
        successor_list = system.successor_list(name)
        line_list.append(branch + name
                         + ("" if successor_list else " --> " + STDOUT_NAME))
        inner = prefix + ("      " if last_f else " |    ")
        for k, successor in enumerate(successor_list):
            walk(successor, inner, k == len(successor_list) - 1)

    source_list = system.source_list()
    for k, name in enumerate(source_list):
        walk(name, "", k == len(source_list) - 1)
    return "\n".join(line_list)


def _escaped(text):
    """RETURN: str, 'text' safe inside SVG/XML text and attributes."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def drawn_svg(system):
    """RETURN: str, the system as an SVG document: one column per depth
                    ('<stdin>' left, '<stdout>' right), a box per
                    script, an arrow per edge -- sinks feed '<stdout>'.
    """
    depth_db  = system.depth_db()
    max_depth = max(depth_db.values()) if depth_db else 0
    column_db = {STDIN_NAME: 0, STDOUT_NAME: max_depth + 1}
    column_db.update(depth_db)
    row_db, count_db = {}, {}
    for name in [STDIN_NAME] + system.node_list + [STDOUT_NAME]:
        column = column_db[name]
        row_db[name] = count_db.get(column, 0)
        count_db[column] = row_db[name] + 1
    char_w, box_h, gap_x, gap_y, pad = 8, 30, 60, 24, 20
    width_db = dict((n, 16 + char_w * len(n)) for n in column_db)
    col_w    = max(width_db.values())
    row_n    = max(count_db.values())
    total_h  = max(row_n * (box_h + gap_y), max(count_db.values())) + pad
    total_w  = (max_depth + 2) * (col_w + gap_x) - gap_x + 2 * pad

    def box_of(name):
        column, row = column_db[name], row_db[name]
        height = count_db[column] * (box_h + gap_y)
        top    = pad + (total_h - pad - height) / 2.0 + row * (box_h + gap_y)
        left   = pad + column * (col_w + gap_x) + (col_w - width_db[name]) / 2.0
        return left, top, width_db[name]

    part_list = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="monospace" font-size="13">'
        % (total_w, total_h + pad, total_w, total_h + pad),
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#444"/></marker></defs>']
    edge_list = list(system.edge_list) \
                + [(n, STDOUT_NAME) for n in system.node_list
                   if not system.successor_list(n)]
    for source, target in edge_list:
        sl, st, sw = box_of(source)
        tl, tt, tw = box_of(target)
        part_list.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#444" '
            'stroke-width="1.5" marker-end="url(#arrow)"/>'
            % (sl + sw, st + box_h / 2.0, tl - 2, tt + box_h / 2.0))
    for name in [STDIN_NAME] + system.node_list + [STDOUT_NAME]:
        left, top, width = box_of(name)
        terminal_f = name in (STDIN_NAME, STDOUT_NAME)
        part_list.append(
            '<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="%d" '
            'fill="%s" stroke="#444"/>'
            % (left, top, width, box_h, 15 if terminal_f else 4,
               "#eee" if terminal_f else "#fff"))
        part_list.append(
            '<text x="%.1f" y="%.1f" text-anchor="middle" '
            'dominant-baseline="central" fill="#000">%s</text>'
            % (left + width / 2.0, top + box_h / 2.0, _escaped(name)))
    part_list.append("</svg>")
    return "\n".join(part_list)
