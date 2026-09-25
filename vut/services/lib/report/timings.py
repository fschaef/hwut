"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       'hwut.report.timings' -- WHAT THIS MACHINE MEASURED, read back.

DESCRIPTION
       The traces a run leaves ('hwut-traces.csv', one file per
       directory, this machine's rows only) said in two shapes:

           hwut.report.timings                 TRADITIONAL (the default):
                                               one line per case, the run
                                               time and, where one stands,
                                               the build time in brackets
           hwut.report.timings --table         CSV on stdout, one row per
                                               case, every column the
                                               traces hold
           hwut.report.timings -o <file>       written there instead of
                                               stdout
           hwut.report.timings --directory=<p> that directory (default '.')
           hwut.report.timings -r              walk the tree below it

       TRADITIONAL reads:

           test-engine.py first_sets      412 [1203]
           test-engine.py follow_sets     390
           ...
           21 case(s), 8.31 s

       the number in brackets is the BUILD, which stands only where the
       case was built. The tail counts what was said and sums the run
       times -- the build is not summed: a build is shared by every
       choice of its application and would be counted once per choice.

       A TIME IS WHAT THIS MACHINE SAW (B-11): another machine's rows
       are passed over, and nothing here is a verdict about anything.
       A case the traces do not hold is not named -- absence is data,
       and this face does not invent a row to say 'unmeasured'.
______________________________________________________________________________
"""
import os
import sys

from   ....engine.bookkeeper.traces import TraceDb, system_key
from   ..._exit                     import E_ExitCode, guarded


USAGE = ("usage: hwut.report.timings [--table] [-o <file>]\n"
         "                           [--directory=<path>] [-r] [--help]")

COLUMN_TUPLE = ("directory", "test", "choice", "operation",
                "duration_ms", "cpu_time_ms", "peak_memory_mb", "day")


def directory_list_of(root, recursive_f):
    """
    RETURN: list, the directories to read, sorted -- 'root' alone, or
            every directory below it that holds a traces file where
            'recursive_f' stands.
    """
    if not recursive_f: return [root]
    found = []
    for directory, sub_list, file_list in os.walk(root):
        sub_list[:] = [name for name in sub_list
                       if name not in ("OUT", "TMP", "__pycache__", ".git")]
        if "hwut-traces.csv" in file_list: found.append(directory)
    return sorted(found)


def row_list_of(directory_list):
    """
    RETURN: list of dict, one per (directory, test, choice) THIS MACHINE
            measured, sorted by directory then test then choice. Each
            holds the traces' own columns plus 'directory'; the
            operations of one case are folded into it, so 'Run' and
            'Build' of the same case stand in one row.

    Another machine's rows are passed over (B-11): its milliseconds say
    nothing about this one's.
    """
    system  = system_key()
    case_db = {}
    for directory in directory_list:
        for key, row in TraceDb(directory).read().items():
            row_system, test, choice, operation = key
            if row_system != system: continue
            case = case_db.setdefault((directory, test, choice), {})
            case["directory"], case["test"], case["choice"] = \
                directory, test, choice
            case.setdefault("day", row.get("day", ""))
            for name in ("duration_ms", "cpu_time_ms", "peak_memory_mb"):
                value = row.get(name, "")
                if value: case["%s.%s" % (operation, name)] = value
    return [case_db[key] for key in sorted(case_db)]


def _ms_of(case, operation):
    """RETURN: float, that operation's milliseconds for the case;
              None, where it holds none."""
    text = case.get("%s.duration_ms" % operation, "")
    try:    return float(text)
    except  ValueError: return None


def traditional_line_list_of(row_list, show_directory_f):
    """
    RETURN: list of str, the traditional report: '<test> <choice>' left,
            the run's milliseconds right, the build's in brackets after
            it where one stands, then the count and the summed run time.

    The columns are as wide as the widest name, so the numbers line up
    under one another.
    """
    name_list = []
    for case in row_list:
        name = case["test"]
        if case["choice"]:  name += " " + case["choice"]
        if show_directory_f: name = os.path.join(case["directory"], name)
        name_list.append(name)
    width     = max([len(name) for name in name_list], default=0)
    line_list = []
    total_ms  = 0.0
    for name, case in zip(name_list, row_list):
        run_ms   = _ms_of(case, "Run")
        build_ms = _ms_of(case, "Build")
        if run_ms is not None: total_ms += run_ms
        text = "%-*s  %8s" % (width, name,
                              "-" if run_ms is None else "%d" % run_ms)
        if build_ms is not None: text += " [%d]" % build_ms
        line_list.append(text)
    line_list.append("")
    line_list.append("%d case(s), %.2f s" % (len(row_list), total_ms / 1000.0))
    return line_list


def table_line_list_of(row_list):
    """
    RETURN: list of str, the CSV: a header row, then one row per case --
            every column the traces hold, the operations spelt
            'Run.duration_ms' and so on. Empty where a case holds none.
    """
    field_list = ["directory", "test", "choice", "day"]
    for operation in ("Build", "Run"):
        for name in ("duration_ms", "cpu_time_ms", "peak_memory_mb"):
            field_list.append("%s.%s" % (operation, name))
    line_list = [";".join(field_list)]
    for case in row_list:
        line_list.append(";".join(str(case.get(name, ""))
                                  for name in field_list))
    return line_list


def do(directory=".", table_f=False, recursive_f=False, out_path=None,
       write=print):
    """
    RETURN: E_ExitCode.OK,      the report is written.
            E_ExitCode.EMPTY,   no trace of this machine stands there --
                                a fresh tree, or a suite this machine has
                                never run. Said, not faulted.
            E_ExitCode.REFUSED, the directory does not stand, or the
                                output file cannot be written.
    """
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        return E_ExitCode.REFUSED
    row_list = row_list_of(directory_list_of(directory, recursive_f))
    if not row_list:
        write("EMPTY: no timing of this machine stands in '%s'"
              % directory)
        return E_ExitCode.EMPTY
    line_list = table_line_list_of(row_list) if table_f \
                else traditional_line_list_of(row_list, recursive_f)
    if out_path is None:
        for line in line_list: write(line)
        return E_ExitCode.OK
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(line_list) + "\n")
    except OSError as error:
        write("REFUSED: '%s' cannot be written -- %s" % (out_path, error))
        return E_ExitCode.REFUSED
    write("written: %s" % out_path)
    return E_ExitCode.OK


def main(argv=None):
    """RETURN: E_ExitCode, as 'do' gives it; REFUSED where the command
               line itself is not understood."""
    argv = list(sys.argv if argv is None else argv)[1:]
    if "--help" in argv:
        print(__doc__.split("PURPOSE", 1)[1].rstrip())
        return E_ExitCode.OK
    directory, out_path = ".", None
    table_f = recursive_f = False
    index = 0
    while index < len(argv):
        word = argv[index]; index += 1
        if   word == "--table":                table_f = True
        elif word in ("-r", "--recursive"):    recursive_f = True
        elif word == "-o":
            if index >= len(argv):
                print("REFUSED: '-o' stands without a file")
                print(USAGE)
                return E_ExitCode.REFUSED
            out_path = argv[index]; index += 1
        elif word.startswith("-o="):           out_path  = word[3:]
        elif word.startswith("--directory="):  directory = word[12:]
        else:
            print("REFUSED: '%s' is no word of 'hwut.report.timings'" % word)
            print(USAGE)
            return E_ExitCode.REFUSED
    return do(directory=directory, table_f=table_f,
              recursive_f=recursive_f, out_path=out_path)


if __name__ == "__main__":
    sys.exit(guarded("hwut.report.timings", main))
