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
                     condition-coverage="50% (1/2)"      (ignored)
                     missing-branches="5"/>                 (ignored)

       EX is every '<line>'; CV is every one whose 'hits' is not zero --
       the same two facts LCOV's 'DA' carries, in another spelling.

       THE BRANCH DATA IS NOT KEPT (RATIONALE D-43). 'condition-coverage'
       carries a COUNT -- '(taken/total)' -- and the branch measure is
       the SET of arms taken, which can be unioned across runs where a
       count cannot. 'missing-branches' names the DESTINATION LINES of
       the arms not taken, but not the arms that were: the set is not
       recoverable from the pair. A format that cannot name its arms
       contributes no branch measure; the lines are read as ever.

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
from xml.etree import ElementTree

from .reader import (CCoverageFramework, CCoverageFormat,
                      line_record_of, language_of, register)


XML_SUFFIX = (".xml",)


class CoberturaFormat(CCoverageFormat):
    """Cobertura XML, whoever wrote it. Every xml under the artifact
    directory is unioned; the walk is the base's ('reader.py')."""
    name   = "cobertura-xml"
    suffix = XML_SUFFIX

    def absorb(self, accumulator, path):
        """RETURN: None. One Cobertura document folded in; a file that
        does not parse leaves the accumulator untouched."""
        root = _read(path)
        if root is not None: _absorb(accumulator, root)

    def record_of(self, accumulator, source_root, config, counts_f):
        """RETURN: CoverageRecord over the unioned documents."""
        return _record_of(self, accumulator, source_root, config, counts_f)


class CoberturaFramework(CCoverageFramework):
    """cobertura: invocation; reads CoberturaFormat.

    NOTHING TO WRAP, AND NO SECOND CALL (the base's defaults): the
    ecosystems that write this format drive their own runs (see the
    module header), and the xml is text already."""
    name   = "cobertura"
    format = CoberturaFormat()


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
            path -> {line: [hits]}.

    A file named in two documents -- or twice in one -- is UNIONED: hits
    add.
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
            if was is None: was = [0]
            was[0] += hits
            standing[number] = was


def _record_of(fmt, entry_db, source_root, config, counts_f):
    """
    RETURN: CoverageRecord of the lines the document gave; its branch
            data is not read (module header).
    """
    return line_record_of(fmt, entry_db, config, source_root, counts_f,
                          _language_of)


#  A COBERTURA DOCUMENT CARRIES NO LANGUAGE OF ITS OWN -- the price of
#  a format five ecosystems share. C and C++ appear in one report by
#  design and read 'c++'; any other mix reads 'unknown', SAID rather
#  than defaulted to the commonest member.
_SUFFIX_DB = {".py": "python", ".java": "java", ".kt": "kotlin",
              ".scala": "scala", ".groovy": "groovy", ".cs": "csharp",
              ".vb": "vbdotnet", ".fs": "fsharp", ".rb": "ruby",
              ".php": "php", ".js": "javascript", ".ts": "typescript",
              ".c": "c", ".h": "c", ".cpp": "c++", ".cc": "c++"}
_COLLAPSE_TUPLE = ((("c", "c++"), "c++"),)


def _language_of(file_db):
    """RETURN: str, the language the report is OF; 'unknown' where the
    extensions disagree or say nothing."""
    return language_of(file_db, _SUFFIX_DB, _COLLAPSE_TUPLE)


register(CoberturaFramework())
