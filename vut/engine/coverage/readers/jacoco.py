"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR JACOCO XML -- java, kotlin, scala, groovy.

DESCRIPTION
       WHAT IS READ, per the report DTD ("-//JACOCO//DTD Report 1.1//EN"):

           <report name="...">
             <package name="org/example">          VM notation: '/' already
               <sourcefile name="App.java">
                 <line nr="12" mi="0" ci="3" mb="1" cb="1"/>
                 <counter type="LINE" missed="1" covered="10"/>

           mi  missed instructions      ci  covered instructions
           mb  missed branches          cb  covered branches

       THE PATH IS BUILT, NOT FOUND. A '<sourcefile>' carries only its
       LOCAL name; the directory is its '<package>' name, in VM notation
       -- which already uses '/'. 'org/example' + 'App.java'. A package
       named '' is the default package and contributes nothing. This is
       the same shape go's import path has: the format names a MODULE
       position, not a file position, and the reader must reconstruct
       one.

       EX IS EVERY '<line>': the element exists because JaCoCo assigned
       instructions to that source line, which is what makes it
       executable. CV is 'ci > 0' -- JaCoCo's own words: "A source line
       is considered executed when at least one instruction that is
       assigned to this line has been executed." A line with 'ci > 0'
       and 'mi > 0' is PARTIALLY covered, and this record calls it
       covered: partial coverage is an INSTRUCTION fact, and the
       instruction axis is not one this record holds.

       BRANCHES: total is 'mb + cb', taken is 'cb', and the point exists
       only where that total is above zero -- most lines carry
       'mb="0" cb="0"', which is not a decision with no arms taken but no
       decision at all.

       '<counter>' IS A SUMMARY AND IS NOT CONSULTED. It is derived by
       JaCoCo from the very '<line>' elements beside it; a summary that
       disagreed with its own detail would have to be adjudicated, and
       there is no honest way to do that. It IS used in the TEST, as a
       cross-check on the fixture -- which is a different job.

       '<class>' AND '<method>' ARE NOT READ. They carry counters, not
       line detail, and a method is a different key.

       A '<line>' WITH NEITHER 'ci' NOR 'mi' IS REFUSED, by name. Both
       are '#IMPLIED' in the DTD, so a document without them is
       well-formed -- and it cannot say which lines ran. Reading it would
       mean calling every line uncovered (a false red that makes the
       measurement useless) or every line covered (a false green). Some
       third-party writers of this format do emit such documents; they
       are refused rather than half-read.
______________________________________________________________________________
"""
import os
import xml.etree.ElementTree as ElementTree

from ..configuration import CoverageRefused
from ..reader import (CCoverageFramework, CCoverageFormat,
                      line_record_of, register, artifact_directory_of)


XML_SUFFIX = (".xml",)


class JacocoFormat(CCoverageFormat):
    """JaCoCo's XML report."""
    name = "jacoco-xml"

    def read(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of every JaCoCo report under the artifact
                directory, unioned.
                None, where none stands -- ABSENT.

        Raises CoverageRefused where a report carries '<line>' elements
        with no instruction counts: it is well-formed and cannot say
        which lines ran.
        """
        entry_db = {}
        directory = artifact_directory_of(work_dir)
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if not name.endswith(XML_SUFFIX): continue
                path = os.path.join(directory, name)
                root = _read(path)
                if root is None: continue
                _absorb(entry_db, root, name)
        if not entry_db: return None

        counts_f = bool(config is not None and config.counts)
        return _record_of(self, entry_db, source_root, config, counts_f)


class JacocoFramework(CCoverageFramework):
    """jacoco: invocation; reads JacocoFormat."""
    name   = "jacoco"
    format = JacocoFormat()

    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], 'argv' unchanged.

        JaCoCo instruments through a JVM AGENT ('-javaagent:jacocoagent
        .jar'), which belongs to the java command line the build already
        writes -- not to a wrapper around it. Whether the agent was
        attached is the BUILD's business, and this reader reports its
        absence by finding no report.
        """
        return list(argv)

    def report_argv(self, config, work_dir):
        """
        RETURN: None.

        The agent leaves 'jacoco.exec', which IS binary and DOES need a
        second call -- 'java -jar jacococli.jar report ...'. But that
        call needs the CLASS FILES and the SOURCE ROOTS the build used,
        and this component knows neither. Naming a call that could not
        run would be worse than naming none: the build writes the xml,
        as it already writes the jar.
        """
        return None


def _read(path):
    """
    RETURN: Element, the '<report>' root of a JACOCO document.
            None, where the file is not one -- a Cobertura '<coverage>',
            or an xml that is no coverage at all. Left alone rather than
            half-understood.
    """
    try:    root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError):
        return None
    return root if root.tag == "report" else None


def _absorb(entry_db, root, origin_name):
    """
    RETURN: None. Folds one report into 'entry_db':
            path -> {line: [ci, mi, cb, mb]}.

    Packages may NEST inside groups, so every '<package>' in the tree is
    taken, wherever it stands. A file named in two reports is UNIONED:
    instructions and branches add, which is what two runs of one file
    mean on those axes.

    Raises CoverageRefused on a '<line>' carrying neither 'ci' nor 'mi'.
    """
    for package_node in root.iter("package"):
        prefix = (package_node.get("name") or "").strip("/")
        for file_node in package_node.iter("sourcefile"):
            name = file_node.get("name")
            if not name: continue
            path = "%s/%s" % (prefix, name) if prefix else name
            standing = entry_db.setdefault(path, {})
            for line_node in file_node.iter("line"):
                try:    number = int(line_node.get("nr", ""))
                except ValueError: continue

                covered_text = line_node.get("ci")
                missed_text  = line_node.get("mi")
                if covered_text is None and missed_text is None:
                    raise CoverageRefused(
                        "'%s' names line %i of '%s' with neither 'ci' nor "
                        "'mi': the report is well-formed and cannot say "
                        "whether the line ran. A reader over it would have "
                        "to call every line covered or every line missed, "
                        "and both are inventions."
                        % (origin_name, number, path))

                was = standing.get(number) or [0, 0, 0, 0]
                was[0] += _number(covered_text)
                was[1] += _number(missed_text)
                was[2] += _number(line_node.get("cb"))
                was[3] += _number(line_node.get("mb"))
                standing[number] = was


def _number(text):
    """RETURN: int, the attribute's value; 0 where it is absent or spells
    no number -- an absent count is a count of none, which is what the
    DTD's '#IMPLIED' means here."""
    if text is None: return 0
    try:    return int(text)
    except ValueError: return 0


def _record_of(fmt, entry_db, source_root, config, counts_f):
    """
    RETURN: CoverageRecord, with the branch measurement seated beside the
            line one.

    'counts' are INSTRUCTION counts, not execution counts: JaCoCo says
    how many instructions of a line ran, never how often the line did. So
    they are recorded only where counts were asked for, and what they
    mean is stated here rather than left to look like hit counts.
    """
    def branch_of(line_db, executable):
        """RETURN: tuple, (line, covered, total) per line that carries
        a branch at all; JaCoCo counts COVERED and MISSED, so the
        total is their sum and a line with neither has no branch."""
        return tuple((n, line_db[n][2], line_db[n][2] + line_db[n][3])
                     for n in executable
                     if line_db[n][2] + line_db[n][3] > 0)

    return line_record_of(fmt, entry_db, config, source_root, counts_f,
                          _language_of, branch_of)


def _language_of(file_db):
    """
    RETURN: str, the language the report is OF, from the extensions it
            names; 'unknown' where they disagree or say nothing.

    A JaCoCo report covers the JVM, not one language of it: java, kotlin,
    scala and groovy compile to the same class files and appear in the
    same report. Where they MIX, 'unknown' is said rather than one of
    them chosen.
    """
    suffix_db = {".java": "java", ".kt": "kotlin", ".kts": "kotlin",
                 ".scala": "scala", ".groovy": "groovy"}
    name_set = set()
    for path in file_db:
        name = suffix_db.get(os.path.splitext(path)[1].lower())
        if name is not None: name_set.add(name)
    return name_set.pop() if len(name_set) == 1 else "unknown"


register(JacocoFramework())
