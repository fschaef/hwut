"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.labels.query' COMMAND LINE -- the runs a label
         expression names (disc-8).

    hwut.labels.query [<expr>] [--expand] [--labels]
                      [--directory=<path>]

THE EXPRESSION: 'AND', 'OR', 'NOT', brackets; 'AND' binds tighter;
',' is sugar for 'OR'; 'all' is the universe of runs. A label that
does not stand is REFUSED BY NAME, never treated as an empty set:
'concren AND meta' silently naming nothing is how an author comes to
believe a set is empty. Bare, the expression is 'all AND NOT meta' --
what a bare run would take.

THE DEFAULT OUTPUT IS A WISHLIST, ready to be read back: target lines,
their paths written FROM THE DIRECTORY YOU STAND IN, sorted, ELIDED (':/' the previous line's directory, ':/:' its file),
and nothing else -- it pipes into '--wishlist', 'hwut.labels.add' and
'hwut.labels.remove'. Never a glob: the file it answers from holds
literal targets only.

    --expand   the same runs, one FULL target per line: for eyes and
               for grep. Still a readable wishlist.
    --labels   each run with the labels it carries -- an interior ':'
               stands on the line, which no wishlist reader takes:
               NOT for making a wishlist, for looking.

THE DOMAIN IS WHAT THE TREE OFFERS below '--directory': 'NOT concern'
names the unlabelled too, which only a walked tree can answer. An
entry naming a run the tree no longer offers is not printed here;
finding it is 'hwut.sanitize.propose --orphans' business (E-18).

EXIT STATUS (E-1, services/_exit.py):
    0  OK       the expression named at least one run; printed
    1  FAULT    a fault was met; the face still printed what stands
    2  REFUSED  the command line cannot be read, or a named label
                does not stand
    3  EMPTY    the expression reads, and names nothing
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.orchestrator.exploration.tree_explorer \
                                             import RootConfMissing
from   vut.engine.orchestrator.exploration   import selection
from   vut.engine.orchestrator.plan.label    import (STANDARD_LABEL,
                                                     UNIVERSE_NAME,
                                                     LabelExprError,
                                                     evaluate_f,
                                                     label_name_tuple,
                                                     parse_expression)
from   ..._core                               import usage_line
from   ..._exit                               import E_ExitCode
from   .                                     import _file
from   .                                     import _faces

USAGE = usage_line("usage: hwut.labels.query",
                   ("[<expr>]", "[--expand]", "[--labels]",
                    "[--directory=<path>]"))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n" + USAGE

DEFAULT_EXPRESSION = "%s AND NOT %s" % (UNIVERSE_NAME, STANDARD_LABEL)


def named_key_tuple(directory, view, tree):
    """
    RETURN: [0] tuple[(str, str | None)], every run the tree offers
                that answers the expression, as labels-file entry
                keys, SORTED in the file's own order.
            [1] tuple[Fault], the walk's own faults.

    The domain is the WALKED TREE, not the file: 'NOT <label>' names
    the unlabelled runs too, and only the tree can say who they are.
    """
    root     = os.path.abspath(directory)
    prefix   = os.path.relpath(root, view.boundary)
    found    = selection.all_of_tree(root)
    key_list = []
    for entry in found.case_list:
        joined = os.path.normpath(
            os.path.join(prefix, entry.directory,
                         entry.case.source_file))
        file   = joined.replace(os.sep, "/")
        label_set = view.label_set_of(
            os.path.join(view.boundary, file), entry.case.choice)
        if evaluate_f(tree, label_set):
            key_list.append((file, entry.case.choice))
    return (tuple(sorted(set(key_list), key=_file.sort_key)),
            found.fault_tuple)


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).

    A fault does not withhold the output: this face only reads, so it
    prints the fault, then what stands, and answers FAULT.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from vut.services._core import man_page
        write(man_page("hwut.labels.query", HELP))
        return E_ExitCode.OK

    expand_f  = False
    labels_f  = False
    directory = "."
    text_list = []
    for argument in argv:
        if   argument == "--expand": expand_f = True
        elif argument == "--labels": labels_f = True
        elif argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument.startswith("--"):
            write("REFUSED: 'hwut.labels.query' does not take: %s"
                  % argument)
            write(USAGE)
            return E_ExitCode.REFUSED
        else:
            text_list.append(argument)
    if len(text_list) > 1:
        write("REFUSED: ONE expression holds the whole question; "
              "quote it: '%s'" % " ".join(text_list))
        write(USAGE)
        return E_ExitCode.REFUSED
    text = text_list[0] if text_list else DEFAULT_EXPRESSION

    try:
        tree = parse_expression(text)
    except LabelExprError as error:
        write("REFUSED: '%s' cannot be read -- %s" % (text, error))
        write(USAGE)
        return E_ExitCode.REFUSED

    try:
        boundary = _file.boundary_of(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    try:
        entry_db = _file.read_entry_db(boundary)
    except _file.LabelFileError as error:
        write("FAULT: %s" % error)
        return E_ExitCode.FAULT
    view    = _file.view_of(boundary, entry_db)
    unknown = [name for name in label_name_tuple(tree)
               if name not in view.defined]
    if unknown:
        write("REFUSED: no label '%s' stands in 'hwut-root.labels'"
              % "', '".join(unknown))
        return E_ExitCode.REFUSED

    key_tuple, fault_tuple = named_key_tuple(directory, view, tree)
    for fault in fault_tuple: write("FAULT: %s" % fault)

    #  WHAT WAS ASKED, ANSWERED (E-106): the targets and their labels,
    #  said three ways; the page picks one.
    #  SAID FROM WHERE THE CALLER STANDS (ruled 2026-10-09, f-7): the
    #  label file names a run from the boundary; a line printed here is
    #  typed, or piped into '--wishlist', from the current directory.
    here = lambda target: from_here(target, view.boundary)   # noqa: E731
    answer = _faces.Answer(
        target_tuple = tuple(
            (here(_file.target_text(key)),
             " ".join(sorted(view.label_set_of(
                 os.path.join(view.boundary, key[0]), key[1]))) or "-")
            for key in key_tuple),
        elided_tuple = tuple(here(target) for target
                             in _file.elided_target_tuple(key_tuple)),
        fault_tuple  = tuple(str(f) for f in fault_tuple))
    printed(answer, labels_f, expand_f, write)

    if answer.fault_tuple: return E_ExitCode.FAULT
    if answer.empty_f:     return E_ExitCode.EMPTY
    return E_ExitCode.OK


def from_here(target, boundary):
    """RETURN: str, 'target' -- '<path> [<choice>]', its path written
               from the boundary -- with the path written from the
               current directory instead: 'test-a.sh' for a run of the
               directory the caller stands in, '../x/TEST/test-a.sh'
               for one beside it.
    """
    path, _, rest = target.partition(" ")
    #  A DITTO (':/:', the line above's path again) names no path.
    if path.startswith(":"): return target
    path = os.path.relpath(os.path.join(boundary, path))
    return path + (" " + rest if rest else "")


def printed(answer, labels_f, expand_f, write):
    """RETURN: None. The page 'hwut.labels.query' has always written:
               the targets with their labels under '--labels', one
               target per line under '--expand', the elided form else."""
    if labels_f:
        width = max((len(target) for target, _ in answer.target_tuple),
                    default=0)
        for target, label_text in answer.target_tuple:
            write("%-*s : %s" % (width, target, label_text))
    elif expand_f:
        for target, _ in answer.target_tuple: write(target)
    else:
        for target in answer.elided_tuple:    write(target)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.labels.query", main))
