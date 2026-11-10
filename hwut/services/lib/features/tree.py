"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.tree' COMMAND LINE -- the forest of features
         (spec 43 section 5; intend/43 T-u).

    hwut.features.tree [<id>] [--list] [-e] [--directory=<path>]

prints the roots of 'hwut-feature-forest.csv' first, each feature's
children indented below it, every feature with its title from
'hwut-feature-doc.dat'. The unplaced -- documented, in no forest line --
follow under '(unplaced)'. Retired claims are not printed. A prototype's
instances stand in the trees as '<owner>+<id>', each with the title that
documents it (intend/44 p-5); the prototypes as declared, their members
below them, follow under '(prototypes)'.

    <id>        only the subtree of that feature
    --list      one feature id per line, the parent before its children:
                pasted into a label expression as 'f/<id>', or given to
                'hwut.report.features'
    -e          each feature with the outside's names for it, where
                'hwut-feature-external-map.csv' holds some

EXIT STATUS (E-1, services/_exit.py):
    0  OK       printed
    1  FAULT    a feature file states a fault; it is named
    2  REFUSED  no 'hwut-root.conf', no forest, an <id> the forest does not
                hold, or the command line cannot be read
    3  EMPTY    nothing to print
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_forest import ForestFault
from hwut.engine.orchestrator.exploration.feature_doc    import DocFault
from hwut.engine.orchestrator.exploration.feature_external \
                                         import ExternalFault
from hwut.engine.orchestrator.exploration.feature_forest import read_forest
from hwut.engine.orchestrator.exploration.feature_doc    import read_doc
from hwut.engine.orchestrator.exploration.feature_doc \
                                         import effective_entry
from hwut.engine.orchestrator.exploration.feature_external \
                                         import read_external
from hwut.engine.orchestrator.exploration.finder import FOREST_FILE_NAME
from ..._core                            import usage_line
from ..._exit                            import E_ExitCode
from ..cmdline                           import did_you_mean
from .                                   import _common

NAME  = "hwut.features.tree"
USAGE = usage_line("usage: %s" % NAME,
                   ("[<id>]", "[--list]", "[-e]", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    try:
        write, directory, rest = _common.opened(NAME, argv, write, HELP)
        root = _common.root_of(directory, write)
    except _common.Refused as refusal:
        return refusal.exit_code
    flag_set  = {each for each in rest if each.startswith("-")}
    base_list = [each for each in rest if not each.startswith("-")]
    unknown   = flag_set - {"--list", "-e"}
    if unknown or len(base_list) > 1:
        write("REFUSED: '%s' does not take: %s"
              % (NAME, ", ".join(sorted(unknown) + base_list[1:])))
        write(USAGE)
        return E_ExitCode.REFUSED
    try:
        forest = read_forest(root)
        if forest is None:
            write("REFUSED: no '%s' stands => hwut.features.init"
                  % FOREST_FILE_NAME)
            return E_ExitCode.REFUSED
        doc         = read_doc(root, forest)
        external_db = read_external(root, forest) or {}
    except (ForestFault, DocFault, ExternalFault) as fault:
        write(str(fault))
        return E_ExitCode.FAULT
    entry_db = doc.entry_db if doc is not None else {}
    if base_list:
        base = base_list[0]
        if base not in forest.id_set and base not in entry_db:
            write("REFUSED: '%s' stands in no forest line%s"
                  % (base, did_you_mean(base, sorted(forest.id_set
                                                     | set(entry_db)))))
            return E_ExitCode.REFUSED
        top_tuple, unplaced = (base,), ()
    else:
        top_tuple = forest.root_tuple
        #  A PROTOTYPE'S BLOCK, A MEMBER'S, AN INSTANCE'S are no unplaced
        #  feature (intend/44): they document what the forest expands.
        unplaced  = tuple(each for each in entry_db
                          if each not in forest.id_set
                          and "+" not in each
                          and not forest.prototype_f(each))
    line_list = []

    def walk(feature_id, depth):
        if "--list" in flag_set:
            line_list.append(feature_id)
        else:
            entry = effective_entry(entry_db, forest, feature_id)
            title = entry.title if entry is not None else ""
            line_list.append(("%s%s%s%s" % (
                "  " * depth, feature_id,
                "  " + title if title else "",
                "".join("  = %s" % each
                        for each in external_db.get(feature_id, ()))
                if "-e" in flag_set else "")).rstrip())
        for child in forest.children_of.get(feature_id, ()):
            walk(child, depth + 1)

    for each in top_tuple:
        walk(each, 0)
    if unplaced:
        if "--list" not in flag_set: line_list.append("(unplaced)")
        for each in unplaced:
            walk(each, 0 if "--list" in flag_set else 1)
    if not base_list and forest.prototype_db and "--list" not in flag_set:
        #  THE PROTOTYPES, as declared: what the instances are made of.
        line_list.append("(prototypes)")

        def walk_prototype(name, depth):
            entry = entry_db.get("+" + name)
            line_list.append(("%s+%s%s" % ("  " * depth, name, "  "
                              + entry.title if entry else "")).rstrip())
            for each in forest.prototype_db[name]:
                if each.startswith("+"):
                    walk_prototype(each[1:], depth + 1)
                    continue
                entry = entry_db.get(each)
                line_list.append(("%s%s%s" % ("  " * (depth + 1), each, "  "
                                  + entry.title if entry else "")).rstrip())

        for each in forest.prototype_db:
            if each not in forest.member_of: walk_prototype(each, 1)
    if not line_list:
        return E_ExitCode.EMPTY
    for line in line_list:
        write(line)
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
