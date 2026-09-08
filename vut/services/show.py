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
    --root-conf-template        the 'hwut-root.conf' the boundary face
                                would write -- the language table
                                (E-25) -- for pasting into a root conf
                                placed by hand; reads nothing
    --help                      this text

The plan -- what the framework INTENDS -- is 'hwut.plan', a face of its
own. Faults print before the tree and set the exit status; a file whose
specification carries a fault yields its faults and no tree, since
exploration refuses rather than guesses.
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.orchestrator.exploration.hwut_parse import (text_of_directory,
                                                              text_of_file)
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                      import (RootConfMissing,
                                                              root_conf_directory)
from   vut.engine.orchestrator.plan.label             import STANDARD_LABEL
from   vut.services.lib.labels                            import _file
from   vut.engine.bookkeeper.api               import (Bookkeeper,
                                                              TestIdFault)
from   ._exit                                         import E_ExitCode
from   ._target                                       import entered


USAGE = "usage: hwut.show [<source file>] [--no-default] " \
        "[--provenance] [--gnu] [-v|--verbose] [--directory=<path>] | " \
        "hwut.show --root-conf-template"

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
    -v, --verbose       write the NULL parameters too. Absent, a null
                        is not written -- "nothing set here" is what
                        every unwritten line already says -- and a
                        scope ('build', 'caps') whose every member is
                        null is not written either
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
        bookkeeper = Bookkeeper(directory)
        roster     = bookkeeper.roster()
    except TestIdFault as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT

    write("==[ TEST REGISTER ]%s" % ("=" * 59))
    if not roster:
        write("(empty -- an id is born at first accept)")
        return E_ExitCode.OK

    vanished_db = dict(bookkeeper.vanished())
    for app_id, name, choice_tuple in bookkeeper.app_iterable():
        mark = "   VANISHED: no such file" \
               if app_id in vanished_db else ""
        write("[%i] %s%s" % (app_id, name, mark))
        for choice_id, choice in choice_tuple:
            write("    [%i.%i] %s" % (app_id, choice_id, choice))
    return E_ExitCode.OK


def labels_line_tuple(directory, name):
    """
    RETURN: [0] tuple[str], the '==[ LABELS ]' section for the tests
                of 'directory' -- of the one file 'name', where one is
                named -- each entry as the labels file states it, THE
                SILENT ONES MARKED: the failure mode of every label
                mechanism is a test that silently does not run, and a
                person looking at a test that seems not to exist must
                find the answer in the first place they look (disc-8).
                Empty where no entry concerns what is shown -- the
                feature unused costs no line of output.
            [1] str | None, the fault where 'hwut-root.labels' cannot
                be read; the section is then the fault's alone.

    NO BOUNDARY, NO SECTION: 'hwut.show' works on a bare directory,
    and a tree without a root conf can hold no labels file.
    """
    try:
        boundary = root_conf_directory(directory)
    except RootConfMissing:
        return (), None
    if not os.path.isfile(_file.file_path(boundary)):
        return (), None
    try:
        entry_db = _file.read_entry_db(boundary)
    except _file.LabelFileError as error:
        return (), "FAULT: %s" % error

    where = os.path.relpath(os.path.abspath(directory), boundary)
    where = "" if where == "." else where.replace(os.sep, "/")
    def local_f(key):
        head, _, tail = key[0].rpartition("/")
        return head == where and (name is None or tail == name)
    key_list = sorted((key for key in entry_db if local_f(key)),
                      key=_file.sort_key)
    if not key_list: return (), None

    line_list = ["==[ LABELS ]%s" % ("=" * 66)]
    shown = [("%s%s" % (key[0].rpartition("/")[2],
                        "" if key[1] is None else " %s" % key[1]),
              entry_db[key])
             for key in key_list]
    width = max(len(target) for target, _ in shown)
    for target, label_set in shown:
        line = "%-*s : %s" % (width, target,
                              " ".join(sorted(label_set)))
        if STANDARD_LABEL in label_set:
            line += "   -- SILENT: a bare wish passes this by"
        line_list.append(line)
    return tuple(line_list), None


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
    if "--root-conf-template" in argv:
        from vut.services._boundary import ROOT_CONF_TEXT
        for line in ROOT_CONF_TEXT.rstrip("\n").split("\n"): write(line)
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

    known_set = {"--no-default", "--provenance", "--gnu", "-v", "--verbose",
                 "--show-ids"}
    unknown   = sorted(option_set - known_set)
    if unknown:
        write("REFUSED: unknown option(s): %s" % ", ".join(unknown))
        write(USAGE)
        return E_ExitCode.REFUSED
    #  A TEST NAMED BY PATH IS ENTERED ('services/_target.py', E-47).
    found = entered(name_list, directory, write, USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, name_list = found
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
    verbose_f    = "-v" in option_set or "--verbose" in option_set

    if name_list:
        text, fault_list = text_of_file(directory, name_list[0],
                                        no_default_f, provenance_f,
                                        gnu_f, verbose_f)
    else:
        text, fault_list = text_of_directory(directory, None,
                                             no_default_f, provenance_f,
                                             gnu_f, verbose_f)
    for fault in fault_list:
        write(str(fault))
    if text:
        write(text)
    label_line_tuple, label_fault = labels_line_tuple(
        directory, name_list[0] if name_list else None)
    if label_fault is not None:
        write(label_fault)
    for line in label_line_tuple:
        write(line)
    if fault_list or label_fault is not None:
        return E_ExitCode.FAULT
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
