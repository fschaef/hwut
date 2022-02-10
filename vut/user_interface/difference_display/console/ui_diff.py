"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.user_interface.difference_display.console.canvas import ConsoleCanvasDiff, E_LinePairSelectionMode
from   vut.engine.compare.engine.chunk_pair                 import ChunkPair
from   vut.engine.compare.engine.line_pair                  import LinePair
import vut.system.keyboard                                  as     keyboard
from   vut.external.quex.typed                              import typed

class ConsoleCanvasDiffUI(ConsoleCanvasDiff):
    def interact(self):
        delta_horizontal = 5 # int(canvas.width / 8)
        delta_vertical   = 5 # int(canvas.height / 8)
        self.set_mode(E_LinePairSelectionMode.ERRORS, verbosity_level=2)
        while 1 + 1 == 2:
            self.show()
            while 1 + 1 == 2:
                key = keyboard.get()
                if   key == 'q': return
                elif key == 'a': self._add_horizontal_offset(- delta_horizontal); break
                elif key == 'd': self._add_horizontal_offset(delta_horizontal); break
                elif key == 'w': self._add_vertical_offset(- delta_vertical); break
                elif key == 's': self._add_vertical_offset(delta_vertical); break
                elif key == 'A': self.set_mode(E_LinePairSelectionMode.ANALOGIES); break
                elif key == 'P': self.set_mode(E_LinePairSelectionMode.PLAIN); break
                elif key == 'E': self.set_mode(E_LinePairSelectionMode.ERRORS); break

