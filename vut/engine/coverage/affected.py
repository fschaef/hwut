"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.affected' -- a change goes in, the runs that executed it
         come out.

DESCRIPTION
       THE FACE OVER THE INDEX (DISCUSSIONS disc-7 (a)). It does three
       things and no more:

           a DIFF        -> the lines the change touched, per file
           the RECORDS   -> a TestIndex over them
           the QUERY     -> the runs that executed those lines

       IT SELECTS NOTHING AND RUNS NOTHING. What is done with the answer
       -- piping it into a wish, reading it, ignoring it -- is the
       caller's. The face is driven through 'main(argv, write)', so what
       is shown is the face itself and no process stands between.

       THE DIRECTORY IS SUPPLIED HERE, not by the record (RATIONALE D-4,
       DISCUSSIONS disc-4 (a)): a record's paths are relative to its test
       directory and name no machine, so what disambiguates two 'core.py'
       is WHERE THIS FACE FOUND the record -- a path relative to the
       root it was pointed at, and to nothing outside it.

       THE LIMIT IS PRINTED, ALWAYS. The answer names the runs that
       CERTAINLY executed the changed lines. It never says the rest are
       unaffected: a test may depend on code it never executed -- a
       branch that was deleted, a data file, a dynamic dispatch, an
       absence. A face that printed a test list without saying so would
       invite exactly the false green the framework exists to prevent
       (PHILOSOPHY section 7). '--bare' drops the frame for piping; it
       does not drop the note, which goes to stderr instead.

       THE TWO PATH WORLDS, JOINED HERE AND NOWHERE ELSE. A record's
       source paths are relative to ITS TEST DIRECTORY (D-4); a diff's
       are relative to the ROOT. They do not join by themselves, and a
       face that compared them raw would answer "nobody" to every change
       -- an empty selection that looks like an answer. So this face
       REBASES: the directory a record was found in, plus the path the
       record carries, normalised. 'parser/TEST' + '../core.py' becomes
       'parser/core.py', which is what the diff calls it.

       That join is exactly why the DIRECTORY must come from the
       aggregator (disc-4 (a)) rather than from the record: the record
       cannot know where it will be read from, and must not.

       WHERE THE RECORDS COME FROM. This face WALKS a root for record
       files. That is a stand-in: the store's naming is the BOOKKEEPER'S
       (operations README 6), and the real face asks it for the paths
       rather than spelling a pattern. The seam is 'record_iterable',
       and it is the only place that would change.
______________________________________________________________________________
"""
import os
import sys

from .record   import (ranges_of, RecordFault, CoverageRecord,
                       FileCoverage)
from .binary   import unpack_record
from .index    import index_of, Gathered


RECORD_SUFFIX = ".cover"        # binary (D-20); 'hwut.cov convert' shows it


class E_ExitCode:
    """The face's exit codes.

    A LOCAL STAND-IN: the services share 'services/_exit.py'
    and this face joins them the day it moves there. Stated here so that
    the numbers are not invented twice.
    """
    OK       = 0     # a selection was made
    REFUSED  = 2     # the command line cannot mean anything
    EMPTY    = 3     # the request was understood; nothing answers it


NOTE_LINE_TUPLE = (
    "NOTE: these are the runs that CERTAINLY executed the changed lines.",
    "      A run ABSENT here may still be affected -- by a branch that was",
    "      deleted, by a data file, by a dynamic dispatch, by an absence.",
    "      This is a SUGGESTION, never a clearance: running only these and",
    "      calling the suite green is a false green.",
)


# ------------------------------------------------------------------- diff

def change_db_of_diff(text, strip=1):
    """
    RETURN: dict, source path -> tuple of half-open (begin, end) ranges,
            the lines a unified diff touched ON THE NEW SIDE.

    An ADDED line is the line itself. A REMOVED line is recorded at the
    new-side position where it stood: the line is gone, so its own number
    cannot be asked for, but the code AROUND the removal is what a test
    would have executed -- and saying nothing there would hide a deletion
    entirely.

    'strip' removes leading path components, as 'patch -p<N>' does. A
    file removed wholesale ('+++ /dev/null') contributes nothing: there
    is no new-side line to query.
    """
    def stripped(path):
        """RETURN: str, the path with 'strip' leading components gone."""
        part_list = path.replace("\\", "/").split("/")
        return "/".join(part_list[strip:]) if len(part_list) > strip \
               else part_list[-1]

    line_db  = {}
    path     = None
    new_line = 0
    for raw in text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].split("\t")[0].strip()
            path   = None if target == "/dev/null" else stripped(target)
            continue
        if raw.startswith("@@"):
            #  '@@ -a,b +c,d @@' -- only the new side is asked for.
            try:
                new_part = raw.split("+")[1].split("@@")[0].strip()
                new_line = int(new_part.split(",")[0])
            except (IndexError, ValueError):
                new_line = 0
            continue
        if path is None or new_line == 0:      continue
        if raw.startswith("---") or raw.startswith("diff "): continue
        if raw.startswith("\\"):               continue      # 'No newline'
        if raw.startswith("+"):
            line_db.setdefault(path, []).append(new_line)
            new_line += 1
        elif raw.startswith("-"):
            line_db.setdefault(path, []).append(new_line)
        elif raw.startswith(" ") or raw == "":
            new_line += 1

    return {path: ranges_of(line_list)
            for path, line_list in line_db.items() if line_list}


# ---------------------------------------------------------------- records

def record_iterable(root, suffix=RECORD_SUFFIX):
    """
    YIELD: [0] Gathered         who made the record, AS THIS GATHER SEES
                                IT: a RUN ID the record's own header
                                names, qualified by the DIRECTORY it was
                                found in, relative to 'root'. The
                                qualification is THIS gather's and is
                                never stored (D-14).
           [1] CoverageRecord   what it says

    THE RECORD CARRIES ITS OWN IDS (D-18), so nothing here resolves a
    name: the register issued them and only the EDGE that prints an
    answer needs it to decode. A MERGED record names several runs and
    is yielded once per run -- the fold is over runs, and an aggregate
    that reached a line means every run in it reached that line.

    THE WALK IS SORTED so that the fold allocates group ids identically
    from any two invocations over one tree: found-directory first, then
    the record file's name, then the run id.

    THE SEAM. The store's naming is the BOOKKEEPER'S; walking for a
    suffix is a stand-in until this face can ask it. Nothing else in this
    module knows where a record lives.

    A file that does not parse is SKIPPED and named on stderr, and so is
    one that names NO run -- it cannot be attributed, and attributing it
    to a guess is worse than losing it. One broken record must not cost
    the whole selection, and it must not vanish either.
    """
    for base, dir_list, file_list in sorted(os.walk(root)):
        dir_list[:] = sorted(d for d in dir_list if not d.startswith("."))
        for name in sorted(file_list):
            if not name.endswith(suffix): continue
            path = os.path.join(base, name)
            try:
                with open(path, "rb") as handle:
                    record = unpack_record(handle.read())
            except (OSError, RecordFault) as fault:
                sys.stderr.write("skipped '%s': %s\n" % (path, fault))
                continue
            relative  = os.path.relpath(base, root).replace(os.sep, "/")
            directory = None if relative == "." else relative
            if not record.run:
                sys.stderr.write("skipped '%s': the record names no run\n"
                                 % path)
                continue
            for run_id in sorted(record.run):
                yield (Gathered(directory, run_id),
                       rebased(record, directory))


def rebased(record, directory):
    """
    RETURN: CoverageRecord, the same record with every source path made
            relative to the ROOT instead of to its test directory.

    'parser/TEST' + '../core.py' -> 'parser/core.py'. Without this the
    diff's paths and the record's paths never meet, and every query
    answers 'nobody' -- an empty selection that looks like an answer, and
    therefore the worst possible failure of this face.

    A record found AT the root ('directory' None) is already root
    relative and is handed back untouched.
    """
    if directory is None: return record
    file_db = {}
    for path, entry in record.file_db.items():
        fresh = os.path.normpath(os.path.join(directory, path))
        fresh = fresh.replace(os.sep, "/")
        file_db[fresh] = FileCoverage(fresh, entry.executable,
                                      entry.covered, entry.counts)
    return CoverageRecord(language=record.language, tool=record.tool,
                          source=record.source, counts_f=record.counts_f,
                          file_db=file_db, version=record.version,
                          run=record.run)


# ------------------------------------------------------------------- face

def render(key_tuple, change_db, index, bare_f):
    """
    RETURN: str, what the face prints: the bare run list where 'bare_f',
            else the framed answer -- what was asked, what was indexed,
            and the runs.

    MACHINE-FREE: names and counts, no absolute paths, no timestamps, so
    a pack of this can be compared, stored, or pasted.
    """
    if bare_f:
        return "".join("%s\n" % k for k in key_tuple)

    range_n = sum(len(r) for r in change_db.values())
    line_list = ["==[ HWUT AFFECTED ]%s" % ("=" * 58),
                 "change:  %i file(s), %i range(s)"
                 % (len(change_db), range_n),
                 "index:   %i run(s), %i source file(s)"
                 % (len(index.run_key_set), len(index.file_db)),
                 "groups:  %i distinct" % len(index.group_table),
                 ""]
    if key_tuple:
        line_list.append("runs to perform:")
        line_list += ["  %s" % k for k in key_tuple]
    else:
        line_list.append("runs to perform: NONE executed the changed lines.")
    line_list.append("")
    line_list += list(NOTE_LINE_TUPLE)
    return "\n".join(line_list) + "\n"


def main(argv, write=None, error=None):
    """
    RETURN: int, the exit code -- 'E_ExitCode.OK' with a selection,
            'EMPTY' where nothing executed the change, 'REFUSED' where
            the command line cannot mean anything.

        hwut.affected --records DIR [--diff FILE|-] [-p N] [-b|--bare]

    'write' and 'error' take the two streams so that the face can be
    driven directly, no process between it and its test.
    """
    if write is None: write = sys.stdout.write
    if error is None: error = sys.stderr.write

    root     = None
    diff_arg = "-"
    strip    = 1
    bare_f   = False

    i = 1
    while i < len(argv):
        word = argv[i]
        if   word in ("-b", "--bare"):  bare_f = True
        elif word in ("-h", "--help"):
            write(__doc__.split("DESCRIPTION")[0].strip() + "\n")
            write("\n    hwut.affected --records DIR [--diff FILE|-] "
                  "[-p N] [-b|--bare]\n")
            return E_ExitCode.OK
        elif word == "--records" and i + 1 < len(argv):
            i += 1; root = argv[i]
        elif word == "--diff" and i + 1 < len(argv):
            i += 1; diff_arg = argv[i]
        elif word == "-p" and i + 1 < len(argv):
            i += 1
            try:               strip = int(argv[i])
            except ValueError:
                error("REFUSED: '-p %s' is no number of path components\n"
                      % argv[i])
                return E_ExitCode.REFUSED
        else:
            error("REFUSED: '%s' is no word this face knows\n" % word)
            return E_ExitCode.REFUSED
        i += 1

    if root is None:
        error("REFUSED: '--records DIR' is required: this face reads "
              "coverage records, it does not run tests.\n")
        return E_ExitCode.REFUSED
    if not os.path.isdir(root):
        error("REFUSED: '%s' is no directory\n" % root)
        return E_ExitCode.REFUSED

    try:
        diff_text = sys.stdin.read() if diff_arg == "-" \
                    else open(diff_arg, "r", encoding="utf-8").read()
    except OSError as fault:
        error("REFUSED: %s\n" % fault)
        return E_ExitCode.REFUSED

    change_db = change_db_of_diff(diff_text, strip)
    if not change_db:
        error("REFUSED: the diff touches no line this face can read\n")
        return E_ExitCode.REFUSED

    index     = index_of(record_iterable(root))
    key_tuple = index.of_change(change_db)
    write(render(key_tuple, change_db, index, bare_f))
    if bare_f:
        for line in NOTE_LINE_TUPLE: error("%s\n" % line)

    return E_ExitCode.OK if key_tuple else E_ExitCode.EMPTY


if __name__ == "__main__":
    sys.exit(main(sys.argv))
