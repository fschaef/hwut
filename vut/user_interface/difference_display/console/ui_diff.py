"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.user_interface.difference_display.console.canvas import ConsoleCanvasDiff, \
                                                                   E_LinePairSelectionMode
from   vut.engine.compare.engine.chunk_pair_list            import ChunkPairList
from   vut.engine.compare.engine.chunk_pair                 import ChunkPair
from   vut.engine.compare.engine.line_pair                  import LinePair
import vut.system.keyboard                                  as     keyboard
from   vut.external.quex.typed                              import typed

class InteractionMode:
    def __init__(self, canvas):
        self.canvas = canvas

class InteractionModeDiff(InteractionMode):
    def init(self):
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
        elif key == 'S': self.canvas.set_mode(E_LinePairSelectionMode.ANALOGIES)
        elif key == 'P': self.canvas.set_mode(E_LinePairSelectionMode.PLAIN)
        elif key == 'E': self.canvas.set_mode(E_LinePairSelectionMode.ERRORS)
        else:            return True
        self.canvas.do()
        return True

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

class ConsoleCanvasDiffUI(ConsoleCanvasDiff):
    @typed(chunk_pair_list=ChunkPairList)
    def __init__(self, chunk_pair_list):
        ConsoleCanvasDiff.__init__(self, chunk_pair_list)
        self.mode = InteractionModeDiff(self)

    def interact(self):
        self.mode.init()
        while 1 + 1 == 2:
            if not self.mode.do(keyboard.get()):
                return
        

