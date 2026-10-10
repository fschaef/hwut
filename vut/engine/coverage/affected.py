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

       WHERE THE COVERAGE COMES FROM. THE OUTPUT DIRECTORY of
       'hwut.cov.run' (D-42): its coverage files carry who executed every
       range, its two tables name the runs. '--cov-dir DIR' states it;
       unstated, './hwut.coverage' is read where it stands. A source's
       path there is from the run's ROOT, which is what a diff made at
       that root calls it -- no rebasing. The answer is spelled as
       WISHLIST LINES ('./<directory>/<test> <choice>'), so '--bare'
       feeds 'hwut.run --wishlist'.

       A DIRECTORY THAT HOLDS NO COVERAGE IS REFUSED BY NAME. Measured
       2026-10-10: over a measured tree this face indexed '0 run(s)'
       and answered 'NONE executed the changed lines' -- a wrong
       answer dressed as an empty one.

       THE PER-CASE RECORDS ('--records DIR') are the older input: the
       coverage run removes them once gathered, so they stand only
       where somebody kept them. This face WALKS a root for record
       files. That is a stand-in: the store's naming is the BOOKKEEPER'S
       (operations README 6), and the real face asks it for the paths
       rather than spelling a pattern. The seam is 'record_iterable',
       and it is the only place that would change.
______________________________________________________________________________
"""
import os
import sys

from .database.api import (ranges_of, index_of)
from .output       import (DEFAULT_DIRECTORY_NAME, RUN_ID_FILE, Output,
                           OutputRefused)


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
#
#  'record_iterable' and 'rebased' moved to 'database/index.py'
#  (session 2026-09-04, applying a recommendation from the prior
#  session's report): 'gather.py' needs them too, and a database-
#  side module importing this face -- itself built ON the database
#  api -- closed a circular import. Both are re-exported through
#  '.database.api' so nothing else in this module changes.
from .database.api import record_iterable

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


def render_output(run_tuple, change_db, output, known_n, source_n, bare_f):
    """
    RETURN: str, what the face prints over a coverage OUTPUT DIRECTORY:
            the runs as wishlist lines where 'bare_f', else the framed
            answer -- what was asked, how much of it the output has
            measured, what the output holds, and the runs.

    MACHINE-FREE, as 'render'.
    """
    name_list = ["./%s%s%s" % ("" if directory in (".", "")
                                  else directory + "/", test,
                               "" if choice is None else " " + choice)
                 for directory, test, choice in run_tuple]
    if bare_f:
        return "".join("%s\n" % name for name in name_list)

    range_n = sum(len(r) for r in change_db.values())
    line_list = ["==[ HWUT AFFECTED ]%s" % ("=" * 58),
                 "change:  %i file(s), %i range(s); %i file(s) measured"
                 % (len(change_db), range_n, known_n),
                 "index:   %i run(s), %i source file(s)"
                 % (len(output.name_db), source_n),
                 "groups:  %i distinct" % len(output.group_db),
                 ""]
    if name_list:
        line_list.append("runs to perform:")
        line_list += ["  %s" % name for name in name_list]
    else:
        line_list.append("runs to perform: NONE executed the changed lines.")
    line_list.append("")
    line_list += list(NOTE_LINE_TUPLE)
    return "\n".join(line_list) + "\n"


USAGE_STR = ("hwut.affected [--cov-dir DIR | --records DIR] "
             "[--diff FILE|-] [-p N] [-b|--bare]")


def main(argv, write=None, error=None):
    """
    RETURN: int, the exit code -- 'E_ExitCode.OK' with a selection,
            'EMPTY' where nothing executed the change, 'REFUSED' where
            the command line cannot mean anything.

        hwut.affected [--cov-dir DIR | --records DIR] [--diff FILE|-]
                      [-p N] [-b|--bare]

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
            write("\n    %s\n" % USAGE_STR)
            return E_ExitCode.OK
        elif word in ("--records", "--cov-dir") and i + 1 < len(argv):
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

    if root is None and os.path.isdir(DEFAULT_DIRECTORY_NAME):
        root = DEFAULT_DIRECTORY_NAME
    if root is None:
        error("REFUSED: no './%s' here and no '--cov-dir DIR': this face "
              "reads the output of 'hwut.cov.run', it does not run "
              "tests.\n" % DEFAULT_DIRECTORY_NAME)
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

    if os.path.isfile(os.path.join(root, RUN_ID_FILE)):
        #  THE OUTPUT DIRECTORY OF A COVERAGE RUN.
        try:
            output = Output(root)
            key_tuple, known_n, source_n = output.runs_of_change(change_db)
        except OutputRefused as fault:
            error("REFUSED: %s\n" % fault)
            return E_ExitCode.REFUSED
        if not output.name_db:
            error("REFUSED: '%s' names no test run -- no coverage was "
                  "recorded there\n" % root)
            return E_ExitCode.REFUSED
        write(render_output(key_tuple, change_db, output, known_n,
                            source_n, bare_f))
    else:
        index     = index_of(record_iterable(root))
        if not index.run_key_set:
            error("REFUSED: '%s' holds no coverage -- neither the output "
                  "of 'hwut.cov.run' ('%s') nor a per-case record\n"
                  % (root, RUN_ID_FILE))
            return E_ExitCode.REFUSED
        key_tuple = index.of_change(change_db)
        write(render(key_tuple, change_db, index, bare_f))
    if bare_f:
        for line in NOTE_LINE_TUPLE: error("%s\n" % line)

    return E_ExitCode.OK if key_tuple else E_ExitCode.EMPTY


if __name__ == "__main__":
    sys.exit(main(sys.argv))
