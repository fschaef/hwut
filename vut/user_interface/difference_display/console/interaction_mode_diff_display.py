"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.user_interface.difference_display.console.interaction_mode import InteractionMode
from   vut.user_interface.difference_display.console.canvas           import E_LinePairSelectionMode
from   vut.system.terminal.core                                       import ConsoleCanvas, \
                                                                             LEFT, RIGHT, \
                                                                             Fore, Back
from   vut.external.quex.typed                                        import typed
from   vut.engine.constants                                           import E_Side

class InteractionModeDiff(InteractionMode):
    def init(self):
        self.name = "difference"

    def do(self, key):
        if   self._exit(key):          return False
        elif self._move_commands(key): pass
        elif key == 'm': self.canvas.set_interaction(InteractionModeSpecifySelection)
        elif key == ' ': self.canvas.set_interaction(InteractionModeMark)
        return True

    def get_status_line_content(self):
        key_txt = "[q] quit [h] help [w] up [s] down [a] left [d] right [m] selection mode [space] mark"
        return key_txt, self.name

class InteractionModeSpecifySelection(InteractionMode):
    def init(self):
        self.name = "mode select"

    def get_status_line_content(self):
        key_txt = "[p] plain [d] deviations [e] errors [a] analogies [A] a.-errs. [D] a.-defs. [0,1,2] verbosity level [y] accept"
        return key_txt, self.name

    def do(self, key):
        if   self._exit(key): self.canvas.set_interaction(InteractionModeDiff)
        elif key == 'p':      self.canvas.set_selection_mode(E_LinePairSelectionMode.PLAIN)
        elif key == 'd':      self.canvas.set_selection_mode(E_LinePairSelectionMode.ERRORS_AND_TOLERATED)
        elif key == 'e':      self.canvas.set_selection_mode(E_LinePairSelectionMode.ERRORS)
        elif key == 'a':      self.canvas.set_selection_mode(E_LinePairSelectionMode.ANALOGIES)
        elif key == 'A':      self.canvas.set_selection_mode(E_LinePairSelectionMode.ANALOGIES_ERRORS_ONLY)
        elif key == 'D':      self.canvas.set_selection_mode(E_LinePairSelectionMode.ANALOGIES_DEFINITIONS_ONLY)
        elif key == '0':      self.canvas.set_verbosity_level(0)
        elif key == '1':      self.canvas.set_verbosity_level(1)
        elif key == '2':      self.canvas.set_verbosity_level(2)
        elif key == 'y':      self.canvas.set_interaction(InteractionModeDiff)
        else:                 return True
        return True


class InteractionModeMark(InteractionMode):
    def init(self):
        self.name = "mode mark"
        self.canvas.cursor_init()

    def get_status_line_content(self):
        key_txt = "[q] quit mark mode [space] mark begin/end [w/s] up/down [a/d] switch side"
        return key_txt, self.name

    def do(self, key):
        if   self._exit(key):                 self.canvas.set_interaction(InteractionModeDiff)
        elif self._cursor_move_commands(key): pass
        elif key == ' ':                      self.canvas.cursor_iterate_focus()
        return True

    def _cursor_move_commands(self, key):
        """RETURNS: True, if a 'move key' has been pressed.
                    False, else.
        """
        if   key == 'a': self.canvas.cursor_switch_side();  return True
        elif key == 'd': self.canvas.cursor_switch_side();  return True
        elif key == 's': self.canvas.cursor_add_line_n(1);  return True
        elif key == 'w': self.canvas.cursor_add_line_n(-1); return True
        else:            return False
