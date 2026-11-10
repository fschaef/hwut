"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.register' COMMAND LINE -- what the feature
         files and the links disagree about (spec 43 section 6; intend/43
         T-h). It adds nothing by itself: there is no position to read an
         id out of; the author writes the forest and the doc file.

    hwut.features.register [--directory=<path>]

NAMES, one NOTE each, with 'did you mean' where a known id is near:

    a feature documented and standing in no forest line
    a ROOT of the forest that no doc block explains
    a link of a test run to an id that stands nowhere, or a retired one
    a file of the past ('hwut-features.conf', 'hwut-root-features.conf',
    'hwut-feature-map.conf'), read by nothing

A non-root with no documentation is silent: a child may lean on its
parent's sentence. A rename is 'hwut.features.rename'.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       nothing disagrees, or only notes are named
    1  FAULT    a feature file states a fault; it is named
    2  REFUSED  no 'hwut-root.conf', no forest ('hwut.features.init'), or
                the command line cannot be read
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_detector import detect
from hwut.engine.orchestrator.exploration.feature_view \
                                         import view_of, ViewRefused
from hwut.engine.orchestrator.exploration.tree_explorer \
                                         import forest_note_tuple
from ..._core                            import usage_line
from ..._exit                            import E_ExitCode
from .                                   import _common

NAME  = "hwut.features.register"
USAGE = usage_line("usage: %s" % NAME, ("[--directory=<path>]",))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    try:
        write, directory, rest = _common.opened(NAME, argv, write, HELP)
        if rest:
            write("REFUSED: '%s' does not take: %s"
                  % (NAME, ", ".join(rest)))
            write(USAGE)
            return E_ExitCode.REFUSED
        root = _common.root_of(directory, write)
    except _common.Refused as refusal:
        return refusal.exit_code
    try:
        view = view_of(root)
    except ViewRefused as refusal:
        text = str(refusal)
        write(text if text.startswith("FAULT") else "REFUSED: %s" % text)
        return E_ExitCode.FAULT if text.startswith("FAULT") \
               else E_ExitCode.REFUSED
    note_list = detect(view)
    for each in note_list:
        write(each.text)
    if not note_list:
        write("nothing disagrees")
    #  A BUBBLE BELOW WITH A FOREST OF ITS OWN (E-200): named, not passed
    #  in silence (book D-76); one without is this forest's.
    for note in forest_note_tuple(root):
        write(note)
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
