import sys

sys.path.insert(0, "../../../../..")

import vut.user_interface.difference_display.console.TEST.cases as     cases
import vut.engine.compare.main                                  as     compare
from   vut.engine.compare.configuration                         import Configuration
from   vut.engine.compare.engine.line_association_chunk_list    import LineAssociationChunkList
import vut.user_interface.difference_display.console.main       as     console
from   vut.user_interface.difference_display.console.canvas     import ConsoleCanvasDiff, E_DiffMode
import vut.system.terminal_size                                 as     terminal_size

from   io import StringIO

config = Configuration()
config.pattern_finder.numeric_tolerance_ratio = 0.01
config.pattern_finder.equivalent_pattern_list = ["rot|orange", "Röslein|Tülplein"]
config.pattern_finder.visible_nothing_pattern_list = [", hm,", ", wtf,", "[ ]*\(who cares\)"]


def test(subject_txt, nominal_txt, offset=0, mode=E_DiffMode.PLAIN, level=0, both=True):
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)
    la = list(compare.line_associations(config, subject, nominal))

    if   "diff" in sys.argv:  console.diff(LineAssociationChunkList(la))
    elif "merge" in sys.argv: console.merge(LineAssociationChunkList(la))
    else:                     print("Specify 'diff' or 'merge' on command line.")

test(cases.subject_txt + "\n" + "\n" + cases.nominal_txt, cases.nominal_txt * 2)
