"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER FOR GO'S COVER PROFILE -- the one format that is
         already shaped like this record.

DESCRIPTION
       WHAT 'go test -coverprofile' WRITES:

           mode: set
           demo/app.go:3.22,4.11 1 1
           demo/app.go:4.11,6.3 1 1
           demo/app.go:7.2,7.10 1 0

           <import path>/<file>:<l>.<c>,<l>.<c> <statements> <count>

       A LINE IS A BLOCK, NOT A LINE. Every other format this component
       reads says something per SOURCE LINE and leaves this record to
       fold runs of them into ranges. Go says it per BASIC BLOCK, with a
       start and an end -- which IS a range, and arrives as one. Nothing
       is folded; the block's line span is the interval.

       Blocks OVERLAP on their boundary lines ('3.22,4.11' and
       '4.11,6.3' both touch line 4), because the columns divide what the
       lines do not. A line-keyed record unions them: line 4 is
       executable, and covered if ANY block over it ran. The columns are
       dropped, and that is the one thing lost -- a record keyed by line
       cannot say 'the first half of this line ran'.

       THE MODE LINE IS PROVENANCE.
           set     the count is 0 or 1: WHETHER a block ran
           count   the count is how OFTEN
           atomic  the same, safe under concurrency
       Counts are read only under 'count'/'atomic', and only where they
       were asked for: under 'set' a count of 1 means 'ran', and
       recording it as a hit COUNT would be inventing a measurement.

       THE PATH IS AN IMPORT PATH, NOT A FILE PATH. 'demo/app.go' is the
       MODULE NAME followed by the path inside the module -- and 'demo'
       is a name in go.mod, not a directory on disk. Left alone it would
       match nothing a diff ever names. So the module path is read from
       'go.mod' and stripped. Where there is no 'go.mod' the path is left
       as it stands, and that is SAID rather than guessed at.
______________________________________________________________________________
"""
import io
import os

from ..reader import (I_Reader, register, artifact_directory_of,
                      relative_path, wanted, record_of)


PROFILE_SUFFIX = (".out", ".cover", ".coverprofile")

COUNTING_MODE_SET = ("count", "atomic")


class GoReader(I_Reader):
    """Go's cover profile."""
    name          = "go"
    source_format = "go-coverprofile"

    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], 'argv' unchanged.

        'go test' takes '-coverprofile' as an argument of ITS OWN
        command line, not as a wrapper around somebody else's. A test
        application that is a go test invocation states that flag
        itself; one that is a compiled binary cannot be wrapped at all.
        """
        return list(argv)

    def report_argv(self, config, work_dir):
        """RETURN: None. The profile is text, written by the run."""
        return None

    def harvest(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, of every profile under the artifact
                directory.
                None, where none stands -- ABSENT.
        """
        block_db  = {}
        mode      = None
        directory = artifact_directory_of(work_dir)
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                if not name.endswith(PROFILE_SUFFIX): continue
                with io.open(os.path.join(directory, name), "r",
                             encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
                seen = read_profile(text, block_db)
                if seen is not None: mode = seen
        if not block_db: return None

        prefix   = module_prefix_of(work_dir)
        counts_f = bool(config is not None and config.counts
                        and mode in COUNTING_MODE_SET)
        return record_of(self, "go",
                         entry_iterable(block_db, prefix, source_root,
                                        config, counts_f),
                         counts_f)


def module_prefix_of(work_dir):
    """
    RETURN: str, the module path 'go.mod' declares, with a trailing '/'
            -- what every profile path is prefixed with.
            None, where no 'go.mod' stands beside the run, or it declares
            no module. The paths are then left as they are, which is
            honest and useless to a diff; guessing a prefix would be
            worse.

    Walks upward: a test may sit in a package below the module root.
    """
    directory = os.path.abspath(work_dir)
    while True:
        path = os.path.join(directory, "go.mod")
        if os.path.isfile(path):
            try:
                with io.open(path, "r", encoding="utf-8") as handle:
                    for raw in handle:
                        line = raw.strip()
                        if line.startswith("module "):
                            return line[7:].strip() + "/"
            except OSError:
                return None
            return None
        parent = os.path.dirname(directory)
        if parent == directory: return None
        directory = parent


def read_profile(text, block_db):
    """
    RETURN: str, the 'mode:' the profile declares.
            None, where the text declares none -- it is then no profile,
            and nothing of it is absorbed.

    Folds the blocks into 'block_db': path -> list of (begin, end, count)
    half-open line spans. A block is kept as it arrived; the intervals
    are formed later, because two blocks may share a boundary line.
    """
    mode = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith("mode:"):
            mode = line[5:].strip()
            continue
        if mode is None: return None          # no mode: no profile

        head, _, tail = line.rpartition(" ")   # count
        head, _, _    = head.rpartition(" ")   # statements
        path, _, span = head.rpartition(":")
        begin_text, _, end_text = span.partition(",")
        try:
            count = int(tail)
            begin = int(begin_text.split(".")[0])
            end   = int(end_text.split(".")[0])
        except ValueError:
            continue
        if not path or end < begin: continue
        block_db.setdefault(path, []).append((begin, end + 1, count))
    return mode


def entry_iterable(block_db, prefix, source_root, config, counts_f):
    """
    YIELD: (path, executable_lines, covered_lines, count_list) per source
           file inside the gather set.

    A block's span is expanded to its LINES, because two blocks sharing a
    boundary line must union rather than sit beside each other -- the
    columns that told them apart are gone.
    """
    from ..record import ranges_of
    for raw_path in sorted(block_db):
        path = raw_path
        if prefix is not None and path.startswith(prefix):
            path = path[len(prefix):]
        path = relative_path(path, source_root)
        if not wanted(path, config): continue

        executable = set()
        covered    = set()
        count_db   = {}
        for begin, end, count in block_db[raw_path]:
            for number in range(begin, end):
                executable.add(number)
                if count > 0:
                    covered.add(number)
                    count_db[number] = max(count_db.get(number, 0), count)

        count_list = None
        if counts_f:
            count_list = [max(count_db[n] for n in range(begin, end)
                              if n in count_db)
                          for begin, end in ranges_of(sorted(covered))]
        yield path, sorted(executable), sorted(covered), count_list


register(GoReader())
