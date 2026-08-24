"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR COBERTURA XML -- the SECOND lingua franca.

DESCRIPTION
       ONE FORMAT, MANY WORLDS. Cobertura's DTD outlived Cobertura: it is
       what Java's tooling exports for CI, what coverage.py writes as
       'coverage xml', what coverlet emits for .NET, and what PHP, Ruby
       and JavaScript tools offer beside their own. Nothing else this
       component reads has that reach.

       WHAT IS READ.

           <class filename="...">        the source file
             <lines>
               <line number="" hits=""                   -> EX, and CV
                     branch="true"                          where hits>0
                     condition-coverage="50% (1/2)"      -> BRANCH
                     missing-branches="5"/>                 (ignored)

       EX is every '<line>'; CV is every one whose 'hits' is not zero --
       the same two facts LCOV's 'DA' carries, in another spelling.

       THE BRANCH DATA IS KEPT, and this is the first reader that keeps
       any measurement beside lines. 'condition-coverage' carries the
       ratio TWICE -- as a percentage and as '(taken/total)' -- and the
       PAIR is read, never the percentage: a percentage has already
       thrown away the denominator, and 50% of two arms and 50% of eight
       are not the same fact. It becomes a 'branch' point
       ('measure.py'), and the record writes a 'BR' line.

       'missing-branches' names the DESTINATION LINES of the arms not
       taken. It is not read: a destination is not a decision, and the
       record has no key for it.

       WHAT IS IGNORED, AND WHY. Every 'line-rate', 'branch-rate',
       'lines-valid' and 'lines-covered' attribute is a SUMMARY of the
       detail below it. The detail is read and the summary is not
       consulted -- a summary that disagreed with its own lines would
       have to be adjudicated, and there is no honest way to do that.

       'complexity' is not coverage. '<methods>' is a different key.

       THE ROOT TAG IS CHECKED. A directory may hold a JaCoCo report
       ('<report>'), a Clover one ('<coverage>' with '<project>'), or an
       unrelated xml. Only '<coverage>' carrying '<packages>' is read;
       everything else is LEFT ALONE rather than half-understood.

       PATHS. 'filename' is usually relative to a '<sources><source>'
       root, and usually already the form a record wants. An absolute one
       is made relative to the test directory here.

       NO SECOND CALL. Whoever produced the xml did so as part of their
       own build or test run -- coverlet, gradle, 'coverage xml'. This
       component does not know how to drive five ecosystems, and
       pretending to would be a call that does nothing.
______________________________________________________________________________
"""
import os
import xml.etree.ElementTree as ElementTree

from ..reader import (I_Reader, register, artifact_directory_of,
                      relative_path, wanted, record_of)
from ..record import ranges_of, FileCoverage, CoverageRecord


XML_SUFFIX = (".xml",)


class CoberturaReader(I_Reader):
    """Cobertura XML, whoever wrote it."""
    name          = "cobertura"
    source_format = "cobertura-xml"

    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], 'argv' unchanged. The ecosystems that write
        this format drive their own runs; see the module header.
        """
        return list(argv)

    def report_argv(self, config, work_dir):
        """RETURN: None. The xml is text already."""
        return None

    def harvest(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of every Cobertura xml under the artifact
                directory, unioned.
                None, where none stands -- ABSENT.
        """
        entry_db = {}
        directory = artifact_directory_of(work_dir)
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if not name.endswith(XML_SUFFIX): continue
                root = _read(os.path.join(directory, name))
                if root is None: continue
                _absorb(entry_db, root)
        if not entry_db: return None

        counts_f = bool(config is not None and config.counts)
        return _record_of(self, entry_db, source_root, config, counts_f)


def _read(path):
    """
    RETURN: Element, the '<coverage>' root of a COBERTURA document.
            None, where the file is not one -- a JaCoCo '<report>', a
            Clover project, or an xml that is no coverage at all. Left
            alone rather than half-understood.
    """
    try:    root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError):
        return None
    if root.tag != "coverage":              return None
    if root.find("packages") is None:       return None
    return root


def _absorb(entry_db, root):
    """
    RETURN: None. Folds one document into 'entry_db':
            path -> {line: [hits, branch_taken|None, branch_total|None]}.

    A file named in two documents -- or twice in one -- is UNIONED: hits
    add, and the branch pair keeps the LARGER 'taken', which is the most
    that can honestly be said of two counts that do not carry WHICH arms
    (see 'measure.py').
    """
    for class_node in root.iter("class"):
        path = class_node.get("filename")
        if not path: continue
        standing = entry_db.setdefault(path, {})
        for line_node in class_node.iter("line"):
            try:    number = int(line_node.get("number", ""))
            except ValueError: continue
            try:    hits = int(line_node.get("hits", "0"))
            except ValueError: hits = 0

            was = standing.get(number)
            if was is None: was = [0, None, None]
            was[0] += hits

            taken, total = _condition_pair(line_node)
            if total is not None:
                was[1] = taken if was[1] is None else max(was[1], taken)
                was[2] = total if was[2] is None else max(was[2], total)
            standing[number] = was


def _condition_pair(line_node):
    """
    RETURN: [0] int, arms taken at this decision.
            [1] int, arms there are.
            (None, None) where the line carries no branch data.

    Read from the '(taken/total)' PART of 'condition-coverage', never
    from its percentage: a percentage has thrown the denominator away,
    and half of two arms is not half of eight.
    """
    if line_node.get("branch", "").lower() != "true": return (None, None)
    text = line_node.get("condition-coverage", "")
    begin = text.find("(")
    end   = text.find(")", begin + 1)
    if begin < 0 or end < 0: return (None, None)
    taken_text, _, total_text = text[begin + 1:end].partition("/")
    try:    return (int(taken_text), int(total_text))
    except ValueError:
        return (None, None)


def _record_of(reader, entry_db, source_root, config, counts_f):
    """
    RETURN: CoverageRecord, with the branch measurement seated beside the
            line one.

    Built here rather than through 'reader.record_of' because that helper
    knows only lines, and this is the first reader that carries a
    measure. What it does with the line part is identical.
    """
    file_db = {}
    for raw_path in sorted(entry_db):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        line_db    = entry_db[raw_path]
        executable = sorted(line_db)
        covered    = [n for n in executable if line_db[n][0] > 0]

        count_list = None
        if counts_f:
            count_list = tuple(max(line_db[n][0] for n in range(begin, end)
                                   if n in line_db)
                               for begin, end in ranges_of(covered))
        point_tuple = tuple((n, line_db[n][1], line_db[n][2])
                            for n in executable
                            if line_db[n][2] is not None)
        measure_db  = {"branch": point_tuple} if point_tuple else {}

        file_db[path] = FileCoverage(path, ranges_of(executable),
                                     ranges_of(covered), count_list,
                                     measure_db)

    return CoverageRecord(language = _language_of(file_db),
                          tool     = reader.name,
                          source   = reader.source_format,
                          counts_f = counts_f,
                          file_db  = file_db)


def _language_of(file_db):
    """
    RETURN: str, the language the report is OF, from the extensions it
            names; 'unknown' where they disagree or say nothing.

    A Cobertura document carries no language of its own -- which is the
    price of a format five ecosystems share. 'unknown' is SAID rather
    than defaulted to the commonest one.
    """
    suffix_db = {".py": "python", ".java": "java", ".kt": "kotlin",
                 ".scala": "scala", ".groovy": "groovy", ".cs": "c#",
                 ".vb": "vb.net", ".fs": "f#", ".rb": "ruby",
                 ".php": "php", ".js": "javascript", ".ts": "typescript",
                 ".c": "c", ".h": "c", ".cpp": "c++", ".cc": "c++"}
    name_set = set()
    for path in file_db:
        name = suffix_db.get(os.path.splitext(path)[1].lower())
        if name is not None: name_set.add(name)
    if len(name_set) == 1:       return name_set.pop()
    if name_set == {"c", "c++"}: return "c++"
    return "unknown"


register(CoberturaReader())
