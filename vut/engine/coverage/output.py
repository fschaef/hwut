"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE OUTPUT DIRECTORY OF A COVERAGE RUN (coverage D-42) -- the
         ONE place coverage data is kept: every source file's coverage,
         each covered range annotated with the test runs that executed
         it.

    <output>/hwut-coverage.marker        this directory is hwut's; the
                                         root the run walked
    <output>/test_run_id_db.csv          directory;test;choice;
                                         test_run_id -- one row per
                                         test run, as 'GOOD/book.csv'
                                         is written: a directory or a
                                         test equal to the row above is
                                         left empty
    <output>/test_run_group_id_db.csv    test_run_group_id;test_run_ids
                                         -- one row per distinct SET of
                                         test runs that executed some
                                         range together
    <output>/<source path>.cover         one file per SOURCE file, its
                                         path taken from the run's root

THE COVERAGE FILE is record version 3 ('database/gathered.py'), BINARY
on disk (D-43); its text spelling, which 'hwut.cov.conv.to_humans' shows, is

    ##VUT-COVERAGE 3
    ##source:   engine/compare/core.py
    ##language: python
    ##tool:     coverage
    ##format:   coverage.py-json
    ##id-width: 2
    EX:3+12,5+5
    BR:5*2,0*3
    CV@02:3+4
    CV@10:8+8
    BR@02:1*1,1*5
    BR@10:1*2

'EX' and the ranges after 'CV@<reference>:' are DELTA CODED as in every
record ('database/FORMAT.txt' section 4). A REFERENCE is a test run id
where ONE run executed the ranges, a test run group id where several
did. The 'CV' lines are disjoint; their union is what was covered.

EVERY MEASURE IS CARRIED (D-43, FORMAT.txt section 10): 'BR:' is the
UNIVERSE of the branch measure, every decision with the number of its
arms, once; 'BR@<reference>:' lists the arms that reference took, as
'ordinal delta * mask'. Every arm stands under exactly one reference --
the one whose set of runs is exactly the set that took it -- so the
arms a run took are the OR over the references that include it. The
same holds for MC, TG, CP and FN.

AN IDENTIFIER STANDS IN EXACTLY ONE OF THE TWO TABLES. Test run ids
count from zero; group ids begin at the next round value above the
last test run id, so the two never overlap and no file needs to say
where one kind ends. 'read' asserts it.

AN IDENTIFIER IS A NUMBER IN BASE 64 ('database/identifier.py'), every
identifier of one output written at ONE WIDTH, which each coverage file
carries as 'id-width'.

THE DIRECTORY HOLDS EXACTLY ONE RUN. Everything in it is removed when a
coverage run starts. IT IS REMOVED ONLY WHERE IT IS HWUT'S: an empty
directory, or one carrying the marker. Anything else is refused by
name -- a mistyped '-o' must not cost a directory of somebody's files.

HIT COUNTS ARE NOT CARRIED: a line was executed or it was not.
______________________________________________________________________________
"""
import csv
import os
import shutil

from .database.api import (GatheredFile, MeasureFault, RecordFault,
                           group_id_start, id_text, measure_db_of,
                           measure_of,
                           pack_gathered, rebased, subtract,
                           unpack_gathered, unpack_record, union)
from .database.api import index_of

DEFAULT_DIRECTORY_NAME = "hwut.coverage"
MARKER_FILE            = "hwut-coverage.marker"
RUN_ID_FILE            = "test_run_id_db.csv"
GROUP_ID_FILE          = "test_run_group_id_db.csv"
COVERAGE_SUFFIX        = ".cover"
SEPARATOR              = ";"

GROUP_ID_COMMENT = (
    "# This file defines groups of test run ids: a group is a set of",
    "# test runs that executed some range of source together.",
    "# A group id and a test run id ('%s') never" % RUN_ID_FILE,
    "# overlap: an identifier stands in exactly one of the two files.")


class OutputRefused(ValueError):
    """An output directory that may not be emptied, or cannot be read,
    named at the door."""


def prepared(output_directory, root):
    """
    RETURN: str, the absolute path of 'output_directory', standing
            EMPTY but for the marker, which names 'root' -- the
            directory the coverage run walks. What stood in it is
            removed.

    Raises OutputRefused where the path is no directory, or is a
    directory holding files and no marker of hwut's.
    """
    path = os.path.abspath(str(output_directory))
    if os.path.exists(path):
        if not os.path.isdir(path):
            raise OutputRefused("'%s' is no directory" % path)
        if os.listdir(path) \
           and not os.path.isfile(os.path.join(path, MARKER_FILE)):
            raise OutputRefused(
                "'%s' holds files and no '%s': not emptied. Name an "
                "empty directory, or one a coverage run made"
                % (path, MARKER_FILE))
        shutil.rmtree(path)
    os.makedirs(path)
    with open(os.path.join(path, MARKER_FILE), "w",
              encoding="utf-8") as handle:
        handle.write("coverage data of 'hwut.cov.run'; removed at the "
                     "start of the next coverage run\n")
        handle.write("root: %s\n" % os.path.abspath(str(root)))
    return path


def root_of(output_directory):
    """
    RETURN: str, the root the coverage run of that output walked, as
            its marker names it.
            None, where no marker stands or it names none.
    """
    try:
        with open(os.path.join(str(output_directory), MARKER_FILE),
                  encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("root: "): return line[6:].rstrip("\n")
    except OSError:
        pass
    return None


def coverage_path(output_directory, source):
    """RETURN: str, where the coverage file of the source file 'source'
    (its path from the run's root) stands under 'output_directory'."""
    return os.path.join(str(output_directory),
                        *(source + COVERAGE_SUFFIX).split("/"))


def gather(output_directory, run_list):
    """
    RETURN: [0] int, the test runs gathered
            [1] int, the source files written
            [2] list of str, source files OUTSIDE the run's root, which
                have no place under the output directory and were left
                out, sorted

    'run_list' holds one '(directory, test, choice, record path)' per
    test run that left a per-case record: 'directory' relative to the
    run's root with '/' between, 'choice' None where the test has
    none. The three tables of the output are written: the test run
    ids, the groups, and one coverage file per source file.

    THE WHOLE RUN IS FOLDED AT ONCE: a source file is complete only
    when every test directory that reaches it has been read.
    """
    run_list = sorted(run_list,
                      key=lambda run: (run[0], run[1], run[2] or ""))
    pair_list = []
    header_db = {}                 # source -> {key: set of values}
    executable_db = {}             # source -> ranges
    measure_run_db = {}            # source -> {measure: [(run, entry)]}
    for number, (directory, _, _, path) in enumerate(run_list):
        with open(path, "rb") as handle:
            record = rebased(unpack_record(handle.read()),
                             None if directory in ("", ".") else directory)
        pair_list.append((number, record))
        for source, entry in record.file_db.items():
            executable_db[source] = union(executable_db.get(source, ()),
                                          entry.executable)
            for name, points in (entry.measure_db or {}).items():
                measure_run_db.setdefault(source, {}).setdefault(
                    name, []).append((number, points))
            value_db = header_db.setdefault(source, {})
            for key, value in (("language", record.language),
                               ("tool", record.tool),
                               ("format", record.source)):
                value_db.setdefault(key, set()).update(
                    str(value or "").split(","))
    index = index_of(pair_list)

    start    = group_id_start(len(run_list))
    group_db = {}                  # frozenset of run numbers -> group id
    line_db  = {}                  # source -> {reference: [ranges]}
    universe_db, item_db = {}, {}  # source -> universe_tuple, {ref: items}
    outside_list = []
    for source in sorted(executable_db):
        if source == ".." or source.startswith("../"):
            outside_list.append(source)
            continue
        reference_db = {}
        for span, run_set in index.segment_iterable(source):
            if not run_set: continue
            if len(run_set) == 1:
                reference = next(iter(run_set))
            else:
                reference = group_db.setdefault(run_set,
                                                start + len(group_db))
            reference_db.setdefault(reference, []).append(span)
        line_db[source] = reference_db
        try:
            universe_db[source], item_db[source] = _measures_of(
                measure_run_db.get(source, {}), group_db, start)
        except MeasureFault as fault:
            raise OutputRefused("'%s' cannot be gathered: %s"
                                % (source, fault)) from None
    width = len(id_text(start + max(len(group_db) - 1, 0), 1))

    def text(number):
        """RETURN: str, the identifier of 'number' at this output's
        width."""
        return id_text(number, width)

    _write_table(os.path.join(output_directory, RUN_ID_FILE), (),
                 ("directory", "test", "choice", "test_run_id"),
                 [(directory, test, choice or "", text(number))
                  for number, (directory, test, choice, _)
                  in enumerate(run_list)], elide_n=2)
    _write_table(os.path.join(output_directory, GROUP_ID_FILE),
                 GROUP_ID_COMMENT,
                 ("test_run_group_id", "test_run_ids"),
                 [(text(group), ",".join(text(n) for n in sorted(run_set)))
                  for run_set, group in sorted(group_db.items(),
                                               key=lambda item: item[1])],
                 elide_n=0)
    for source in line_db:
        value_db = header_db[source]
        joined   = {key: ",".join(sorted(v for v in value_db[key] if v))
                    for key in ("language", "tool", "format")}
        span_db = line_db[source]
        taken   = item_db[source]
        gathered = GatheredFile(
            source, joined["language"], joined["tool"], joined["format"],
            width, tuple(executable_db[source]),
            tuple((reference, tuple(span_db.get(reference, ())),
                   tuple(taken.get(reference, ())))
                  for reference in sorted(set(span_db) | set(taken))),
            universe_db[source])
        path = coverage_path(output_directory, source)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(pack_gathered(gathered))
    return len(run_list), len(line_db), outside_list


def _measures_of(run_db, group_db, start):
    """
    RETURN: [0] tuple of (measure name, tuple of (line, name, total)),
                the UNIVERSE of every measure the runs reported for ONE
                source: every point with the number of its items
            [1] dict, reference number -> tuple of (measure name, tuple
                of (ordinal, mask)): the items that reference took

    'run_db' is measure name -> [(run number, entry)] over the runs that
    reported the measure for this source. A point is identified by its
    line, its name and its place among the points of that line and
    name. EVERY ITEM IS PLACED UNDER THE ONE REFERENCE whose runs are
    exactly the runs that took it; a set of several runs takes its id
    from 'group_db' (frozenset of run numbers -> group id), which this
    adds to, new ids counted from 'start'.

    Raises MeasureFault where a measure cannot name its items or where
    two runs disagree on the number of items of one point.
    """
    universe_list, taken_db = [], {}
    for name in sorted(run_db):
        measure  = measure_of(name)
        total_db = {}                          # key -> total
        mask_db  = {}                          # key -> [(run, mask)]
        for number, entry in run_db[name]:
            place_db = {}
            for line, point_name, total, mask in measure.point_list(entry):
                place = place_db.get((line, point_name), 0)
                place_db[(line, point_name)] = place + 1
                key = (line, point_name, place)
                if total_db.setdefault(key, total) != total:
                    raise MeasureFault(
                        "the point '%s' of '%s' at line %i has %i items "
                        "in one run and %i in another: these are not one "
                        "point" % (point_name, name, line, total_db[key],
                                   total))
                mask_db.setdefault(key, []).append((number, mask))
        key_list = sorted(total_db)
        universe_list.append((name, tuple((key[0], key[1], total_db[key])
                                          for key in key_list)))
        for ordinal, key in enumerate(key_list, 1):
            every = 0
            for _, mask in mask_db[key]: every |= mask
            by_set = {}                        # run set -> mask of items
            bit = 0
            while every >> bit:
                if every >> bit & 1:
                    run_set = frozenset(number for number, mask
                                        in mask_db[key] if mask >> bit & 1)
                    by_set[run_set] = by_set.get(run_set, 0) | 1 << bit
                bit += 1
            for run_set, mask in by_set.items():
                if len(run_set) == 1:
                    reference = next(iter(run_set))
                else:
                    reference = group_db.setdefault(run_set,
                                                    start + len(group_db))
                taken_db.setdefault(reference, {}).setdefault(
                    name, []).append((ordinal, mask))
    item_db = {reference: tuple((name, tuple(sorted(entry_list)))
                                for name, entry_list
                                in sorted(measure_db.items()))
               for reference, measure_db in taken_db.items()}
    return tuple(universe_list), item_db


def _write_table(path, comment_tuple, column_tuple, row_list, elide_n):
    """
    RETURN: None. A ';'-separated table written at 'path': the comment
            lines, the header, the rows. In each of the first 'elide_n'
            columns a cell equal to the one above is left EMPTY -- and
            a cell left of a changed one is always written, so an
            empty cell means 'the one above' and nothing else.
    """
    with open(path, "w", encoding="utf-8", newline="") as handle:
        for line in comment_tuple: handle.write(line + "\n")
        writer = csv.writer(handle, delimiter=SEPARATOR,
                            lineterminator="\n")
        writer.writerow(column_tuple)
        above = None
        for row in row_list:
            cell_list = list(row)
            if above is not None:
                for i in range(elide_n):
                    if row[i] != above[i]: break
                    cell_list[i] = ""
            writer.writerow(cell_list)
            above = row


def _read_table(path, elide_n):
    """
    RETURN: list of tuple, the rows of the table at 'path', the elided
            cells of the first 'elide_n' columns filled from above;
            comment lines and the header left out.

    Raises OutputRefused where the file cannot be read.
    """
    row_list = []
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.reader((line for line in handle
                                 if not line.startswith("#")),
                                delimiter=SEPARATOR)
            next(reader, None)
            above = None
            for row in reader:
                if above is not None:
                    for i in range(elide_n):
                        if row[i] != "": break
                        row[i] = above[i]
                above = row
                row_list.append(tuple(row))
    except (OSError, csv.Error, UnicodeDecodeError, IndexError) as fault:
        raise OutputRefused("'%s' cannot be read: %s" % (path, fault))
    return row_list


class Output:
    """A coverage run's output directory, READ: the test runs, the
    groups, and the coverage files."""

    def __init__(self, output_directory):
        """
        RETURN: Output over 'output_directory', its two tables read.

        Raises OutputRefused where a table cannot be read, or where an
        identifier stands in both -- the gatherer keeps them apart, and
        a directory where they overlap was not written by it.
        """
        self.directory = str(output_directory)
        self.run_db    = {}        # (directory, test, choice|None) -> id
        self.name_db   = {}        # id -> (directory, test, choice|None)
        for directory, test, choice, run_id in _read_table(
                os.path.join(self.directory, RUN_ID_FILE), elide_n=2):
            key = (directory, test, choice or None)
            self.run_db[key]     = run_id
            self.name_db[run_id] = key
        self.group_db  = {}        # group id -> frozenset of run ids
        for group_id, member_text in _read_table(
                os.path.join(self.directory, GROUP_ID_FILE), elide_n=0):
            self.group_db[group_id] = frozenset(member_text.split(","))
        both = sorted(set(self.name_db) & set(self.group_db))
        if both:
            raise OutputRefused(
                "'%s': identifier '%s' is a test run id and a group id"
                % (self.directory, both[0]))

    def run_set_of(self, reference):
        """
        RETURN: frozenset of test run ids, the runs the reference of a
                'CV@' line stands for: itself where it is a test run
                id, its members where it is a group id.

        Raises OutputRefused where it stands in neither table.
        """
        if reference in self.name_db:  return frozenset((reference,))
        if reference in self.group_db: return self.group_db[reference]
        raise OutputRefused("'%s': reference '%s' is in neither table"
                            % (self.directory, reference))

    def gathered_iterable(self):
        """
        YIELD: GatheredFile, the coverage file of one source, whole: its
               lines, its universes, the items of its references.

        Every coverage file of the output, in path order.

        Raises OutputRefused where a coverage file cannot be read.
        """
        found = []
        for directory, _, name_list in os.walk(self.directory):
            for name in name_list:
                if name.endswith(COVERAGE_SUFFIX):
                    found.append(os.path.join(directory, name))
        for path in sorted(found):
            try:
                with open(path, "rb") as handle:
                    yield unpack_gathered(handle.read())
            except (OSError, RecordFault) as fault:
                raise OutputRefused("'%s' cannot be read: %s"
                                    % (path, fault))

    def source_iterable(self):
        """
        YIELD: [0] str, a source file's path from the run's root
               [1] tuple of (begin, end), its executable ranges
               [2] list of (reference, tuple of (begin, end)), its
                   covered ranges by who executed them

        The LINE AXIS of every coverage file of the output, in path
        order; 'gathered_iterable' holds the rest.

        Raises OutputRefused where a coverage file cannot be read.
        """
        for gathered in self.gathered_iterable():
            yield (gathered.source, gathered.executable,
                   [(id_text(reference, gathered.id_width), span_tuple)
                    for reference, span_tuple, _ in gathered.reference_list
                    if span_tuple])

    def of_run(self, directory, test, choice):
        """
        RETURN: list of (source, covered, not_executed), what ONE test
                run reached: per source file it executed any line of,
                the ranges it executed and the executable ranges it
                did not; in path order.
                None, where the output names no such test run.
        """
        run_id = self.run_db.get((directory, test, choice or None))
        if run_id is None: return None
        result = []
        for source, executable, covered in self.source_iterable():
            reached = ()
            for reference, ranges in covered:
                if run_id in self.run_set_of(reference):
                    reached = union(reached, ranges)
            if reached:
                result.append((source, reached,
                               subtract(executable, reached)))
        return result


    def measures_of_run(self, directory, test, choice):
        """
        RETURN: list of (source, measure_db), what ONE test run took
                BESIDE the lines: per source file whose coverage file
                holds any measure, a dict measure name -> entry (the
                measure's own shape, as a per-case record holds it); in
                path order. Every point of the source's universe stands
                in the entry, the items the run did not take as an empty
                mask.
                None, where the output names no such test run.
        """
        run_id = self.run_db.get((directory, test, choice or None))
        if run_id is None: return None
        result = []
        for gathered in self.gathered_iterable():
            if not gathered.universe_tuple: continue
            reference_set = {
                reference for reference, _, _ in gathered.reference_list
                if run_id in self.run_set_of(
                    id_text(reference, gathered.id_width))}
            result.append((gathered.source,
                           measure_db_of(gathered, reference_set)))
        return result


__all__ = ("DEFAULT_DIRECTORY_NAME", "MARKER_FILE", "Output",
           "OutputRefused", "coverage_path", "gather", "prepared",
           "root_of")
