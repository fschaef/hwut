"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR THE LCOV TRACEFILE -- the lingua franca.

DESCRIPTION
       ONE FORMAT, MANY TOOLS. 'lcov', 'gcovr', 'grcov' and 'kcov' all
       emit an LCOV tracefile, and so does 'coverage lcov'. This reader
       therefore stands for FOUR entries in the registry, and is the
       cheapest way to admit a fifth tool: if it speaks LCOV, it is
       already read.

       WHAT IS READ, AND WHAT IS IGNORED.

           SF:<path>              a source file's record begins
           DA:<line>,<count>      an EXECUTABLE line, and its hits
           end_of_record          the record ends

           TN: LF: LH: FN: FNDA:  summaries and function data. IGNORED
           FNF: FNH: BRDA: BRF:   deliberately: LF/LH are DERIVED from
           BRH: VER:              the DA lines, and a summary that
                                  disagreed with its own detail would
                                  have to be adjudicated -- so the
                                  detail is read and the summary is not
                                  consulted. Branch data is a different
                                  measurement (todo).

       EX is every 'DA' line; CV is every 'DA' whose count is not zero.
       HIT COUNTS are read and kept where they were ASKED for; otherwise
       the counts are dropped and the header says 'counts: no'. A tool
       that reports counts does not oblige a record to carry them.

       ONE FILE, SEVERAL BLOCKS. A merged tracefile may carry the same
       'SF' twice. The blocks are UNIONED -- which is what merging means
       here, and the same operation the record's own merge is.

       PATHS. 'SF' is frequently ABSOLUTE, because the tools that write
       it run from build directories. It is made relative to the test
       directory here, which is the one point where the absolute form is
       still available and can be discarded for good.

       THIS READER NAMES NO CALL. A tracefile is text: whoever produced
       it did so as part of the build or by the tool's own run, and this
       component does not know how to drive four different tools'
       reporters. 'report_argv' returns None, honestly -- and a
       configuration whose tool leaves no tracefile gets no record, which
       is reported as ABSENT and never as an empty measurement.
______________________________________________________________________________
"""
import io
import os

from ..reader import (CCoverageFramework, CCoverageFormat,
                      register, artifact_directory_of,
                      relative_path, wanted, record_of)


TRACEFILE_SUFFIX = (".info", ".lcov")


class LcovFormat(CCoverageFormat):
    """An LCOV tracefile, whoever wrote it."""
    name = "lcov-tracefile"

    def read(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of every tracefile under the artifact
                directory, unioned.
                None, where no tracefile stands -- ABSENT.
        """
        text_list = []
        directory = artifact_directory_of(work_dir)
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if not name.endswith(TRACEFILE_SUFFIX): continue
                with io.open(os.path.join(directory, name), "r",
                             encoding="utf-8", errors="replace") as handle:
                    text_list.append(handle.read())
        if not text_list: return None

        count_db = {}
        for text in text_list:
            merge_count_db(count_db, count_db_of(text))

        counts_f = bool(config is not None and config.counts)
        return record_of(self, language_of(count_db),
                         entry_iterable(count_db, source_root, config,
                                        counts_f),
                         counts_f)


class LcovFramework(CCoverageFramework):
    """lcov: invocation; reads LcovFormat.

    NOTHING TO WRAP (the base's default): the tools that write LCOV
    tracefiles are driven by the build or by the test's own command
    line, not by a wrapper this component could put around them.
    """
    name   = "lcov"
    format = LcovFormat()




def count_db_of(text):
    """
    RETURN: dict, source path -> {line: hit count}, of one tracefile.

    Only 'SF' and 'DA' are read; a 'DA' before any 'SF' is ignored
    rather than guessed at.
    """
    result = {}
    path   = None
    for raw in text.splitlines():
        line = raw.strip()
        if   line.startswith("SF:"):    path = line[3:].strip()
        elif line == "end_of_record":   path = None
        elif line.startswith("DA:") and path is not None:
            body = line[3:].split(",")
            if len(body) < 2: continue
            try:    number, count = int(body[0]), int(body[1])
            except ValueError: continue
            entry = result.setdefault(path, {})
            entry[number] = entry.get(number, 0) + count
    return result


def merge_count_db(into, other):
    """
    RETURN: None. Unions 'other' into 'into': a line known to both keeps
            the SUM of its counts, which is what merging two runs of one
            file means.
    """
    for path, line_db in other.items():
        standing = into.setdefault(path, {})
        for number, count in line_db.items():
            standing[number] = standing.get(number, 0) + count


def language_of(count_db):
    """
    RETURN: str, the language the tracefile is OF, guessed from the
            extensions it names -- 'c', 'c++', 'rust', 'lua', 'python',
            or 'unknown' where the extensions disagree or say nothing.

    A tracefile carries no language of its own. 'unknown' is SAID rather
    than defaulted to the commonest one: the header must not claim
    something nobody wrote down.
    """
    suffix_db = {".c": "c", ".h": "c", ".cpp": "c++", ".cc": "c++",
                 ".hpp": "c++", ".rs": "rust", ".lua": "lua",
                 ".py": "python", ".go": "go"}
    name_set = set()
    for path in count_db:
        name = suffix_db.get(os.path.splitext(path)[1].lower())
        if name is not None: name_set.add(name)
    if len(name_set) == 1: return name_set.pop()
    if name_set == {"c", "c++"}: return "c++"
    return "unknown"


def entry_iterable(count_db, source_root, config, counts_f):
    """
    YIELD: (path, executable_lines, covered_lines, count_list) per source
           file inside the gather set, paths relative to the test
           directory.

    The counts ride with the COVERED ranges, in the order those ranges
    are formed -- one count per RANGE, not per line: a range exists
    because its lines agree.
    """
    from ..record import ranges_of
    for raw_path in sorted(count_db):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        line_db    = count_db[raw_path]
        executable = sorted(line_db)
        covered    = [n for n in executable if line_db[n] > 0]
        count_list = None
        if counts_f:
            count_list = [max(line_db[n] for n in range(begin, end)
                              if n in line_db)
                          for begin, end in ranges_of(covered)]
        yield path, executable, covered, count_list


register(LcovFramework())
