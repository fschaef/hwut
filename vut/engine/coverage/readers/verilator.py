"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR VERILATOR'S NATIVE '.dat' -- the artifact the
         lcov export flattens, read whole.

DESCRIPTION
       WHAT IS READ, witnessed (WITNESS-hdl-artifacts.txt): a text file
       headed '# SystemC::Coverage-3', one point per line --

           C '<key>' <count>

       -- where the key is a sequence of '\\x01<field>\\x02<value>' pairs:
       'f' the file, 'l' the line, 'page' the coverage KIND plus the
       module, 'o' the point's own name, 'S' an optional line span, 'h'
       the instance hierarchy. Four kinds are read:

           v_line     EX is every point's span; CV where the count is
                      above zero.
           v_branch   the ARMS of one decision, each a point of its own
                      seated at the decision's line -- folded into the
                      'branch' measure: arms taken of arms there are.
           v_toggle   one point PER BIT ('count[3]'), seated at the
                      signal's DECLARATION line -- the 'toggle' measure,
                      covered where the count is above zero.
           v_user     a 'cover property', seated at its statement -- the
                      'cover' measure.

       THE INSTANCE QUESTION IS THE TOOL'S, ALREADY ANSWERED: verilator
       merges instances per declaration before writing ('h' reads
       'TOP.tb.dut.*', a literal wildcard, counts summed). A point named
       twice -- two reports, or per-instance wires of one parent -- has
       its counts ADDED, which is what two observations of one point
       mean.

       WHY THIS READER EXISTS BESIDE THE LCOV ROAD: the export
       ('verilator_coverage --write-info') MISFILES toggle and user
       points as line coverage -- a declaration line reads uncovered
       because one bit never toggled (finding 3, pinned in the
       'verilator' test choice). The registry road for the export says
       '--coverage-line'; THIS reader takes the full '--coverage'
       artifact and keeps every kind on its own axis.

       A FILE WITHOUT THE HEADER IS LEFT ALONE: '.dat' is anybody's
       suffix, and a document this reader cannot vouch for is not
       half-read.
______________________________________________________________________________
"""
import os

from ..reader import (CCoverageFramework, CCoverageFormat,
                      register, relative_path, wanted)
from ..record import ranges_of, FileCoverage


DAT_SUFFIX = (".dat",)
HEADER     = "# SystemC::Coverage-3"

_PAGE_LINE, _PAGE_BRANCH, _PAGE_TOGGLE, _PAGE_USER = (
    "v_line", "v_branch", "v_toggle", "v_user")


class VerilatorFormat(CCoverageFormat):
    """Verilator's native coverage data file."""
    name = "verilator-dat"

    suffix = DAT_SUFFIX

    def absorb(self, accumulator, path):
        """RETURN: None. One '.dat' folded in -- line coverage, branch
        arms, toggle bits, cover properties."""
        _absorb(accumulator, path)

    def record_of(self, accumulator, source_root, config, counts_f):
        """RETURN: CoverageRecord over the unioned '.dat' files."""
        return _record_of(self, accumulator, source_root, config, counts_f)


class VerilatorFramework(CCoverageFramework):
    """verilator: invocation; reads VerilatorFormat.

    NOTHING TO WRAP (the base's default): instrumentation happens when
    the model is VERILATED ('--coverage' on the verilator command
    line), not when it runs -- the build's business, as the JaCoCo
    agent is the java command line's. The run then writes the '.dat'
    itself.
    """
    name   = "verilator"
    format = VerilatorFormat()




def _absorb(point_db, path):
    """
    RETURN: None. Folds one '.dat' into 'point_db':
            (file, kind, line, name) -> count, counts ADDED on a point
            named twice.

    A file whose first line is not the witnessed header is LEFT ALONE.
    """
    try:
        with open(path, encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read()
    except OSError:
        return
    line_list = text.splitlines()
    if not line_list or line_list[0].strip() != HEADER: return

    for raw in line_list[1:]:
        raw = raw.strip()
        if not raw.startswith("C '"): continue
        key_text, _, count_text = raw[3:].rpartition("' ")
        try:    count = int(count_text)
        except ValueError: continue

        field_db = {}
        for piece in key_text.split("\x01"):
            name, _, value = piece.partition("\x02")
            if name: field_db[name] = value

        page = field_db.get("page", "")
        kind = page.split("/", 1)[0]
        if kind not in (_PAGE_LINE, _PAGE_BRANCH, _PAGE_TOGGLE,
                        _PAGE_USER):
            continue
        source = field_db.get("f")
        try:    line = int(field_db.get("l", ""))
        except ValueError: continue
        if not source: continue

        if kind == _PAGE_LINE:
            for n in _span_iterable(field_db.get("S"), line):
                key = (source, kind, n, "")
                point_db[key] = point_db.get(key, 0) + count
        else:
            #  A branch ARM'S own name is 'if'/'else'; two arms of one
            #  decision share 'o' across DIFFERENT decisions, so the
            #  arm is keyed by its span too, which verilator writes
            #  distinctly per arm.
            name = field_db.get("o", "")
            if kind == _PAGE_BRANCH:
                name = "%s@%s" % (name, field_db.get("S", ""))
            key = (source, kind, line, name)
            point_db[key] = point_db.get(key, 0) + count


def _span_iterable(span_text, fallback_line):
    """
    RETURN: iterable of int, the lines a 'S' span names ('11', '15-16'),
            or the point's own line where no span stands.
    """
    if not span_text: return (fallback_line,)
    result = []
    for piece in span_text.split(","):
        begin_text, _, end_text = piece.partition("-")
        try:
            begin = int(begin_text)
            end   = int(end_text) if end_text else begin
        except ValueError:
            continue
        result.extend(range(begin, end + 1))
    return result or (fallback_line,)


def _record_of(fmt, point_db, source_root, config, counts_f):
    """
    RETURN: CoverageRecord over the absorbed points, one FileCoverage
            per source file, each measure on its own axis.
    """
    from ..measure import BRANCH, TOGGLE, COVER               # noqa: F401
    by_file = {}
    for (source, kind, line, name), count in point_db.items():
        by_file.setdefault(source, {}).setdefault(kind, {})[
            (line, name)] = count

    file_db = {}
    for raw_path in sorted(by_file):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        kind_db = by_file[raw_path]

        line_db    = {line: count for (line, _), count
                      in kind_db.get(_PAGE_LINE, {}).items()}
        executable = sorted(line_db)
        covered    = [n for n in executable if line_db[n] > 0]

        count_list = None
        if counts_f and covered:
            count_list = tuple(max(line_db[n]
                                   for n in range(begin, end)
                                   if n in line_db)
                               for begin, end in ranges_of(covered))

        measure_db = {}
        arm_db = kind_db.get(_PAGE_BRANCH, {})
        if arm_db:
            decision_db = {}
            for (line, _), count in arm_db.items():
                total, taken = decision_db.get(line, (0, 0))
                decision_db[line] = (total + 1,
                                     taken + (1 if count > 0 else 0))
            measure_db["branch"] = tuple(
                (line, taken, total)
                for line, (total, taken) in sorted(decision_db.items()))
        for kind, measure_name in ((_PAGE_TOGGLE, "toggle"),
                                   (_PAGE_USER,   "cover")):
            named_db = kind_db.get(kind, {})
            if not named_db: continue
            measure_db[measure_name] = tuple(sorted(
                (line, name, 1 if count > 0 else 0, 1)
                for (line, name), count in named_db.items()))

        file_db[path] = FileCoverage(path, ranges_of(executable),
                                     ranges_of(covered), count_list,
                                     measure_db)

    return fmt.record_from(file_db, counts_f, _language_of(file_db))


def _language_of(file_db):
    """
    RETURN: str, the language the report is OF, from the extensions it
            names; 'unknown' where they disagree or say nothing.
            Verilog and systemverilog MIX by design -- one simulation --
            and the mix reads 'verilog': the subset relation makes that
            honest where java/kotlin's would not be.
    """
    suffix_db = {".v": "verilog", ".vh": "verilog",
                 ".sv": "systemverilog", ".svh": "systemverilog"}
    name_set = set()
    for path in file_db:
        name = suffix_db.get(os.path.splitext(path)[1].lower())
        if name is not None: name_set.add(name)
    if not name_set:                      return "unknown"
    if name_set == {"verilog", "systemverilog"}: return "verilog"
    return name_set.pop() if len(name_set) == 1 else "unknown"


register(VerilatorFramework())
