"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE EXPLANATION OF THE FEATURES, 'hwut-feature-doc.dat', read
         (spec 43 section 2; intend/43 T-c, T-g, T-p, T-s). ONE file beside
         the forest (t-7 struck, 2026-11-08): blocks headed by a bracketed
         line, each running to the next heading or to the end of the file.

    [[CUSTOMERS]]
    manager:   the one who puts us under pressure
    intern:    the student

    [[gateway to manager]]
    documents: ../README.txt, spec/routing.txt#3
    The gateway forwards what reaches it.          <- the TITLE
    Further lines are the DOC.

    [[keeporder not manager]]
    ...
    [[old-thing:retired]]
    ...

    read_doc(top, forest)       -> CDoc | None
    doc_of_text(text, forest)   -> CDoc               (raises DocFault)

THE HEADINGS: '[[<id>]]', '[[<id> to <audience>, ...]]', '[[<id> not
<audience>, ...]]', '[[<id>:retired]]', '[[CUSTOMERS]]'. <id> may also be
'+<prototype>' -- documenting every instance of it -- or an instance's
'<owner>+<id>', which wins over its member's block (intend/44 p-5). 'CUSTOMERS' is
reserved and no feature id. A block: an optional 'documents:' line --
paths separated by commas, relative to the doc file, '#<anchor>' may
follow, or URLs -- then the prose; its first non-empty line is the title,
the rest the doc. Before the first heading only blank lines and '#'
comments may stand.

AUDIENCES ARE DOCUMENTATION ONLY (T-g): 'to' adds the named audiences to
the feature and everything below it in the forest, 'not' removes them
from what it inherits. An audience '[[CUSTOMERS]]' does not declare is a
fault; so is an id documented twice, an id both retired and standing in
a forest line, and an id with a retired block and a plain one.

A FAULT of an unknown name ends in 'did you mean' ('suggestion').
______________________________________________________________________________
"""
import os
import re
from   dataclasses import dataclass, field

from .feature_forest import id_valid_f
from .suggestion     import did_you_mean

from .finder         import DOC_FILE_NAME

CUSTOMERS     = "CUSTOMERS"
DOCUMENTS     = "documents:"
RETIRED_MARK  = ":retired"

_HEADING_RE   = re.compile(r"\[\[(.*)\]\]\s*\Z")
_AUDIENCE_RE  = re.compile(r"([A-Za-z0-9_\-]+)\s*:\s*(.*)\Z")


class DocFault(Exception):
    """The doc file cannot be read. 'word' is the name the fault concerns
    and 'candidate_tuple' what it was looked for among: the text ends in
    their 'did you mean'; both empty where nothing is to suggest."""

    def __init__(self, text, word="", candidate_tuple=()):
        super().__init__(text + (did_you_mean(word, candidate_tuple)
                                 if word else ""))
        self.word            = word
        self.candidate_tuple = tuple(candidate_tuple)


@dataclass(frozen=True)
class CDocEntry:
    """One feature's block: its title (the first prose line), the doc
    (the rest, '' where none), the documents it names, the audiences its
    heading adds ('to') and removes ('not'), and where it stands."""
    id:             str
    title:          str = ""
    doc:            str = ""
    document_tuple: tuple = ()
    to_tuple:       tuple = ()
    not_tuple:      tuple = ()
    line_n:         int = 0
    retired_f:      bool = False


@dataclass(frozen=True)
class CDoc:
    """What the doc file states: the blocks of standing features, the
    retired ones, the audiences declared ('customer_db', name -> who it
    is, file order) and each feature's audiences folded down the forest
    ('audience_db', id -> tuple, sorted; only ids that have some)."""
    entry_db:    dict = field(default_factory=dict)   # id -> CDocEntry
    retired_db:  dict = field(default_factory=dict)   # id -> CDocEntry
    customer_db: dict = field(default_factory=dict)   # audience -> text
    audience_db: dict = field(default_factory=dict)   # id -> tuple
    file:        str = DOC_FILE_NAME


def read_doc(top, forest):
    """
    RETURN: CDoc, what 'top/hwut-feature-doc.dat' states, the audiences
            folded down 'forest' (a CForest, or None: no forest)
            None, no such file stands
    RAISES: DocFault, where it cannot be read or states a fault.
    """
    path = os.path.join(top, DOC_FILE_NAME)
    if not os.path.isfile(path): return None
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise DocFault("%s: cannot be read (%s)"
                       % (DOC_FILE_NAME, error)) from error
    return doc_of_text(text, forest, DOC_FILE_NAME)


def _fault(file, line_n, message, word="", candidate_tuple=()):
    """RETURN: DocFault, 'FAULT: <file>:<line>: <message>'."""
    return DocFault("FAULT: %s:%i: %s" % (file, line_n, message),
                    word, candidate_tuple)


def _heading(text, file, line_n):
    """
    RETURN: tuple (id, kind, audience tuple) of one heading's inside:
            kind '' plain, 'to', 'not', 'retired', or 'customers'
    RAISES: DocFault, where it is none of the five shapes.
    """
    text = text.strip()
    if text == CUSTOMERS: return CUSTOMERS, "customers", ()
    if text.endswith(RETIRED_MARK):
        feature_id = text[:-len(RETIRED_MARK)].strip()
        kind, audience_tuple = "retired", ()
    else:
        word_list  = text.split(None, 2)
        feature_id = word_list[0] if word_list else ""
        if len(word_list) == 1:
            kind, audience_tuple = "", ()
        elif len(word_list) == 3 and word_list[1] in ("to", "not"):
            kind = word_list[1]
            audience_tuple = tuple(each.strip()
                                   for each in word_list[2].split(","))
            if not all(id_valid_f(each) for each in audience_tuple):
                raise _fault(file, line_n, "'[[%s]]': an audience is a "
                             "word '[A-Za-z0-9_-]+', ',' between" % text)
        else:
            raise _fault(file, line_n, "'[[%s]]' is no heading -- "
                         "'[[<id>]]', '[[<id> to <audience>, ...]]', "
                         "'[[<id> not <audience>, ...]]', "
                         "'[[<id>:retired]]', '[[CUSTOMERS]]'" % text)
    if feature_id == CUSTOMERS:
        raise _fault(file, line_n, "'CUSTOMERS' is reserved and no "
                     "feature id")
    if not heading_id_valid_f(feature_id):
        raise _fault(file, line_n, "'%s' is no feature id -- "
                     "'[A-Za-z0-9_-]+', '+<prototype>' or '<owner>+<id>'"
                     % feature_id)
    return feature_id, kind, audience_tuple


def heading_id_valid_f(text):
    """RETURN: True, 'text' may head a block: a feature id or a member's,
    '+<prototype>' (intend/44 p-5), or '<owner>+<id>' of an instance;
    False else."""
    if text.startswith("+"): return id_valid_f(text[1:])
    owner, mark, rest = text.partition("+")
    return id_valid_f(owner) and (not mark or id_valid_f(rest))


def effective_entry(entry_db, forest, feature_id):
    """
    RETURN: CDocEntry, what documents 'feature_id': its own block; for an
            instance '<owner>+<id>' without one, the block of the member
            '<id>', else of the prototype it stands in -- for an inner
            prototype's instance '<owner>+<Q>' the block '[[+Q]]', else
            the prototype's around it (intend/44 p-5, p-8)
            None, nothing does
    """
    entry = entry_db.get(feature_id)
    if entry is not None or "+" not in feature_id[1:]: return entry
    word = feature_id.partition("+")[2]
    if forest is None: return entry_db.get(word)
    if word in forest.prototype_db:
        entry, word = entry_db.get("+" + word), word
    else:
        entry = entry_db.get(word)
    while entry is None and word in forest.member_of:
        word  = forest.member_of[word]
        entry = entry_db.get("+" + word)
    return entry


def _entry(feature_id, kind, audience_tuple, line_list, line_n):
    """RETURN: CDocEntry of one feature's block, 'line_list' its lines
    after the heading."""
    body = list(line_list)
    while body and not body[0].strip(): body.pop(0)
    document_tuple = ()
    if body and body[0].strip().startswith(DOCUMENTS):
        document_tuple = tuple(
            each.strip() for each in
            body.pop(0).strip()[len(DOCUMENTS):].split(",")
            if each.strip())
    while body and not body[0].strip(): body.pop(0)
    while body and not body[-1].strip(): body.pop()
    title = body.pop(0).strip() if body else ""
    while body and not body[0].strip(): body.pop(0)
    return CDocEntry(feature_id, title, "\n".join(each.rstrip()
                                                   for each in body),
                     document_tuple,
                     audience_tuple if kind == "to" else (),
                     audience_tuple if kind == "not" else (),
                     line_n, kind == "retired")


def doc_of_text(text, forest, file=DOC_FILE_NAME):
    """
    RETURN: CDoc, what 'text' states as a doc file, the audiences folded
            down 'forest' (None: every feature a root).
    RAISES: DocFault, at the first fault -- text before the first heading,
            a heading of no shape, an id documented twice, a retired id
            standing in a forest line, an audience not declared, a
            'CUSTOMERS' line of no shape.
    """
    block_list, current = [], None             # (heading, line_n, lines)
    for line_n, line in enumerate(text.splitlines(), start=1):
        found = _HEADING_RE.match(line.strip()) if line.startswith("[[") \
                else None
        if found is not None:
            current = (_heading(found.group(1), file, line_n), line_n, [])
            block_list.append(current)
        elif current is not None:
            current[2].append(line)
        elif line.strip() and not line.lstrip().startswith("#"):
            raise _fault(file, line_n, "text before the first heading -- "
                         "'[[<id>]]' opens a block")
    entry_db, retired_db, customer_db, seen = {}, {}, {}, {}
    customer_line_n = None
    for (feature_id, kind, audience_tuple), line_n, line_list in block_list:
        if kind == "customers":
            if customer_line_n is not None:
                raise _fault(file, line_n, "'[[CUSTOMERS]]' stands twice "
                             "(line %i)" % customer_line_n)
            customer_line_n = line_n
            for i, line in enumerate(line_list, start=line_n + 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                found = _AUDIENCE_RE.match(line.strip())
                if found is None:
                    raise _fault(file, i, "'%s' is no audience line -- "
                                 "'<audience>: <who that is>'"
                                 % line.strip())
                customer_db[found.group(1)] = found.group(2).strip()
            continue
        if feature_id in seen:
            raise _fault(file, line_n, "'%s' is documented twice (line %i)"
                         % (feature_id, seen[feature_id]))
        seen[feature_id] = line_n
        entry = _entry(feature_id, kind, audience_tuple, line_list, line_n)
        (retired_db if entry.retired_f else entry_db)[feature_id] = entry
    for entry in entry_db.values():
        for audience in entry.to_tuple + entry.not_tuple:
            if audience not in customer_db:
                raise _fault(file, entry.line_n, "'%s': the audience '%s' "
                             "is not declared in '[[CUSTOMERS]]'"
                             % (entry.id, audience), audience,
                             tuple(customer_db))
    for entry in entry_db.values():
        _instance_heading_checked(entry, forest, file)
    if forest is not None:
        for entry in retired_db.values():
            if entry.id in forest.id_set:
                raise _fault(file, entry.line_n, "'%s' is retired and "
                             "stands in a forest line (%s:%i) -- strike "
                             "one" % (entry.id, forest.file,
                                      forest.line_of[entry.id]))
    return CDoc(entry_db, retired_db, customer_db,
                _audience_db(entry_db, forest), file)


def _instance_heading_checked(entry, forest, file):
    """RETURN: None. RAISES: DocFault where the block heads a prototype
    the forest does not declare, or an instance it does not hold."""
    if entry.id.startswith("+"):
        if forest is None or entry.id[1:] not in forest.prototype_db:
            raise _fault(file, entry.line_n, "'%s' heads a block and no "
                         "prototype '%s' is declared" % (entry.id, entry.id))
    elif "+" in entry.id:
        if forest is None or entry.id not in forest.id_set:
            raise _fault(file, entry.line_n, "'%s' heads a block and names "
                         "no instance of the forest" % entry.id, entry.id,
                         sorted(each for each in (forest.id_set if forest
                                                  else ()) if "+" in each))


def _audience_db(entry_db, forest):
    """RETURN: dict, id -> tuple of audiences (sorted), every id of the
    forest and of 'entry_db' that has some: what its ancestors add, then
    its own heading's 'to' added and 'not' removed."""
    result, cache = {}, {}
    id_set = set(each for each in entry_db if not each.startswith("+")) \
             | (set(forest.id_set) if forest else set())

    def audience_of(feature_id):
        if feature_id in cache: return cache[feature_id]
        parent = forest.parent_of.get(feature_id) if forest else None
        found  = set(audience_of(parent)) if parent is not None else set()
        entry  = effective_entry(entry_db, forest, feature_id)
        if entry is not None:
            found |= set(entry.to_tuple)
            found -= set(entry.not_tuple)
        cache[feature_id] = frozenset(found)
        return cache[feature_id]

    for each in id_set:
        found = audience_of(each)
        if found: result[each] = tuple(sorted(found))
    return result


def doc_text(entry_list, customer_db=None, head_comment=()):
    """RETURN: str, a doc file stating 'customer_db' (audience -> text;
    None or empty: no block) and the blocks of 'entry_list' (CDocEntry),
    in order, a blank line between, after 'head_comment' ('# ' lines)."""
    part_list = ["".join("# %s\n" % each if each else "#\n"
                         for each in head_comment)]
    if customer_db:
        width = max(len(each) for each in customer_db) + 1
        part_list.append("[[CUSTOMERS]]\n" + "".join(
            "%-*s %s\n" % (width, each + ":", text)
            for each, text in customer_db.items()))
    for entry in entry_list:
        heading = entry.id + RETIRED_MARK if entry.retired_f \
                  else "%s to %s" % (entry.id, ", ".join(entry.to_tuple)) \
                  if entry.to_tuple \
                  else "%s not %s" % (entry.id, ", ".join(entry.not_tuple)) \
                  if entry.not_tuple else entry.id
        line_list = ["[[%s]]" % heading]
        if entry.document_tuple:
            line_list.append("%s %s" % (DOCUMENTS,
                                        ", ".join(entry.document_tuple)))
        if entry.title: line_list.append(entry.title)
        if entry.doc:   line_list.append(entry.doc)
        part_list.append("\n".join(line_list) + "\n")
    return "\n".join(each for each in part_list if each)
