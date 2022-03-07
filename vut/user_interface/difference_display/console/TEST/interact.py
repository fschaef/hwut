"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
import sys

sys.path.insert(0, "../../../../..")

import vut.user_interface.difference_display.console.TEST.cases as     cases
import vut.engine.compare.main                                  as     compare
from   vut.engine.compare.configuration                         import Configuration
from   vut.engine.compare.engine.chunk_pair_list    import ChunkPairList
import vut.user_interface.difference_display.console.main       as     console
from   vut.user_interface.difference_display.console.canvas     import E_LinePairSelectionMode
import vut.user_interface.difference_display.console.prepare    as     prepare
import vut.system.terminal.core_size                                 as     terminal_size

from   io import StringIO

def test(subject_txt, nominal_txt, offset=0, mode=E_LinePairSelectionMode.PLAIN, level=0, both=True):
    subject = StringIO(subject_txt)
    nominal = StringIO(nominal_txt)

    la = list(compare.associate(cases.config, subject, nominal))

    la_list = ChunkPairList(la)
    if   "diff" in sys.argv:  console.diff(la_list)
    elif "merge" in sys.argv: console.merge(la_list)
    elif "test" in sys.argv:  cases.test(subject_txt, nominal_txt)
    else:                     print("Specify 'diff' or 'merge' on command line.")

test(cases.subject_txt + "\n" + "\n" + cases.nominal_txt, cases.nominal_txt * 2)
