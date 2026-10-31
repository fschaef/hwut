"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut-root.labels' -- reading it, writing it (disc-8).

The file stands BESIDE 'hwut-root.conf', at the tree's boundary, the
very boundary the configuration climb ends at
('tree_explorer.root_conf_directory'). Absent means no label exists,
which is not an error.

    #  hwut-root.labels -- the sets of this tree.
    ./engine/bookkeeper/TEST/test-group_table.py : concern
    :/: groups                                   : meta
    :/test-stream_store.py                       : meta

    <target> : <label> [<label>...]

ONE MARK, TWO POSITIONS: a LEADING ':' is a ditto for one path
component (':/' the previous entry's directory, ':/:' its directory
and file, a choice following); an INTERIOR ' : ' -- one colon, a blank
either side -- separates the target from its labels.

LITERAL TARGETS ONLY. Globbing is for what a PERSON writes -- the
command line and a wishlist; THIS FILE IS THE FRAMEWORK'S, the faces
expand at write time, and a glob found here is refused by name.

SORTED on '(directory, file, choice)', the choice-less entry of an
application first; the writer rewrites the file WHOLE, sorted and
elided, so the ditto chain is always canonical and a hand edit that
broke it is repaired by the next write.

A HAND COMMENT SURVIVES WHERE IT IS GLUED (E-96): comment lines that
stand directly above an entry (no blank between) travel with that
entry -- rewritten beside it, removed with it; lines after the LAST
entry of a block (before a blank or the end) travel below it. A
comment between two entries introduces the one below. A comment with
a blank line on both sides is glued to nothing; the rewrite may drop
it without notice. The header is the framework's.

THE HEADER IS A PREAMBLE THE PERSON OWNS (E-98): from line 1 down to
the first '#___' rule, kept verbatim by every rewrite. A file without
the rule receives the framework's header, which ends in that rule.

ONE LINE PER RUN. A run named twice is a fault, named by line: two
answers to one question is not a merge, it is a mistake.

DERIVED LABELS (D-56) stand in a section of their own, to the end of
the file, below the entries:

    [derived]
    needs-outside = needs-container OR needs-network OR needs-pwsh
    sandbox       = meta AND NOT needs-outside

    <label> = <label expression>

The expression is the '--label' grammar (plan/label.py). A run carries
a derived label where its labels -- assigned, and derived on lines it
may name -- answer the expression; derived labels expand RECURSIVELY,
and a circle is a fault naming it. A name nothing assigns or derives
is absent in the evaluation and said as 'missing in expression
evaluation' by 'hwut.labels.list'. The section is the PERSON'S: every
rewrite keeps it verbatim, in its order, with its comments; an entry
below the heading is refused by name.
______________________________________________________________________________
"""
import io
import re
import os

from ....engine.orchestrator.plan.label import (KEYWORD_TUPLE,
                                                  LABEL_NAME_REGEX,
                                                  STANDARD_LABEL,
                                                  UNIVERSE_NAME,
                                                  CLabelView)
from ....engine.orchestrator.plan.wish import (ElisionError,
                                                  expanded_target)
from   hwut.engine.orchestrator.exploration.tree_explorer \
                                          import root_conf_directory

LABELS_FILE_NAME = "hwut-root.labels"

GLOB_MARK_TUPLE  = ("*", "?", "[")

HEADER = (
    "# TEST RUN LABEL DEFINITIONS:",
    "# ",
    "# This files defines labels to be referred to for test runs (using '--label').",
    "# The format is the following:",
    "#",
    "#        <target> : <label> [<label>...]",
    "#",
    "# Globs like '*' and '?' expressions may not be used. However, following ",
    "# shorthands exits:",
    "#",
    "#   Leading ':/'   means: directory same as in previous entry",
    "#           ':/:' means: same directory and application as previous entry.",
    "#",
    "# This files is modified and read by the 'hwut.labels.*' applications. ",
    "#",
    "# NOTE: Hand written comments",
    "#",
    "#   Comments glued to an entry (line above/below, no blank) travel with it, go ",
    "#   with it; comments blank-separated may be dropped.",
    "#",
    "#   Any comment above the first '#__...' line is also maintained",
    "#" + "_" * 78,
)
#  THE HEADER'S CLOSING RULE (E-98): everything from line 1 down to the
#  first line of this shape is the PREAMBLE, kept verbatim by every
#  rewrite -- a person may edit it or note things there. A file without
#  the rule gets HEADER written.
_RULE_RE = re.compile(r"^#_{3,}\s*$")

#  WHAT THE LAST READ OF EACH FILE KEPT, by the file's path: the glued
#  comments by entry key (E-96), the preamble (E-98), and the derived
#  section (D-56) -- what the next write of THAT file puts back. Keyed by
#  path: a face that reads one tree's file and writes another's
#  ('hwut.move' across roots) must not write one file's header or
#  derivations into the other.
_KEPT_DB = {}

DERIVED_HEADING = "[derived]"
_DERIVATION_RE  = re.compile(r"^([^\s=]+)\s*=\s*(.*\S)\s*$")


class _Kept:
    """What one read of one labels file keeps for its next write."""
    __slots__ = ("glued_db", "preamble", "derived_line_list",
                 "derivation_list")

    def __init__(self):
        self.glued_db          = {}       # key -> (above, below)
        self.preamble          = []       # the header, verbatim
        self.derived_line_list = []       # the section below the heading
        self.derivation_list   = []       # (line_n, label, text, tree)


def _kept(path):
    """RETURN: _Kept, what the last read of 'path' kept; an empty one
               where the file was not read in this process."""
    return _KEPT_DB.get(os.path.abspath(path)) or _Kept()


class LabelFileError(Exception):
    """A labels file that cannot be meant: a missing separator, a
    glob, a ditto with no predecessor, a run named twice, a word no
    label may be. The message names file and line."""


def file_path(boundary):
    """
    RETURN: str, where the labels file of the tree bounded at
            'boundary' stands -- beside 'hwut-root.conf'.
    """
    return os.path.join(boundary, LABELS_FILE_NAME)


def boundary_of(directory):
    """
    RETURN: str, the absolute directory holding the 'hwut-root.conf'
            that bounds the tree 'directory' stands in.

    Raises RootConfMissing (tree_explorer) where none stands: the
    labels file anchors where the configuration climb ends, or two
    climbs could name two trees.
    """
    return root_conf_directory(directory)


def read_entry_db(boundary):
    """
    RETURN: dict, '(<file>, <choice> | None)' -> frozenset[str] -- what
            'hwut-root.labels' assigns; the file path RELATIVE to
            'boundary', '/'-separated, no './'. Empty where the file
            is absent, which means: no label exists.

    Raises LabelFileError, naming file and line, where a line cannot
    be meant (see the module purpose).
    """
    path = file_path(boundary)
    kept = _Kept()
    _KEPT_DB[os.path.abspath(path)] = kept
    if not os.path.isfile(path): return {}
    with io.open(path, "r", encoding="utf-8") as file_handle:
        line_list = file_handle.read().splitlines()

    entry_db = {}
    previous = None                        # last EXPANDED target text
    glued_db = kept.glued_db
    preamble = kept.preamble
    #  THE PREAMBLE: up to and including the first '#___' rule (E-98).
    #  Without a rule, a leading comment block from line 1 is the old
    #  header and is replaced.
    rule_i = next((i for i, l in enumerate(line_list) if _RULE_RE.match(l)),
                  None)
    if rule_i is not None:
        preamble[:] = line_list[:rule_i + 1]
        line_list    = line_list[rule_i + 1:]
        number_base  = rule_i + 1
    else:
        number_base  = 0
    #  THE DERIVED SECTION: from its heading to the end of the file.
    heading_i = next((i for i, l in enumerate(line_list)
                      if l.strip() == DERIVED_HEADING), None)
    if heading_i is not None:
        kept.derived_line_list = line_list[heading_i + 1:]
        _read_derivations(path, kept, number_base + heading_i + 2)
        line_list = line_list[:heading_i]
    above, last_key, header_f = [], None, rule_i is None
    for number, line in enumerate(line_list, start=1 + number_base):
        text = line.strip()
        if not text:
            if above and last_key is not None:   # ended by a blank: below
                glued_db[last_key][1].extend(above)
            above, last_key = [], None      # a blank breaks the glue
            header_f = False                # ... and ends an old header
            continue
        if text.startswith("#"):
            if header_f: continue           # an old header without a rule
            #  A COMMENT INTRODUCES WHAT FOLLOWS: between two entries it
            #  is glued ABOVE the next; it is glued BELOW the last only
            #  where no entry follows before a blank or the end.
            above.append(line)
            continue
        header_f = False
        target_part, label_part = _split(path, number, text)
        if target_part.startswith(":"):
            try:
                target_part = expanded_target(target_part, previous)
            except ElisionError as error:
                raise LabelFileError("%s:%d: %s"
                                     % (path, number, error)) from None
        previous = target_part
        key = _key(path, number, target_part)
        if key in entry_db:
            raise LabelFileError(
                "%s:%d: the run '%s' is named twice -- two answers "
                "to one question is not a merge, it is a mistake"
                % (path, number, target_text(key)))
        entry_db[key] = frozenset(_label_tuple(path, number,
                                               label_part))
        glued_db[key] = (above, [])
        above, last_key = [], key
    if above and last_key is not None:      # trailing: below the last
        glued_db[last_key][1].extend(above)
    _order_derivations(path, kept)
    return entry_db


def _read_derivations(path, kept, first_number):
    """
    RETURN: None, filling 'kept.derivation_list' with one '(line,
            label, expression text, tree)' per derivation of the section,
            in file order, if success.
            raises LabelFileError naming file and line, else: a line
            that is no '<label> = <expression>', an entry below the
            heading, a word no label may be, an expression the grammar
            cannot mean, a label derived twice.
    """
    from ....engine.orchestrator.plan.label import (parse_expression,
                                                     LabelExprError)
    seen_db = {}
    for number, line in enumerate(kept.derived_line_list,
                                  start=first_number):
        text = line.strip()
        if not text or text.startswith("#"): continue
        if text.startswith("./") or text.startswith(":"):
            raise LabelFileError(
                "%s:%d: an entry stands below '%s' -- entries go above "
                "the heading; below it stand derivations only"
                % (path, number, DERIVED_HEADING))
        match = _DERIVATION_RE.match(text)
        if match is None:
            raise LabelFileError(
                "%s:%d: a derivation reads '<label> = <expression>'"
                % (path, number))
        label, expression = match.group(1), match.group(2)
        _label_tuple(path, number, label)
        if label in seen_db:
            raise LabelFileError(
                "%s:%d: '%s' is derived twice (line %d) -- one label, "
                "one expression" % (path, number, label, seen_db[label]))
        seen_db[label] = number
        try:
            tree = parse_expression(expression)
        except LabelExprError as error:
            raise LabelFileError("%s:%d: %s" % (path, number, error)) \
                  from None
        kept.derivation_list.append((number, label, expression, tree))


def _order_derivations(path, kept):
    """
    RETURN: None, with 'kept.derivation_list' ordered so that every
            derived label an expression names stands before it, if
            success.
            raises LabelFileError naming the circle, else.
    """
    from ....engine.orchestrator.plan.label import label_name_tuple
    by_label = {d[1]: d for d in kept.derivation_list}
    ordered, state = [], {}

    def visit(label, trail):
        """RETURN: None. Places 'label' after what it depends on."""
        if state.get(label) == "done": return
        if state.get(label) == "open":
            circle = trail[trail.index(label):] + [label]
            raise LabelFileError(
                "%s:%d: derived labels form a circle: %s"
                % (path, by_label[label][0], " -> ".join(circle)))
        state[label] = "open"
        for name in label_name_tuple(by_label[label][3]):
            if name in by_label: visit(name, trail + [label])
        state[label] = "done"
        ordered.append(by_label[label])

    for derivation in kept.derivation_list:
        visit(derivation[1], [])
    kept.derivation_list = ordered


def derivation_tuple(boundary, entry_db):
    """
    RETURN: tuple of (label, expression text, member count, missing
            names) -- one per derivation of the file 'read_entry_db'
            last read under 'boundary', in the FILE'S order. 'member
            count' counts the file's targets that carry the label;
            'missing names' are the names the expression mentions that
            nothing assigns or derives (D-56).
    """
    from ....engine.orchestrator.plan.label import (label_name_tuple,
                                                     derived_label_set,
                                                     feature_label_f)
    kept     = _kept(file_path(boundary))
    derived  = tuple((d[1], d[3]) for d in kept.derivation_list)
    known    = defined_label_set(entry_db) | {d[0] for d in derived}
    result   = []
    for number, label, text, tree in sorted(kept.derivation_list):
        member_n = 0
        for (file, choice), label_set in entry_db.items():
            own = label_set if choice is None \
                  else label_set | entry_db.get((file, None), frozenset())
            if label in derived_label_set(derived, own): member_n += 1
        #  A FEATURE LABEL ('f/...') is the feature relation's, never
        #  assigned here: not missing, and not counted among the members.
        missing = tuple(name for name in label_name_tuple(tree)
                        if name not in known and not feature_label_f(name))
        result.append((label, text, member_n, missing))
    return tuple(result)


def write_entry_db(boundary, entry_db):
    """
    RETURN: None. Rewrites 'hwut-root.labels' WHOLE: header, then the
            entries sorted and elided. An 'entry_db' holding nothing
            REMOVES the file -- absent and empty mean the same, 'no
            label exists', and only one of the two spellings can be
            canonical.
    """
    path = file_path(boundary)
    kept = _kept(path)
    derived_line_list = list(kept.derived_line_list)
    while derived_line_list and not derived_line_list[-1].strip():
        derived_line_list.pop()
    if not entry_db and not kept.derivation_list:
        if os.path.isfile(path): os.remove(path)
        return
    line_list = _elided_line_list(entry_db)
    width     = max([len(target) for target, _ in line_list] or [0])
    with io.open(path, "w", encoding="utf-8", newline="\n") \
         as file_handle:
        for line in (kept.preamble or HEADER):
            file_handle.write(line.rstrip("\n") + "\n")
        for key, (target, label_tuple) in zip(sorted(entry_db, key=sort_key),
                                              line_list, strict=True):
            above, below = kept.glued_db.get(key, ([], []))
            for line in above: file_handle.write(line.rstrip() + "\n")
            file_handle.write("%-*s : %s\n"
                              % (width, target,
                                 " ".join(label_tuple)))
            for line in below: file_handle.write(line.rstrip() + "\n")
        #  THE DERIVED SECTION, as the person wrote it (D-56).
        if kept.derivation_list or derived_line_list:
            file_handle.write("\n%s\n" % DERIVED_HEADING)
            for line in derived_line_list:
                file_handle.write(line.rstrip() + "\n")


def defined_label_set(entry_db):
    """
    RETURN: frozenset[str], every label that stands -- the assigned
            ones, and the standard label always: 'meta' needs no
            'create' and is never undefined.
    """
    found = set((STANDARD_LABEL,))
    for label_set in entry_db.values():
        found.update(label_set)
    return frozenset(found)


def view_of(boundary, entry_db):
    """
    RETURN: CLabelView over 'entry_db' -- the shape the engine's
            selection reads (plan/label.py).
    """
    kept    = _kept(file_path(boundary))
    derived = tuple((d[1], d[3]) for d in kept.derivation_list)
    return CLabelView(boundary = os.path.abspath(boundary),
                      entry_db = dict(entry_db),
                      defined  = defined_label_set(entry_db)
                                 | frozenset(label for label, _ in derived),
                      derived  = derived)


def sort_key(key):
    """
    RETURN: tuple, the file's sort order for an entry key: directory
            COMPONENT-WISE, then file, then the choice -- the
            choice-less entry of an application FIRST, because the
            ditto chain hangs on the order.
    """
    file, choice = key
    directory, _, name = file.rpartition("/")
    part_tuple = tuple(directory.split("/")) if directory else ()
    return (part_tuple, name,
            (0, "") if choice is None else (1, choice))


def target_text(key):
    """
    RETURN: str, the entry as a full target line: './<file>', a choice
            after one blank where the key holds one.
    """
    file, choice = key
    return "./%s" % file if choice is None \
           else "./%s %s" % (file, choice)


def elided_target_tuple(key_list):
    """
    RETURN: tuple[str], the keys as WRITTEN targets, in the order
            given -- full ('./<file> [<choice>]'), ':/<file>
            [<choice>]' where the directory repeats, ':/: <choice>'
            where the file does. The caller sorts ('sort_key'); the
            elision only pays, and only holds, over a sorted run.
    """
    target_list   = []
    previous_file = None
    previous_dir  = None
    for key in key_list:
        file, choice = key
        full      = "./%s" % file
        directory = full.rsplit("/", 1)[0]
        if full == previous_file:
            assert choice is not None, \
                   "one file twice without a choice is a duplicate " \
                   "key, refused at reading"
            target = ":/: %s" % choice
        elif directory == previous_dir:
            target = ":/%s" % full.rsplit("/", 1)[1]
            if choice is not None: target += " %s" % choice
        else:
            target = target_text(key)
        previous_file = full
        previous_dir  = directory
        target_list.append(target)
    return tuple(target_list)


def _elided_line_list(entry_db):
    """
    RETURN: list[(str, tuple[str])], the entries sorted, each as its
            WRITTEN target with its labels sorted beside it.
    """
    key_list = sorted(entry_db, key=sort_key)
    return [(target, tuple(sorted(entry_db[key])))
            for key, target
            in zip(key_list, elided_target_tuple(key_list),
                   strict=True)]


def _split(path, number, text):
    """
    RETURN: [0] str, the target half of the line.
            [1] str, the label half.

    Raises LabelFileError where no ' : ' separator stands -- one
    colon, a blank either side. A leading ditto's colons carry no
    blank before them, so position alone tells the two apart.
    """
    target_part, separator, label_part = text.partition(" : ")
    if not separator:
        raise LabelFileError(
            "%s:%d: no ' : ' separates the target from its labels"
            % (path, number))
    return target_part.rstrip(), label_part.strip()


def _key(path, number, target_text):
    """
    RETURN: (str, str | None), the entry key of the EXPANDED target:
            the file relative to the boundary, and the choice.

    Raises LabelFileError where the target does not start './' -- the
    file's own ground, stated, not guessed -- or where it carries a
    glob: LITERAL TARGETS ONLY, this file is the framework's, and a
    stored pattern would hold two truths at once.
    """
    if not target_text.startswith("./"):
        raise LabelFileError(
            "%s:%d: a target starts './' -- the file's own ground -- "
            "and '%s' does not" % (path, number, target_text))
    if any(mark in target_text for mark in GLOB_MARK_TUPLE):
        raise LabelFileError(
            "%s:%d: '%s' carries a glob; this file holds LITERAL "
            "targets only -- globs are spent by the faces at write "
            "time, never stored" % (path, number, target_text))
    body = target_text[2:]
    file, _, choice = body.partition(" ")
    choice = choice.strip()
    return (file, choice if choice else None)


def _label_tuple(path, number, label_part):
    """
    RETURN: tuple[str], the labels of one line, each a word a label
            may be.

    Raises LabelFileError for an empty label half, a keyword, the
    universe, or a word outside the label alphabet. The STANDARD label
    is a label and passes.
    """
    word_tuple = tuple(label_part.split())
    if not word_tuple:
        raise LabelFileError("%s:%d: the line names no label"
                             % (path, number))
    for word in word_tuple:
        if word in KEYWORD_TUPLE or word == UNIVERSE_NAME:
            raise LabelFileError(
                "%s:%d: '%s' is reserved and never assigned"
                % (path, number, word))
        if LABEL_NAME_REGEX.match(word) is None:
            raise LabelFileError(
                "%s:%d: a label is letters, digits, '_', '-', '.' -- "
                "'%s' is not" % (path, number, word))
    return word_tuple
