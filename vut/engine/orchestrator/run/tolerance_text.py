"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TOLERANCE AS TEXT, AND BACK (intend 21) -- what the merge
         screen's tolerance pane shows, and what it makes of what the
         author typed there.

DESCRIPTION
       THE PANE SPEAKS THE HEADER'S LANGUAGE. It shows one scope,

           tolerance {
               numeric_ratio = 0.0                   # default
               eq_pattern    = ["SUCCESS.*"]
               ...
           }

       every key 'tolerance { }' knows, with the value compare will use,
       and '# default' where that is compare's own. What the author
       leaves in the pane is read by the exploration's OWN reader --
       'hwut_hocon', then the validator's '_tolerance' -- so a key the
       header refuses is refused here with the same words, and nothing
       parses a second grammar.

       THE LOWER LINE STANDS. The header's rule is that a key stated
       twice is a fault. In the pane the proposals stand, commented,
       below the keys they would replace; uncommenting one would then
       be a fault the author did not make. So, in the pane only, a key
       stated on a line of its own a second time replaces the earlier
       line.

       THE CONFIGURATION IN MEMORY IS THE BASE. What the pane states is
       applied onto a copy of the configuration the session holds, by
       the run's own mapping ('adapter.tolerance_applied'); what the
       pane cannot state -- the line level's numbers, the regions'
       parameters -- stays as it was.
______________________________________________________________________________
"""
import copy
import re

from vut.test_writing_support.python             import hwut_hocon
from vut.engine.orchestrator.exploration         import validator
from vut.engine.orchestrator.exploration.unwrapper import plain_lines
#  ONE PRINTER OF VALUES (exploration X-PRINTED): what the pane shows is
#  what 'hwut.config.show' shows, escaped so it reads back as written.
from vut.engine.orchestrator.exploration.printer   import value_text
from .adapter import TOLERANCE_LEAF_TUPLE, tolerance_applied

PANE_FILE = "<tolerance pane>"

_INDENT       = "    "
_KEY_WIDTH    = max(len(leaf) for leaf in TOLERANCE_LEAF_TUPLE)
_VALUE_COLUMN = 42


def leaf_db_of(options):
    """
    RETURN: dict, tolerance leaf -> the value compare holds for it, in
            the header's terms: a number, a boolean, a tuple of strings;
            a marker PAIR as a 2-tuple, or () where it is off.
    """
    finder = options.pattern_finder
    return {
        "numeric_ratio": float(finder.numeric_tolerance_ratio),
        "whitespace":    bool(finder.whitespace_f),
        "regions":       bool(finder.regions_f),
        "eq_pattern":    tuple(finder.equivalent_pattern_list),
        "nothing":       tuple(finder.visible_nothing_pattern_list),
        "analogy":       (finder.analogy_begin_marker,
                          finder.analogy_end_marker) if finder.analogy_f else (),
        "constraints":   tuple(options.constraint_expression_list),
        "comment":       (finder.ignored_line_begin_marker,
                          finder.ignored_line_end_marker)
                         if finder.ignored_line_f else (),
    }


PROPOSAL_HEAD = ("# PROPOSALS stand, commented, under the key they would replace: "
                 "uncomment one -- the lower line stands -- then <F5>")


def text_of(options, proposal_db=None):
    """
    RETURN: str, the pane: 'tolerance { ... }' with every key and its
            value, '# default' beside each that is compare's own, and
            under a key the PROPOSALS for it -- comments, '# key = value'
            aligned as the key's own line is -- so a person comments the
            old, uncomments the new, and sees both in one place.

    'proposal_db' is 'proposal.proposal_db''s: key -> comment lines.
    """
    from vut.engine.compare.api import Configuration
    default_db  = leaf_db_of(Configuration())
    proposal_db = proposal_db or {}
    line_list   = [PROPOSAL_HEAD] if proposal_db else []
    line_list.append("tolerance {")
    for leaf, value in leaf_db_of(options).items():
        line = "%s%-*s = %s" % (_INDENT, _KEY_WIDTH, leaf, value_text(value))
        if value == default_db[leaf]:
            line = "%-*s # default" % (_VALUE_COLUMN, line)
        line_list.append(line)
        for proposal in proposal_db.get(leaf, ()):
            match = re.match(r"#\s*%s\s*=\s*(.*)$" % re.escape(leaf), proposal)
            if match is not None:
                proposal = "# %-*s = %s" % (_KEY_WIDTH, leaf, match.group(1))
            line_list.append(_INDENT + proposal)
    line_list.append("}")
    return "\n".join(line_list) + "\n"


def stated_text_of(options):
    """
    RETURN: str, one line 'tolerance { key = value  ... }' holding every
            key whose value is NOT compare's default -- what a header
            must state to make compare read as 'options' does.
            None, where every value is the default.
    """
    from vut.engine.compare.api import Configuration
    default_db = leaf_db_of(Configuration())
    pair_list  = ["%s = %s" % (leaf, value_text(value))
                  for leaf, value in leaf_db_of(options).items()
                  if value != default_db[leaf]]
    if not pair_list: return None
    return "tolerance { %s }" % "  ".join(pair_list)


def configuration_of(text, base):
    """
    RETURN: (Configuration, None), 'base' copied, with what 'text' states
                                   applied.
            (None, str), the text cannot be read: the fault, with its
                         line in the pane -- 'line 3: ...'.
    """
    pane_line_list = _lower_line_stands(text.split("\n"))
    source_list    = plain_lines("\n".join(["hwut {"] + pane_line_list + ["}"]))
    document, parse_fault_list = hwut_hocon.parse(source_list, PANE_FILE)
    if parse_fault_list:
        return None, _fault_text(parse_fault_list[0].position,
                                 parse_fault_list[0].message)

    fault_list = []
    node = validator.document_hwut_node(document, PANE_FILE, fault_list)
    if node is None or fault_list:
        return None, _fault_text(None, fault_list[0].message
                                 if fault_list else "nothing to read")
    entry_list = [entry for entry in node.entry_list]
    if len(entry_list) != 1 or entry_list[0].key != "tolerance":
        return None, "the pane holds one scope: 'tolerance { ... }'"

    tolerance = validator._tolerance(entry_list[0], PANE_FILE, fault_list)
    if fault_list:
        return None, _fault_text(fault_list[0].position, fault_list[0].message)
    options = copy.deepcopy(base)
    tolerance_applied(options, tolerance)
    return options, None


_KEY_LINE_RE = re.compile(r"^\s*([A-Za-z_]+)\s*=")


def _lower_line_stands(line_list):
    """RETURN: list[str], 'line_list' with every earlier line of a key
               that a LATER line of its own states again blanked -- where
               both are whole on their line (brackets balanced)."""
    last_db = {}
    for i, line in enumerate(line_list):
        match = _KEY_LINE_RE.match(line)
        if match is not None and _whole_f(line):
            last_db[match.group(1)] = i
    result = []
    for i, line in enumerate(line_list):
        match = _KEY_LINE_RE.match(line)
        if match is not None and _whole_f(line) and last_db[match.group(1)] != i:
            result.append("")
        else:
            result.append(line)
    return result


def _whole_f(line):
    """RETURN: bool, True where the line's brackets and braces balance."""
    return line.count("[") == line.count("]") and line.count("{") == line.count("}")


def _fault_text(position, message):
    """RETURN: str, the fault as the pane's status bar says it -- the line
               counted in the pane, not in the wrapper around it."""
    if position is None: return message
    return "line %i: %s" % (position.line - 1, message)
