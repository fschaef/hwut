"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THE FEATURE FACES WRITE (spec 43 section 5) -- each act
         edits the three files and the links, every other byte untouched,
         checks what it would write with the readers before it writes, and
         writes nothing where anything is refused.

    init(top)                -> list of str   empty forest and doc file
    rename(top, old, new)    -> list of str   the id and every reference
    retire(top, feature_id)  -> list of str   the block retired, the id
                                              out of every forest line
______________________________________________________________________________
"""
import os
import re

from .feature_forest   import forest_of_text, id_valid_f, ForestFault
from .feature_doc      import (doc_of_text, DocFault, CUSTOMERS,
                               RETIRED_MARK)
from .feature_external import external_of_text, ExternalFault
from .feature_link_edit import (links_planned, write_atomic,
                                _LINK_LIST_RE, _QUOTED_RE)
from .finder           import (FOREST_FILE_NAME, DOC_FILE_NAME,
                               EXTERNAL_FILE_NAME, CONF_NAME,
                               ROOT_CONF_NAME)
from .suggestion       import did_you_mean

FOREST_HEAD = (
    "hwut-feature-forest.csv -- THE FEATURE TREES (spec 43). One line per",
    "feature that has children:",
    "",
    "    <feature-id> : <child-id>, <child-id>, ...",
    "",
    "A feature id is '[A-Za-z0-9_-]+'. An id standing as no child is a ROOT.",
    "Every id stands once as a child (one parent); no circle. What a feature",
    "is, is said in 'hwut-feature-doc.dat'; a retired one stands in no line.",
)
DOC_HEAD = (
    "hwut-feature-doc.dat -- WHAT THE FEATURES ARE (spec 43). One block per",
    "feature, headed '[[<id>]]' -- or '[[<id> to <audience>, ...]]',",
    "'[[<id> not <audience>, ...]]', '[[<id>:retired]]'; '[[CUSTOMERS]]'",
    "declares the audiences. A block: an optional 'documents:' line (paths",
    "from this file's directory, ',' between), then the prose -- its first",
    "line the title, the rest the doc.",
)


class ActRefused(Exception):
    """The act is refused; nothing was written. The text says why."""


def _text_of(path):
    """RETURN: str, the content of 'path'; '' where it does not stand."""
    if not os.path.isfile(path): return ""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _head_text(line_tuple):
    """RETURN: str, 'line_tuple' as '# ' comment lines, then a blank."""
    return "".join("# %s\n" % each if each else "#\n"
                   for each in line_tuple) + "\n"


def init(top):
    """
    RETURN: list of str, one line per file written: an empty forest and an
            empty doc file beside the root at 'top', each where none stands.
            Raises ActRefused where both stand already.
    """
    line_list = []
    for name, head in ((FOREST_FILE_NAME, FOREST_HEAD),
                       (DOC_FILE_NAME, DOC_HEAD)):
        path = os.path.join(top, name)
        if os.path.exists(path): continue
        write_atomic(path, _head_text(head))
        line_list.append("'%s' written" % name)
    if not line_list:
        raise ActRefused("'%s' and '%s' stand already"
                         % (FOREST_FILE_NAME, DOC_FILE_NAME))
    return line_list


class _Files:
    """The three files of 'top' as text, read and checked once."""

    def __init__(self, top):
        """RETURN: None. Raises ActRefused where the forest does not
        stand, or a file states a fault."""
        self.top    = top
        self.forest_text   = _text_of(os.path.join(top, FOREST_FILE_NAME))
        self.doc_text      = _text_of(os.path.join(top, DOC_FILE_NAME))
        self.external_text = _text_of(os.path.join(top, EXTERNAL_FILE_NAME))
        if not os.path.isfile(os.path.join(top, FOREST_FILE_NAME)):
            raise ActRefused("no '%s' stands at '%s' => hwut.features.init"
                             % (FOREST_FILE_NAME, top))
        self.forest, self.doc = self.checked(self.forest_text,
                                             self.doc_text,
                                             self.external_text)

    @staticmethod
    def checked(forest_text, doc_text, external_text):
        """RETURN: (CForest, CDoc), what the texts state. Raises
        ActRefused, naming the fault, where one states one."""
        try:
            forest = forest_of_text(forest_text, FOREST_FILE_NAME)
            doc    = doc_of_text(doc_text, forest, DOC_FILE_NAME)
            external_of_text(external_text, forest, EXTERNAL_FILE_NAME)
        except (ForestFault, DocFault, ExternalFault) as fault:
            raise ActRefused(str(fault)) from fault
        return forest, doc

    def known_set(self):
        """RETURN: set of str, the ids of the forest and the doc file,
        the retired included -- the prototypes and their members too
        (intend/44), not the instances: an instance follows its owner and
        its member."""
        return {each for each in set(self.forest.id_set)
                | set(self.doc.entry_db) | set(self.doc.retired_db)
                if not each.startswith("+") and "+" not in each} \
               | set(self.forest.prototype_db) | set(self.forest.member_of)

    def written(self, forest_text, doc_text, external_text):
        """RETURN: list of str, a line per file whose text changes, each
        written -- after the new texts were checked (ActRefused)."""
        self.checked(forest_text, doc_text, external_text)
        line_list = []
        for name, old, new in ((FOREST_FILE_NAME, self.forest_text,
                                forest_text),
                               (DOC_FILE_NAME, self.doc_text, doc_text),
                               (EXTERNAL_FILE_NAME, self.external_text,
                                external_text)):
            if old == new: continue
            write_atomic(os.path.join(self.top, name), new)
            line_list.append("    %s" % name)
        return line_list


def _id_re(feature_id):
    """RETURN: re.Pattern, 'feature_id' as a whole id: no id letter
    before or after it."""
    return re.compile(r"(?<![A-Za-z0-9_\-])%s(?![A-Za-z0-9_\-])"
                      % re.escape(feature_id))


def _forest_renamed(text, old, new):
    """RETURN: str, the forest 'text' with the id 'old' written 'new' on
    both sides of every line; comments untouched."""
    pattern, result = _id_re(old), []
    for line in text.splitlines(keepends=True):
        body, mark, comment = line.partition("#")
        result.append(pattern.sub(new, body) + mark + comment)
    return "".join(result)


_HEADING_LINE_RE = re.compile(r"\[\[\s*([A-Za-z0-9_\-+]+)(.*)\]\]\s*\Z")


def _doc_renamed(text, old, new):
    """RETURN: str, the doc 'text' with 'old' written 'new' wherever it
    stands as a whole id in a heading's name -- '[[old]]', '[[old to
    ...]]', '[[old:retired]]', '[[+old]]', '[[<owner>+old]]',
    '[[old+<id>]]'; the prose and the audiences untouched."""
    pattern, result = _id_re(old), []
    for line in text.splitlines(keepends=True):
        found = _HEADING_LINE_RE.match(line.strip()) \
                if line.startswith("[[") else None
        if found is not None and pattern.search(found.group(1)):
            line = line.replace("[[" + found.group(1),
                                "[[" + pattern.sub(new, found.group(1)), 1)
        result.append(line)
    return "".join(result)


def _external_renamed(text, old, new):
    """RETURN: str, the map 'text' with 'old' written 'new' in the left
    column; the outside's names untouched."""
    result = []
    for line in text.splitlines(keepends=True):
        ours, mark, theirs = line.partition(";")
        if mark and _id_re(old).search(ours.split("#", 1)[0]):
            line = _id_re(old).sub(new, ours) + mark + theirs
        result.append(line)
    return "".join(result)


def _conf_links_planned(top, map_f):
    """RETURN: dict, path -> new text: every 'hwut.conf' and
    'hwut-root.conf' below 'top' (a bubble with a forest of its own not
    entered) whose 'features = [...]' lists 'map_f' changes -- the links
    of the applications a conf declares."""
    from .tree_explorer import forest_owner_f
    plan_db = {}
    for here, directory_list, file_list in os.walk(top):
        directory_list[:] = sorted(
            each for each in directory_list if not each.startswith(".")
            and each not in ("TMP", "OUT", "__pycache__")
            and not forest_owner_f(os.path.join(here, each)))
        for name in file_list:
            if name not in (CONF_NAME, ROOT_CONF_NAME): continue
            path = os.path.join(here, name)
            before = _text_of(path)

            def quoted(match):
                found = map_f(match.group(1))
                return match.group(0) if found is None else '"%s"' % found

            after = _LINK_LIST_RE.sub(
                lambda m: _QUOTED_RE.sub(quoted, m.group(0)), before)
            if after != before: plan_db[path] = after
    return plan_db


def rename(top, old, new):
    """
    RETURN: list of str, what was done: the id 'old' written 'new' IN ONE
            STEP in every reference (t-4) -- both sides of the forest's
            lines, the doc file's headings, the map's left column, the
            test headers' and the confs' 'features = [...]'. The outside's
            names are untouched: that is the map's point (T-e).

    Raises ActRefused where 'old' stands nowhere, 'new' is no id, is
    'CUSTOMERS', or stands already; nothing is written then.
    """
    files = _Files(top)
    known = files.known_set()
    if old not in known:
        raise ActRefused("'%s' stands in no forest line and no doc block"
                         "%s" % (old, did_you_mean(old, sorted(known))))
    if not id_valid_f(new):
        raise ActRefused("'%s' is no feature id -- '[A-Za-z0-9_-]+'" % new)
    if new == CUSTOMERS:
        raise ActRefused("'CUSTOMERS' is reserved and no feature id")
    if new in known:
        raise ActRefused("'%s' stands already" % new)
    from .tree_explorer import forest_gate_of
    pattern = _id_re(old)

    def mapped(link):
        """RETURN: str, 'link' with 'old' written 'new' where it stands as
        a whole id -- a feature, an owner, a member; None, untouched."""
        return pattern.sub(new, link) if pattern.search(link) else None

    plan_db = links_planned(top, mapped, bubble_gate=forest_gate_of(top))
    plan_db.update(_conf_links_planned(top, mapped))
    line_list = ["renamed  %s -> %s" % (old, new)]
    line_list += files.written(_forest_renamed(files.forest_text, old, new),
                               _doc_renamed(files.doc_text, old, new),
                               _external_renamed(files.external_text, old,
                                                 new))
    for source in sorted(plan_db):
        write_atomic(source, plan_db[source])
        line_list.append("    link renamed in %s"
                         % os.path.relpath(source, top).replace(os.sep, "/"))
    return line_list


def _forest_without(text, feature_id):
    """RETURN: str, the forest 'text' with 'feature_id' taken out of the
    line that names it as a child -- that line dropped where it names no
    other child; every other line byte for byte."""
    result = []
    for line in text.splitlines(keepends=True):
        body, mark, comment = line.partition("#")
        if ":" not in body:
            result.append(line)
            continue
        head, colon, tail = body.partition(":")
        child_list = [each.strip() for each in tail.split(",")]
        if feature_id not in child_list:
            result.append(line)
            continue
        child_list.remove(feature_id)
        end = "\n" if line.endswith("\n") else ""
        if child_list:
            result.append("%s%s %s%s%s" % (head, colon, ", ".join(child_list),
                                           " " + mark + comment.rstrip("\n")
                                           if mark else "", end))
        elif mark:
            result.append(mark + comment)
    return "".join(result)


def _doc_retired(text, doc, feature_id):
    """RETURN: str, the doc 'text' with the heading of 'feature_id' written
    '[[<id>:retired]]' (its audiences dropped: a retired claim concerns
    nobody); a retired block of its own appended where it had none."""
    if feature_id not in doc.entry_db:
        return text.rstrip("\n") + "\n\n[[%s%s]]\n" % (feature_id,
                                                       RETIRED_MARK)
    result, done = [], False
    for line in text.splitlines(keepends=True):
        found = _HEADING_LINE_RE.match(line.strip()) \
                if line.startswith("[[") else None
        if not done and found is not None and found.group(1) == feature_id:
            end  = "\n" if line.endswith("\n") else ""
            line = "[[%s%s]]%s" % (feature_id, RETIRED_MARK, end)
            done = True
        result.append(line)
    return "".join(result)


def _member_retired(files, member):
    """
    RETURN: list of str, what was done: the member 'member' taken out of
            its prototype's line and its block headed '[[<id>:retired]]'
            -- in every instance at once (intend/44 p-7); a link to an
            instance of it names a retired claim from then on.

    Raises ActRefused where it is its prototype's last member (the
    prototype would declare nothing), where a block of one of its
    instances stands, or where the map names an instance; nothing is
    written then.
    """
    prototype = files.forest.member_of[member]
    right = files.forest.prototype_db[prototype]
    if right == (member,):
        raise ActRefused("'%s' is the last member of '+%s' -- strike the "
                         "prototype and its '+%s' aggregations by hand"
                         % (member, prototype, prototype))
    suffix = "+" + member
    instance_list = sorted(each for each in files.doc.entry_db
                           if each.endswith(suffix) and each != member)
    if instance_list:
        raise ActRefused("'%s': blocks of its instances stand: %s -- take "
                         "them out first" % (member, ", ".join(
                             "[[%s]]" % each for each in instance_list)))
    if re.search(r"(?m)^\s*[A-Za-z0-9_\-]+%s\s*;" % re.escape(suffix),
                 files.external_text):
        raise ActRefused("'%s': an instance is named in '%s': the outside "
                         "was told it -- take its line out first"
                         % (member, EXTERNAL_FILE_NAME))
    line_list = ["retired  %s (a member of '+%s', in every instance)"
                 % (member, prototype)]
    line_list += files.written(_forest_without(files.forest_text, member),
                               _doc_retired(files.doc_text, files.doc,
                                            member),
                               files.external_text)
    return line_list


def retire(top, feature_id):
    """
    RETURN: list of str, what was done: the doc block of 'feature_id'
            headed '[[<id>:retired]]' and the id taken out of every forest
            line (T-s) -- its claim kept as it was, nothing below it.

    Raises ActRefused where the id stands nowhere, is retired already,
    has children (a retired claim has nothing below it: retire them
    first), or the map names it; nothing is written then.
    """
    files = _Files(top)
    if feature_id in files.doc.retired_db:
        raise ActRefused("'%s' is retired already" % feature_id)
    if feature_id in files.forest.member_of:
        return _member_retired(files, feature_id)
    if feature_id in files.forest.prototype_db or "+" in feature_id:
        raise ActRefused("'%s' is a prototype or an instance: no claim of "
                         "its own -- retire its members, or strike the "
                         "'+<prototype>' from its owner's line by hand"
                         % feature_id)
    known = set(files.forest.id_set) | set(files.doc.entry_db)
    if feature_id not in known:
        raise ActRefused("'%s' stands in no forest line and no doc block%s"
                         % (feature_id, did_you_mean(feature_id,
                                                     sorted(known))))
    child_tuple = files.forest.children_of.get(feature_id, ())
    if child_tuple:
        raise ActRefused("'%s' has children: %s -- a retired claim has "
                         "nothing below it; retire them first"
                         % (feature_id, ", ".join(child_tuple)))
    if re.search(r"(?m)^\s*%s\s*;" % re.escape(feature_id),
                 files.external_text):
        raise ActRefused("'%s' is named in '%s': the outside was told it "
                         "-- take its line out first"
                         % (feature_id, EXTERNAL_FILE_NAME))
    line_list = ["retired  %s" % feature_id]
    line_list += files.written(_forest_without(files.forest_text,
                                               feature_id),
                               _doc_retired(files.doc_text, files.doc,
                                            feature_id),
                               files.external_text)
    return line_list
