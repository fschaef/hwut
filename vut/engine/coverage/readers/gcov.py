"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR 'gcov' -- gcc's own annotated source, for C and
         C++.

DESCRIPTION
       WHAT gcov LEAVES, AND WHEN. A binary built with '--coverage'
       writes '.gcda' COUNTERS as it runs -- binary, and unreadable. The
       'gcov' program turns those into '<name>.gcov', an ANNOTATED COPY
       OF THE SOURCE, one line per source line:

               1:    3:int used(int n) {
           #####:    7:    return 0;
               -:    8:}

           <count>    the line ran that often
           '-'        the line is NOT EXECUTABLE -- neither EX nor CV
           '#####'    executable, never executed
           '====='    executable, unreachable except by exception
           '<n>*'     executed, but not every block on the line was

       Line 0 carries the header pseudo-lines, and 'Source:' among them
       is where the SOURCE PATH comes from -- not the file name, which
       '-p' mangles on purpose.

       THE SECOND CALL, AND WHY IT MUST BE MADE LATE. 'report_argv'
       globs for the '.gcda' files that the run just wrote: before the
       run there are none to name. It is called after the application
       has ended, which is exactly when the execute stage would make it.
       Returning None where no '.gcda' exists says 'the build was not
       instrumented' rather than running gcov over nothing.

       '-p' IS NOT DECORATION. Without it, two 'core.c' in two
       directories both become 'core.c.gcov' and the second silently
       replaces the first -- a whole file's coverage lost, in the green
       direction. '-p' keeps the path in the name.

       WHERE THE '.gcov' FILES LAND. gcov writes them into the CURRENT
       DIRECTORY and offers no way to say otherwise ('-o' names the
       OBJECT directory, not the output one). So this reader looks in
       the artifact directory first and in the work directory second,
       and says so rather than pretending the placement is controlled.

       NO HIT COUNTS BY DEFAULT. gcov reports them and this reader reads
       them, but a record carries them only where they were ASKED for
       (D-5). '<n>*' is read as <n>: the star says some block on the line
       did not run, which is a BRANCH fact, and branch coverage is a
       different measurement (todo).
______________________________________________________________________________
"""
import io
import os

from .reader import (CCoverageFramework, CCoverageFormat,
                      register, artifact_directory_of,
                      relative_path, wanted, record_of)


GCOV_SUFFIX = ".gcov"
GCDA_SUFFIX = ".gcda"

NOT_EXECUTABLE = "-"
NEVER_EXECUTED = ("#####", "=====", "$$$$$")


class GcovFormat(CCoverageFormat):
    """gcc's '.gcov' annotated source."""
    name = "gcov-annotated"

    def read(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of every '.gcov' the second call left.
                None, where none stands -- ABSENT, which is not an empty
                measurement.
        """
        path_list = gcov_path_tuple(work_dir)
        if not path_list: return None

        counts_f = bool(config is not None and config.counts)
        entry_db = {}
        for path in path_list:
            with io.open(path, "r", encoding="utf-8",
                         errors="replace") as handle:
                source, line_db = read_annotated(handle.read())
            if source is None: continue
            standing = entry_db.setdefault(source, {})
            for number, count in line_db.items():
                if count is None:
                    standing.setdefault(number, None)
                else:
                    was = standing.get(number)
                    standing[number] = count if was is None else was + count

        return record_of(self, "c",
                         entry_iterable(entry_db, source_root, config,
                                        counts_f),
                         counts_f)


class GcovFramework(CCoverageFramework):
    """gcov: invocation; reads GcovFormat.

    NOTHING TO WRAP (the base's default): gcov instruments at BUILD
    time ('--coverage'), not at launch, and a wrapper that did nothing
    would be worse than none. Whether the build carried the flag is
    the BUILD's business, and this reader reports its absence by
    finding no '.gcda'. The one framework that can
    CHECK instrumentation: gcc leaves a '.gcno' beside every object it
    instrumented, before anything runs."""
    name   = "gcov"
    format = GcovFormat()

    def instrumented_f(self, target, work_dir):
        """
        RETURN: True,  at least one '.gcno' stands under 'work_dir' --
                       something was compiled with '--coverage'.
                False, none does: nothing here was instrumented.

        Never None: the trace either stands or it does not.
        """
        for base, _, file_list in os.walk(work_dir):
            if any(name.endswith(".gcno") for name in file_list):
                return True
        return False


    def report_argv(self, config, work_dir):
        """
        RETURN: list[str], 'gcov -b -p <every .gcda the run wrote>'.
                None, where the run wrote none -- the build was not
                instrumented, and gcov over nothing would only add a
                failure with a misleading name.

        Made LATE, after the application ended: before it there is no
        '.gcda' to name.
        """
        path_list = gcda_path_tuple(work_dir)
        if not path_list: return None
        return ["gcov", "-b", "-p"] + list(path_list)


def gcda_path_tuple(work_dir):
    """
    RETURN: tuple of str, every '.gcda' under the work directory, sorted
            -- the counters this run wrote.
    """
    result = []
    for base, dir_list, file_list in os.walk(work_dir):
        for name in file_list:
            if name.endswith(GCDA_SUFFIX):
                result.append(os.path.join(base, name))
    return tuple(sorted(result))


def gcov_path_tuple(work_dir):
    """
    RETURN: tuple of str, every '.gcov' file to read: those in the
            artifact directory, else those in the work directory itself.

    Two places, because gcov chooses the second and cannot be told
    otherwise (module header).
    """
    for directory in (artifact_directory_of(work_dir), work_dir):
        if not os.path.isdir(directory): continue
        found = tuple(sorted(os.path.join(directory, name)
                             for name in os.listdir(directory)
                             if name.endswith(GCOV_SUFFIX)))
        if found: return found
    return ()


def read_annotated(text):
    """
    RETURN: [0] str,  the source path the file annotates, from its
                      'Source:' header.
                None, where it names none -- the file is then not read,
                      rather than attributed to a guessed name.
            [1] dict, line number -> hit count; None as the count where
                      the line is EXECUTABLE but was never executed.
                      Non-executable lines do not appear at all.

    Lines that are not '<count>:<number>:<text>' -- gcov's 'function',
    'branch' and 'call' annotations under '-b' -- are skipped: they are a
    different measurement.
    """
    source  = None
    line_db = {}
    for raw in text.splitlines():
        part_list = raw.split(":", 2)
        if len(part_list) < 3: continue
        count_text = part_list[0].strip()
        try:    number = int(part_list[1].strip())
        except ValueError: continue          # 'function'/'branch'/'call'

        if number == 0:
            body = part_list[2].strip()
            if body.startswith("Source:"): source = body[7:].strip()
            continue
        if count_text == NOT_EXECUTABLE:     continue
        if count_text in NEVER_EXECUTED:
            line_db[number] = None
            continue
        #  '<n>*': executed, though not every block on the line was. The
        #  star is a BRANCH fact; the count is the line's.
        try:    line_db[number] = int(count_text.rstrip("*"))
        except ValueError: continue
    return source, line_db


def entry_iterable(entry_db, source_root, config, counts_f):
    """
    YIELD: (path, executable_lines, covered_lines, count_list) per source
           file inside the gather set, paths relative to the test
           directory.

    EX is every line gcov admitted as executable -- counted or '#####'
    alike. CV is those with a count above zero.
    """
    from ..database.record import ranges_of
    for raw_path in sorted(entry_db):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        line_db    = entry_db[raw_path]
        executable = sorted(line_db)
        covered    = [n for n in executable
                      if line_db[n] is not None and line_db[n] > 0]
        count_list = None
        if counts_f:
            count_list = [max(line_db[n] for n in range(begin, end)
                              if line_db.get(n) is not None)
                          for begin, end in ranges_of(covered)]
        yield path, executable, covered, count_list


register(GcovFramework())
