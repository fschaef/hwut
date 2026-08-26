"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.show' COMMAND LINE -- what the framework READ. It
         checks the syntax, resolves the defaults, and prints the
         complete configuration as a tree (R-29, P-16); what an author
         wrote he can read himself.

    hwut.show                   the whole directory: 'hwut.conf' first,
                                then every test application
    hwut.show <source file>     one file's specification
    --no-default                drop every value nobody stated
    --provenance                name the place of every stated value
    --gnu                       name it as 'file:line:column'
    --directory=<path>          where to read; the current one else
    --help                      this text

The plan -- what the framework INTENDS -- is 'hwut.plan', a face of its
own. Faults print before the tree and set the exit status; a file whose
specification carries a fault yields its faults and no tree, since
exploration refuses rather than guesses.
______________________________________________________________________________
"""
import sys

from   vut.engine.orchestrator.exploration.hwut_parse import (text_of_directory,
                                                              text_of_file)
from   vut.engine.bookkeeper.test_id_db               import (TestIdDb,
                                                              TestIdFault)
from   ._exit                                         import E_ExitCode


USAGE = "usage: hwut.show [<source file>] [--no-default] " \
        "[--provenance] [--gnu] [--directory=<path>]"

HELP = """hwut.show -- the configuration the framework READ

    hwut.show                   the whole directory: 'hwut.conf' first,
                                then every test application as a tree
    hwut.show <source file>     one file's specification
    hwut.show --show-ids        the TEST REGISTER: every registered
                                application and choice with its id;
                                a registered application whose file
                                is ABSENT is marked VANISHED

OPTIONS
    --show-ids          print the register instead of the tree
    --no-default        drop every value nobody stated, leaving what
                        somebody chose
    --provenance        name the place of every stated value -- the
                        file and the line it stands on
    --gnu               name it in the GNU error format,
                        'file:line:column', which an editor jumps to
    --directory=<path>  the directory to read; the current one else
    --help              this text

What is shown is what the framework READ -- syntax checked, defaults
resolved -- not what was written. A specification carrying a fault
yields its faults and no tree. The printed form is the specification
language itself and can be read back (R-50).

The TEST PLAN -- what the framework intends to run -- is the service
'hwut.plan'.

EXIT STATUS
    0    nothing refused, no fault met
    1    a fault was met
    2    the command line cannot be read"""


def show_register(directory, write):
    """
    RETURN: E_ExitCode, OK -- also for an EMPTY register, which is a
            fresh directory and not a fault. FAULT where the register
            file itself cannot be read.

    Prints every registered application '[id] name', its choices
    beneath as '[id.id] choice'. A registered application whose FILE
    IS ABSENT is marked VANISHED: it left without 'hwut.remove', and
    healing is a service, never a guess.
    """
    try:
        id_db = TestIdDb(directory)
    except TestIdFault as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT

    write("==[ TEST REGISTER ]%s" % ("=" * 59))
    if len(id_db) == 0:
        write("(empty -- an id is born at first accept)")
        return E_ExitCode.OK

    vanished_db = dict(id_db.vanished())
    for app_id, name, choice_tuple in id_db.app_iterable():
        mark = "   VANISHED: no such file" \
               if app_id in vanished_db else ""
        write("[%i] %s%s" % (app_id, name, mark))
        for choice_id, choice in choice_tuple:
            write("    [%i.%i] %s" % (app_id, choice_id, choice))
    return E_ExitCode.OK


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where nothing was
            refused and no fault was met, FAULT where one was met,
            REFUSED where the command line itself cannot be read.

    'write' takes one line at a time; 'print' where none is given, so
    a test may capture the face without a process.
    """
    if write is None: write = print

    if argv is None: argv = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    directory  = "."
    option_set = set()
    name_list  = []
    for argument in argv:
        if argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument.startswith("-"):
            option_set.add(argument)
        else:
            name_list.append(argument)

    known_set = {"--no-default", "--provenance", "--gnu",
                 "--show-ids"}
    unknown   = sorted(option_set - known_set)
    if unknown:
        write("REFUSED: unknown option(s): %s" % ", ".join(unknown))
        write(USAGE)
        return E_ExitCode.REFUSED
    if len(name_list) > 1:
        write("REFUSED: %d source files named; 'hwut.show' reads one, "
              "or the directory" % len(name_list))
        write(USAGE)
        return E_ExitCode.REFUSED

    if "--show-ids" in option_set:
        return show_register(directory, write)

    no_default_f = "--no-default" in option_set
    provenance_f = "--provenance" in option_set
    gnu_f        = "--gnu"        in option_set

    if name_list:
        text, fault_list = text_of_file(directory, name_list[0],
                                        no_default_f, provenance_f,
                                        gnu_f)
    else:
        text, fault_list = text_of_directory(directory, None,
                                             no_default_f, provenance_f,
                                             gnu_f)
    for fault in fault_list:
        write(str(fault))
    if text:
        write(text)
    return E_ExitCode.FAULT if fault_list else E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
