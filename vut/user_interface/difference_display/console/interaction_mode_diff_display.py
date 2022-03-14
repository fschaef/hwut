"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.user_interface.difference_display.console.interaction_mode import InteractionMode
from   vut.user_interface.difference_display.console.canvas           import E_LinePairSelectionMode
from   vut.system.terminal.core                                       import ConsoleCanvas, \
                                                                             GLUE, LEFT, RIGHT, CENTER, FIXED, \
                                                                             Fore, Back
from   vut.external.quex.typed                                        import typed

class InteractionModeDiff(InteractionMode):
    def init(self):
        self.name = "difference"
        self.canvas.set_selection_mode(E_LinePairSelectionMode.ERRORS, verbosity_level=2)
        self.canvas.do()

    def do(self, key):
        delta_horizontal = 5 # int(canvas.width / 8)
        delta_vertical   = 5 # int(canvas.height / 8)
        if   key == 'q': return False
        elif key == 'a': self.canvas._add_horizontal_offset(- delta_horizontal)
        elif key == 'd': self.canvas._add_horizontal_offset(delta_horizontal)
        elif key == 'w': self.canvas._add_vertical_offset(- delta_vertical)
        elif key == 's': self.canvas._add_vertical_offset(delta_vertical)
        elif key == 'S': self.canvas.set_selection_mode(E_LinePairSelectionMode.ANALOGIES)
        elif key == 'P': self.canvas.set_selection_mode(E_LinePairSelectionMode.PLAIN)
        elif key == 'E': self.canvas.set_selection_mode(E_LinePairSelectionMode.ERRORS)
        else:            return True
        self.canvas.do()
        return True

    def get_status_line_content(self):
        key_txt = "[q] quit [h] help [w] up [s] down [a] left [d] right"

        return key_txt, self.name

class InteractionModeSpecifySelection(InteractionMode):
    def init(self):
        self.canvas.do()

    def do(self, key):
        delta_horizontal = 5 # int(canvas.width / 8)
        delta_vertical   = 5 # int(canvas.height / 8)
        if   key == 'q': return False
        elif key == 'S': self.canvas.set_mode(E_LinePairSelectionMode.ANALOGIES)
        elif key == 'P': self.canvas.set_mode(E_LinePairSelectionMode.PLAIN)
        elif key == 'E': self.canvas.set_mode(E_LinePairSelectionMode.ERRORS)
        else:            return True
        self.canvas.do()
        return True


