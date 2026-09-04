"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE HOMOGENEOUS COVERAGE RECORD -- one shape, whatever tool and
         whatever language produced it.

DESCRIPTION
       LCOV'S SKELETON, NOT ITS GRAIN (RATIONALE D-5). Keyed by source
       file, merge is addition -- that much is LCOV's and it is good.
       What is dropped is the grain: every coverage format on the market
       writes ONE LINE OF TEXT PER SOURCE LINE, and that is where they
       all become slow and fat.

       Per source file, two sorted INTERVAL lists:

           EX   the ranges that COULD be hit
           CV   the ranges that WERE

       'uncovered = EX - CV'; the percentage is derived. Neither is
       stored: the pack wants the uncovered RANGES, which is what EX - CV
       already is, so there is no conversion at display time.

       THE RANGES ARE DELTA CODED. Each is written 'd+L': 'd' the gap
       from the previous range's end, 'L' the length. A range of ONE line
       -- the common case -- is written 'd' alone. Ranges are disjoint
       and never adjacent, so every 'd' is positive and small.

           lines 3..14 and 20..24     ->     3+12,5+5
           lines 3, 7, 40             ->     3,3,32

       HIT COUNTS are OPTIONAL and OFF by default; the header declares
       whether they are recorded, so a reader never guesses. A counted
       range is written 'd+L*C'.

       THE OTHER MEASUREMENTS -- branch, MC/DC, and whatever else is
       registered -- ride in their own lines, each under the TAG its
       measure claims ('measure.py'). This module dispatches on the tag
       and asks the measure; it knows what none of them MEAN. A file with
       no such measurement writes no such line, so a record of line
       coverage alone is byte-identical to what it was before any measure
       existed.

       AN INTERVAL IS HALF-OPEN: [begin, end), 'end' the first line AFTER
       the range. One convention, everywhere, so a length is a
       subtraction and a union is a comparison.
       THIS IS A CONVENTION FOR A DISCRETE DOMAIN, and it holds because
       line numbers are integers: 'end' is the first integer NOT in the
       set. It does not generalise to a continuous one -- there is no
       first real not in a set, adjacency stops being an arithmetic
       question, and a range type serving both would need explicit
       open/closed flags at each endpoint that nothing here would ever
       read.

       ABSENT AND EMPTY DO NOT COLLAPSE. A source file that was not
       measured has NO block. A source file measured and found to have no
       executable line has a block with an EMPTY 'EX'. The two are
       different facts and the record says which.

______________________________________________________________________________
"""
from dataclasses import dataclass, field
from typing      import Mapping

from .measure import (measure_of_tag, name_tuple as measure_name_tuple,
                      measure_of, tag_tuple)
from ..bookkeeper.api import (TestRunId, run_id_of_text,
                                      RunIdFault)


FORMAT_VERSION = 2

_COMMENT = "##"


class RecordFault(ValueError):
    """A record that cannot be read: a header that names no version, a
    range that spells no number, a delta that walks backwards. Named
    where it is met, never recovered from silently -- a coverage record
    read wrong is a coverage report that lies."""
    pass


class NotMergeable(RecordFault):
    """A union of ranges has no answer for what this record carries
    beside them. Refused by name rather than resolved by a rule nobody
    asked for -- a lower bound reported as a measurement is a false red,
    and becomes a false green the moment somebody 'fixes' it."""
    pass


class CountsNotMergeable(NotMergeable):
    """Merging is the UNION of ranges, and a union has no answer for two
    different hit counts over one line. Refused by name rather than
    resolved by a rule nobody asked for (DISCUSSIONS disc-5)."""
    pass


class MeasureNotMergeable(NotMergeable):
    """A MEASURE that declares itself unmergeable stands in this record.
    Branch and MC/DC both do: a COUNT of arms taken does not carry WHICH
    arms, so two runs covering different arms cannot be combined (see
    'measure.py')."""
    pass


# --------------------------------------------------------------- intervals

def ranges_of(line_iterable) -> tuple:
    """
    RETURN: tuple of (begin, end) half-open ranges, sorted and merged --
            every run of adjacent line numbers folded into one range.
            Empty tuple, if no line was given.

    Duplicates are absorbed; the input need not be sorted.
    """
    line_list = sorted(set(int(x) for x in line_iterable))
    if not line_list: return ()

    result = []
    begin  = line_list[0]
    end    = begin + 1
    for line in line_list[1:]:
        if line == end:
            end = line + 1
        else:
            result.append((begin, end))
            begin, end = line, line + 1
    result.append((begin, end))
    return tuple(result)


def line_n(range_tuple) -> int:
    """RETURN: int, how many lines the ranges cover in total."""
    return sum(end - begin for begin, end in range_tuple)


def union(a, b) -> tuple:
    """
    RETURN: tuple of (begin, end), every line of 'a' or of 'b', merged --
            THE MERGE OPERATION of this format. Associative and
            commutative, so an aggregate over many records does not
            depend on the order it walked them.
    """
    merged = sorted(tuple(a) + tuple(b))
    if not merged: return ()

    result = []
    begin, end = merged[0]
    for next_begin, next_end in merged[1:]:
        if next_begin <= end:
            end = max(end, next_end)
        else:
            result.append((begin, end))
            begin, end = next_begin, next_end
    result.append((begin, end))
    return tuple(result)


def subtract(a, b) -> tuple:
    """
    RETURN: tuple of (begin, end), every line of 'a' that is NOT in 'b'
            -- 'EX - CV' is the UNCOVERED set, which is what a
            conversation about a test actually needs ('these branches
            were never taken'). A percentage alone says nothing
            actionable.
    """
    result   = []
    hole_it  = iter(union(b, ()))
    hole     = next(hole_it, None)
    for begin, end in union(a, ()):
        cursor = begin
        while hole is not None and hole[0] < end:
            if hole[1] <= cursor:
                hole = next(hole_it, None)
                continue
            if hole[0] > cursor:
                result.append((cursor, min(hole[0], end)))
            cursor = max(cursor, hole[1])
            if cursor >= end: break
            hole = next(hole_it, None)
        if cursor < end:
            result.append((cursor, end))
    return tuple(result)


# ---------------------------------------------------------------- encoding

def encode(range_tuple, count_tuple=None) -> str:
    """
    RETURN: str, the ranges DELTA CODED: 'd+L' per range, 'd' alone where
            the range is one line, 'd+L*C' / 'd*C' where counts are
            given. Empty string, where there is no range.

    'd' is the gap from the previous range's END, so the first 'd' is the
    first line number itself and every later one is small.
    """
    if count_tuple is not None and len(count_tuple) != len(range_tuple):
        raise RecordFault("a count per range was promised, %i given for "
                          "%i ranges" % (len(count_tuple), len(range_tuple)))
    piece_list    = []
    previous_end  = 0
    for i, (begin, end) in enumerate(range_tuple):
        delta  = begin - previous_end
        length = end - begin
        text   = "%i" % delta if length == 1 else "%i+%i" % (delta, length)
        if count_tuple is not None:
            text += "*%i" % count_tuple[i]
        piece_list.append(text)
        previous_end = end
    return ",".join(piece_list)


def decode(text, counts_f=False):
    """
    RETURN: [0] tuple of (begin, end), the ranges the text spells.
            [1] tuple of int, the hit counts -- None where the header
                says none are recorded.

    Raises RecordFault on a piece that spells no range, or on a delta
    that would place a range at or before the previous one's end.
    """
    text = text.strip()
    if not text: return (), (() if counts_f else None)

    range_list   = []
    count_list   = []
    previous_end = 0
    for piece in text.split(","):
        body, _, count_text = piece.partition("*")
        if counts_f and not count_text:
            raise RecordFault("the header records counts, but '%s' "
                              "carries none" % piece)
        if not counts_f and count_text:
            raise RecordFault("the header records no counts, but '%s' "
                              "carries one" % piece)
        delta_text, _, length_text = body.partition("+")
        try:
            delta  = int(delta_text)
            length = int(length_text) if length_text else 1
            if counts_f: count_list.append(int(count_text))
        except ValueError:
            raise RecordFault("'%s' spells no range" % piece) from None
        if delta < 1:
            raise RecordFault("delta %i in '%s' does not advance: ranges "
                              "are disjoint and never adjacent"
                              % (delta, piece))
        if length < 1:
            raise RecordFault("length %i in '%s' covers no line"
                              % (length, piece))
        begin = previous_end + delta
        range_list.append((begin, begin + length))
        previous_end = begin + length
    return tuple(range_list), (tuple(count_list) if counts_f else None)


# ------------------------------------------------------------------ record

@dataclass(frozen=True)
class FileCoverage:
    """ONE SOURCE FILE'S coverage, as ranges.

    'path' is RELATIVE TO THE TEST DIRECTORY (RATIONALE D-4) -- which is
    what makes an aggregate over several directories possible, and what
    keeps one machine from being frozen into the record.
    """
    path:       str
    executable: tuple = ()
    covered:    tuple = ()
    counts:     tuple | None = None   # one per COVERED range, or None
    measure_db: Mapping[str, tuple] = field(default_factory=dict)
    #  THE OTHER MEASUREMENTS, by registered name: branch, mcdc, and
    #  whatever else was registered ('measure.py'). Empty is the common
    #  case and costs a record nothing: a measure with no point writes
    #  no line.

    @property
    def uncovered(self):
        """RETURN: tuple of (begin, end), the executable ranges never
        hit -- what a report shows."""
        return subtract(self.executable, self.covered)

    @property
    def ratio(self):
        """
        RETURN: float in [0.0, 1.0], covered lines over executable lines.
                None, where the file has NO executable line -- there is
                no ratio, and 1.0 would be a lie told in the green
                direction.
        """
        total = line_n(self.executable)
        if total == 0: return None
        return line_n(union(self.covered, ())) / float(total)


@dataclass(frozen=True)
class CoverageRecord:
    """A RUN'S coverage, homogeneous, whatever tool made it.

    THE HEADER NAMES ITS PROVENANCE (RATIONALE D-7): with a candidate
    list, which tool served is decided at RUN TIME by what the machine
    happens to have, and the homogeneous body looks the same whichever
    one it was. A later stage that must know would otherwise be guessing.

    Same law as the book entry: a record is HISTORY, and the
    configuration may have moved since.

    'run' NAMES THE RUNS THIS IS OF, as RUN IDS the register issued
    (bookkeeper B-2). In the store the key would do; away from the store
    the record would be anonymous, and an INDEX over many records could
    then only guess which run reached which line from the path it was
    found at. So the header carries them (RATIONALE D-8, D-18).

    A SET, not one id, because 'merge' unions records: a merged record
    is of several runs and its header says so. One run is the common
    case and spells one id.

    IDS, NOT NAMES: an id is issued once and never re-used, so a record
    that travelled decodes to the same test or to 'no longer
    registered', never to another test -- and a rename touches no record
    anywhere.

    A record fresh from a READER carries the EMPTY set: a reader knows
    the ARTIFACT, not the run, and the caller that holds the id seats it
    ('seated'). That absence is SPOKEN as '-' -- an empty field would be
    a byte nobody meant, and a header that merely looked complete.
    """
    language:  str
    tool:      str
    source:    str                          # the format the artifact was in
    counts_f:  bool                    = False
    file_db:   Mapping[str, FileCoverage] = field(default_factory=dict)
    version:   int                     = FORMAT_VERSION
    run:       frozenset               = frozenset()


def seated(record, run):
    """
    RETURN: CoverageRecord, the same record naming 'run' -- a TestRunId,
            or any iterable of them.

    THE ONE SEAM between a reader (which knows the artifact) and the
    caller that knows which run made it.
    """
    run_set = frozenset([run]) if isinstance(run, TestRunId) \
              else frozenset(run)
    return CoverageRecord(language = record.language,
                          tool     = record.tool,
                          source   = record.source,
                          counts_f = record.counts_f,
                          file_db  = record.file_db,
                          version  = record.version,
                          run      = run_set)


def run_text_of(run_set):
    """
    RETURN: str, the run ids sorted and comma separated -- the spelling
            a group table uses for a set.
            '-', where the set is empty: the record names no run.
    """
    return ",".join(str(r) for r in sorted(run_set)) if run_set else "-"


def run_set_of_text(text):
    """
    RETURN: frozenset of TestRunId, what the header's 'run:' spells;
            empty for '-'.

    Raises RecordFault where a word spells no run id -- naming the word,
    because a record whose attribution cannot be read must not be half
    read.
    """
    if text.strip() == "-": return frozenset()
    result = []
    for word in text.split(","):
        if not word.strip(): continue
        try:               result.append(run_id_of_text(word))
        except RunIdFault as fault:
            raise RecordFault("the header's 'run' names '%s': %s"
                              % (word.strip(), fault)) from None
    return frozenset(result)


def format_record(record) -> str:
    """
    RETURN: str, the record as it is stored -- header, then one block per
            source file, files in sorted order so two runs of one test
            produce the same bytes.
    """
    line_list = ["%sVUT-COVERAGE %i" % (_COMMENT, record.version),
                 "%srun:      %s"    % (_COMMENT,
                                        run_text_of(record.run)),
                 "%slanguage: %s"    % (_COMMENT, record.language),
                 "%stool:     %s"    % (_COMMENT, record.tool),
                 "%sformat:   %s"    % (_COMMENT, record.source),
                 "%scounts:   %s"    % (_COMMENT,
                                        "yes" if record.counts_f else "no")]
    for path in sorted(record.file_db):
        entry = record.file_db[path]
        line_list.append("SF:%s" % path)
        line_list.append("EX:%s" % encode(entry.executable))
        line_list.append("CV:%s" % encode(entry.covered,
                                          entry.counts
                                          if record.counts_f else None))
        #  THE OTHER MEASUREMENTS, in registered-name order so the bytes
        #  are stable. A measure with no point writes NO LINE: a record
        #  that measured only lines looks exactly as it did before any
        #  measure was registered.
        for name in measure_name_tuple():
            point_tuple = entry.measure_db.get(name)
            if not point_tuple: continue
            measure = measure_of(name)
            line_list.append("%s:%s" % (measure.tag,
                                        measure.encode(point_tuple)))
    return "\n".join(line_list) + "\n"


def parse_record(text):
    """
    RETURN: CoverageRecord, what the text says.

    Raises RecordFault naming the FIRST fault: an unknown version, a
    missing header field, a block whose 'EX' or 'CV' is absent. A
    coverage record half-read is a coverage report that lies, so nothing
    here recovers and carries on.
    """
    header  = {}
    version = None
    file_db = {}
    path    = None
    pending = {}

    def close():
        """RETURN: None. Seats the block being read, if there is one."""
        if path is None: return
        for key in ("EX", "CV"):
            if key not in pending:
                raise RecordFault("source file '%s' has no '%s' line"
                                  % (path, key))
        counts_f    = header.get("counts") == "yes"
        executable, _      = decode(pending["EX"])
        covered,    count_tuple = decode(pending["CV"], counts_f)
        measure_db = {}
        for tag, text in pending.items():
            if tag in ("EX", "CV"): continue
            measure = measure_of_tag(tag)
            measure_db[measure.name] = measure.decode(text)
        file_db[path] = FileCoverage(path, executable, covered, count_tuple,
                                     measure_db)

    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith(_COMMENT):
            body = line[len(_COMMENT):]
            if body.startswith("VUT-COVERAGE"):
                try:    version = int(body.split()[1])
                except (IndexError, ValueError):
                    raise RecordFault("the header names no format version") from None
                continue
            key, _, value = body.partition(":")
            header[key.strip()] = value.strip()
            continue
        key, _, value = line.partition(":")
        if key == "SF":
            close()
            path, pending = value, {}
        elif key in ("EX", "CV") or measure_of_tag(key) is not None:
            if path is None:
                raise RecordFault("'%s' stands before any 'SF'" % key)
            pending[key] = value
        else:
            raise RecordFault(
                "unknown record line '%s'; this build reads 'EX', 'CV' "
                "and %s" % (key, ", ".join("'%s'" % t
                                           for t in tag_tuple())))
    close()

    if version is None:
        raise RecordFault("the header names no format version")
    if version != FORMAT_VERSION:
        raise RecordFault("format version %i is not %i -- this reader "
                          "does not pretend to read it. Version 1 named "
                          "the run by NAME ('test:', 'choice:'); a "
                          "record names RUN IDS now (D-18)."
                          % (version, FORMAT_VERSION))
    for key in ("run", "language", "tool", "format", "counts"):
        if key not in header:
            raise RecordFault("the header names no '%s'" % key)

    return CoverageRecord(language = header["language"],
                          tool     = header["tool"],
                          source   = header["format"],
                          counts_f = header["counts"] == "yes",
                          file_db  = file_db,
                          version  = version,
                          run      = run_set_of_text(header["run"]))


def merge(record_iterable):
    """
    RETURN: CoverageRecord, the UNION of every record given -- per source
            file, 'EX' and 'CV' unioned. Associative and commutative, so
            an aggregate does not depend on the order it walked.
            None, if no record was given -- an aggregate over nothing is
            not an empty aggregate.

    Provenance that AGREES is carried; provenance that differs is joined,
    so the merged header SHOWS that the aggregate is not uniform. What an
    aggregator does about that -- merge, segregate, refuse -- is its own
    ruling, and it can only be taken because the header says so.

    THE RUNS ARE UNIONED: the merged record is of every run that made
    it, and its 'run:' line spells the set. An unseated record
    contributes nothing to the set and does not make the others
    anonymous.

    Raises CountsNotMergeable where any record carries hit counts: a
    union has no answer for two different counts over one line, and a
    rule nobody asked for would be worse than a refusal (disc-5).
    """
    record_list = list(record_iterable)
    if not record_list: return None

    for record in record_list:
        if record.counts_f:
            raise CountsNotMergeable(
                "record made by '%s' carries hit counts; a union of "
                "ranges has no answer for them" % record.tool)
        for entry in record.file_db.values():
            for name, point_tuple in entry.measure_db.items():
                if not point_tuple: continue
                measure = measure_of(name)
                if measure is None or measure.mergeable: continue
                raise MeasureNotMergeable(
                    "record made by '%s' carries '%s' coverage of '%s', "
                    "which declares itself unmergeable: a COUNT of what "
                    "was covered does not carry WHICH, so two runs "
                    "covering different parts cannot be combined"
                    % (record.tool, name, entry.path))

    def joined(name):
        """RETURN: str, the one value if all agree, else all of them."""
        value_list = sorted(set(str(getattr(r, name)) for r in record_list))
        return value_list[0] if len(value_list) == 1 else ",".join(value_list)

    file_db = {}
    for record in record_list:
        for path, entry in record.file_db.items():
            standing = file_db.get(path)
            if standing is None:
                file_db[path] = entry
            else:
                #  Unmergeable measures were refused above, so what
                #  meets here MERGES -- the measure owns how ('toggle'
                #  and 'cover' union by point identity). A measure one
                #  side lacks is carried: the point set IS what was
                #  measured, and absence stays absent.
                measure_db = dict(standing.measure_db)
                for name, point_tuple in entry.measure_db.items():
                    held    = measure_db.get(name)
                    measure = measure_of(name)
                    if   held is None:       measure_db[name] = point_tuple
                    elif measure is not None:
                        measure_db[name] = measure.merge(held, point_tuple)
                file_db[path] = FileCoverage(
                    path,
                    union(standing.executable, entry.executable),
                    union(standing.covered,    entry.covered),
                    None, measure_db)

    run_set = frozenset().union(*(r.run for r in record_list))
    return CoverageRecord(language = joined("language"),
                          tool     = joined("tool"),
                          source   = joined("source"),
                          counts_f = False,
                          file_db  = file_db,
                          run      = run_set)
