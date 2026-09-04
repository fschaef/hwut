"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR UCIS XML -- Accellera's Unified Coverage
         Interoperability Standard, read against its own XSD.

DESCRIPTION
       WHAT IS READ, against 'ucis.xsd' (shipped with fvutils/pyucis) and
       a REAL artifact -- pyucis' own 'convert' converting this
       component's own witnessed 'verilator' fixture into UCIS XML
       (WITNESS-hdl-artifacts.txt, ucis addendum). Not fetched, not
       hand-written: an independent implementation's encoding, checked
       against the schema that defines it.

       THE ROOT NAMES A FLAT LIST. '<UCIS>' holds 'sourceFiles' (id ->
       name), 'historyNodes' (run metadata, not read), and a FLAT list
       of 'instanceCoverages' -- hierarchy rides in 'parentInstanceId',
       not in nesting, and is not needed here: every coverage kind below
       seats at a '<id file=".." line="..">' (STATEMENT_ID), and the
       record is keyed by FILE, so instances of one module UNION on
       their shared source position exactly as 'readers/verilator.py'
       unions them -- counts ADDED.

       THREE KINDS ARE READ, each carrying a STATEMENT_ID by the XSD's
       own definition:

           blockCoverage/statement    EX is every '<statement><id>';
                                      CV where its bin's
                                      'coverageCount' is above zero.
           branchCoverage//branch     ARMS at THEIR OWN line -- the
                                      witnessed artifact groups every
                                      decision of a file under one
                                      wrapping '<statement>', but each
                                      '<branch>' carries its OWN '<id>',
                                      so arms are grouped by THAT line,
                                      exactly as 'readers/verilator.py'
                                      groups '.dat' arms. Folds into the
                                      'branch' measure.
           toggleCoverage//toggleBit  ONE named point per bit, seated at
                                      its 'toggleObject''s '<id>', named
                                      OBJECT.BIT so two objects sharing a
                                      bit name stay distinct. WITNESSED,
                                      AND WORTH READING TWICE: the
                                      artifact this reader was checked
                                      against does not carry one bit per
                                      signal -- pyucis' 'vltcov' importer
                                      folds EVERY distinct signal of one
                                      source file into a SINGLE
                                      'toggleBit name="bit0"', each of
                                      the file's original points
                                      surviving only as one more
                                      '<toggle>' child under that one
                                      bit. This reader still reads
                                      exactly what stands -- a bit is
                                      COVERED where any of its '<toggle>'
                                      children carries a count above zero
                                      -- but what it then MEANS, from
                                      THIS importer, is 'something in
                                      this file toggled', not 'this named
                                      signal did'. The fault is the
                                      conversion's, not this reader's,
                                      and not UCIS's: the XSD gives every
                                      bit its own 'name' precisely so
                                      this need not happen.

       THREE KINDS ARE NOT READ, and the XSD says exactly why each one
       cannot seat where the three above do:

           conditionCoverage   EXPR carries a STATEMENT_ID and COULD
                               seat -- but no witnessed artifact
                               exercises it, and MC/DC's own encoding is
                               a stated debt already (measure.py,
                               RATIONALE D-2's neighbour): read it
                               against a real one, not invented here.
           fsmCoverage         Neither FSM nor FSM_STATE carries an
                               '<id>' anywhere in the XSD: FSM coverage
                               is line-less BY THE STANDARD'S OWN
                               DEFINITION, not merely by what this
                               session could witness (disc-9 stands).
           covergroupCoverage  CG_ID carries a STATEMENT_ID for the
                               COVERGROUP INSTANCE's declaration -- but
                               no bin beneath it (COVERPOINT_BIN,
                               CROSS_BIN) carries one of its own. Seating
                               every bin at the covergroup's ONE line
                               would silently collide distinct bins into
                               one name at one position: an invention,
                               refused by the same rule that refuses a
                               '<line>' with neither 'ci' nor 'mi'
                               (readers/jacoco.py). disc-9(b) is THIS,
                               precisely: not an availability gap, a
                               structural one the format itself states.

       A DOCUMENT WITHOUT THE ROOT TAG '<UCIS>' IS LEFT ALONE.
______________________________________________________________________________
"""
import os
from xml.etree import ElementTree

from ..reader import (CCoverageFramework, CCoverageFormat,
                      register, relative_path, wanted)
from ..record import ranges_of, FileCoverage


XML_SUFFIX = (".xml",)


class UcisFormat(CCoverageFormat):
    """UCIS XML, Accellera's interchange format."""
    name = "ucis-xml"

    suffix = XML_SUFFIX

    def absorb(self, accumulator, path):
        """RETURN: None. One UCIS document folded in -- line coverage,
        branch arms, toggle bits; a file that does not parse leaves the
        accumulator untouched."""
        root = _read(path)
        if root is not None: _absorb(accumulator, root)

    def record_of(self, accumulator, source_root, config, counts_f):
        """RETURN: CoverageRecord over the unioned documents."""
        return _record_of(self, accumulator, source_root, config, counts_f)


class UcisFramework(CCoverageFramework):
    """ucis: invocation; reads UcisFormat.

    NOTHING TO WRAP, AND NO SECOND CALL (the base's defaults): UCIS XML
    stands at the end of a CONVERSION step (a vendor export, or 'pyucis
    convert' over a native database) that this component neither runs
    nor names -- the same posture 'readers/jacoco.py' takes toward the
    agent that produces ITS artifact. Naming a call that could not run
    would be worse than naming none.
    """
    name   = "ucis"
    format = UcisFormat()




def _read(path):
    """RETURN: Element, the '<UCIS>' root. None, where the file is not
    one -- left alone rather than half-understood."""
    try:    root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError):
        return None
    return root if root.tag == "UCIS" else None


def _file_db_of(root):
    """RETURN: dict, str(id) -> fileName, from '<sourceFiles>'."""
    return {node.get("id"): node.get("fileName")
           for node in root.iter("sourceFiles") if node.get("id")}


def _absorb(entry_db, root):
    """
    RETURN: None. Folds one UCIS document into 'entry_db':
            path -> {'line': {line: count}, 'branch': {line: [names]},
                     'toggle': {(line, name): covered}}, counts and
            points ADDED/OR'd across instances of one file.
    """
    name_of = _file_db_of(root)

    def path_of(id_node):
        """RETURN: str, the source path a '<id>' names, or None."""
        return name_of.get(id_node.get("file")) if id_node is not None else None

    for instance in root.iter("instanceCoverages"):
        for block in instance.iter("blockCoverage"):
            for statement in block.iter("statement"):
                id_node = statement.find("id")
                path    = path_of(id_node)
                if path is None: continue
                line  = int(id_node.get("line"))
                count = _coverage_count(statement.find("bin"))
                standing = entry_db.setdefault(path, {}).setdefault("line", {})
                standing[line] = standing.get(line, 0) + count

        for branch_cov in instance.iter("branchCoverage"):
            for branch in branch_cov.iter("branch"):
                id_node = branch.find("id")
                path    = path_of(id_node)
                if path is None: continue
                line  = int(id_node.get("line"))
                count = _coverage_count(branch.find("branchBin"))
                standing = entry_db.setdefault(path, {}).setdefault("branch", {})
                standing.setdefault(line, []).append(count)

        for toggle_cov in instance.iter("toggleCoverage"):
            for toggle_obj in toggle_cov.iter("toggleObject"):
                id_node = toggle_obj.find("id")
                path    = path_of(id_node)
                if path is None: continue
                line = int(id_node.get("line"))
                for bit in toggle_obj.iter("toggleBit"):
                    name  = "%s.%s" % (toggle_obj.get("name"), bit.get("name"))
                    count = sum(_coverage_count(t.find("bin"))
                               for t in bit.findall("toggle"))
                    standing = entry_db.setdefault(path, {}).setdefault(
                        "toggle", {})
                    key = (line, name)
                    standing[key] = standing.get(key, 0) + count


def _coverage_count(bin_node):
    """RETURN: int, a '<bin><contents coverageCount="..."/></bin>'
    node's count; 0 where the node or the attribute is absent."""
    if bin_node is None: return 0
    contents = bin_node.find("contents")
    if contents is None: return 0
    try:    return int(contents.get("coverageCount", "0"))
    except ValueError: return 0


def _record_of(fmt, entry_db, source_root, config, counts_f):
    """RETURN: CoverageRecord over the absorbed points."""
    from ..measure import BRANCH, TOGGLE                      # noqa: F401
    file_db = {}
    for raw_path in sorted(entry_db):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        axis_db = entry_db[raw_path]

        line_db    = axis_db.get("line", {})
        executable = sorted(line_db)
        covered    = [n for n in executable if line_db[n] > 0]
        count_list = None
        if counts_f and covered:
            count_list = tuple(max(line_db[n] for n in range(begin, end)
                                   if n in line_db)
                               for begin, end in ranges_of(covered))

        measure_db = {}
        branch_db = axis_db.get("branch")
        if branch_db:
            measure_db["branch"] = tuple(
                (line, sum(1 for c in count_list if c > 0), len(count_list))
                for line, count_list in sorted(branch_db.items()))
        toggle_db = axis_db.get("toggle")
        if toggle_db:
            measure_db["toggle"] = tuple(sorted(
                (line, name, 1 if count > 0 else 0, 1)
                for (line, name), count in toggle_db.items()))

        file_db[path] = FileCoverage(path, ranges_of(executable),
                                     ranges_of(covered), count_list,
                                     measure_db)

    return fmt.record_from(file_db, counts_f, _language_of(file_db))


def _language_of(file_db):
    """
    RETURN: str, the language every source names, from its extension;
            'unknown' where they disagree or say nothing. UCIS is the
            JVM's situation generalised -- ONE database over an entire
            verification environment, so a mix is not an error to
            report, just a claim this header will not make.
    """
    suffix_db = {".v": "verilog", ".vh": "verilog",
                 ".sv": "systemverilog", ".svh": "systemverilog",
                 ".vhd": "vhdl", ".vhdl": "vhdl"}
    name_set = set()
    for path in file_db:
        name = suffix_db.get(os.path.splitext(path)[1].lower())
        if name is not None: name_set.add(name)
    if not name_set:                             return "unknown"
    if name_set <= {"verilog", "systemverilog"}:  return "verilog"
    return name_set.pop() if len(name_set) == 1 else "unknown"


register(UcisFramework())
