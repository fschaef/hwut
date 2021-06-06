"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
_______________________________________________________________________________

PURPOSE: Difftool command line

______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../../../../..")

import vut.engine.compare.main                            as     compare
from   vut.engine.compare.configuration                   import Configuration
import vut.user_interface.difference_display.console.main as     console

from   io import StringIO


subject = StringIO("Hallo")
nominal = StringIO("Welt")

config = Configuration()
console.display(compare.line_associations(config, subject, nominal))


