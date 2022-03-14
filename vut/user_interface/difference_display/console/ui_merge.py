"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.user_interface.difference_display.console.canvas   import ConsoleUI, E_LinePairSelectionMode
import vut.user_interface.difference_display.console.prepare  as     prepare
from   vut.engine.compare.engine.chunk_pair                   import ChunkPair
from   vut.engine.compare.engine.chunk_pair_list              import ChunkPairList
from   vut.engine.compare.engine.line_pair                    import LinePair
import vut.system.keyboard                                    as     keyboard
from   vut.external.quex.typed                                import typed
from   vut.external.quex.tools                                import print_callstack
from   vut.system.terminal.core                                    import Back

class ConsoleCanvasMergeUI(ConsoleUI):
    @typed(lina_chunk_list=ChunkPairList)
    def __init__(self, lina_chunk_list):
        ConsoleUI.__init__(self, lina_chunk_list)
        self._range_list    = None
        self._focus_range_i = None
        self._focus_cell_i  = None

    @typed(mode=E_LinePairSelectionMode)
    def set_mode(self, mode, verbosity_level=2):
        ConsoleUI.set_mode(self, mode, verbosity_level)
        self._range_list = prepare.get_Interval_list(self._lina_chunk_list)
        print_callstack()

    def set_focus_range_i(self, value):
        self._focus_range_i = value

    def set_focus_cell_i(self, value):
        self._focus_cell_i = value

    def split(self, part_n):
        """Splits the focus range into 'part_n' parts. The new focus
        range is the range at the beginning of the splitted ranges.
        """
        assert self._range_list is not None # 'set_mode()' must have been called

        split_range = self._range_list[self._focus_range_i]
        del self._range_list[self._focus_range_i]
        self._range_list.insert(self._focus_range_i, split_range.split(part_n))

    @typed(line_n=int)
    def _in_merge_range(self, line_n):
        """RETURNS: True, if line given by 'line_n' is in any merge range.
                    False, else.
        """
        return any(r.begin <= line_n < r.end for r in self._range_list)

    def _in_focus_range(self, line_n):
        """RETURNS: True, if line given by 'line_n' is in focus merge range.
                    False, else.
        """
        if self._focus_range_i is None: 
            return False
        else:
            r = self._range_list[self._focus_range_i]
            return r.begin <= line_n < r.end

    @typed(line=LinePair)
    def _format_line_elements(self, lina, lina_i):
        """RETURNS: [0] subject text: list of (color, text)
                    [1] nominal text: list of (color, text)

        This function is called by 'ConsoleCanvas._prepare_LinePair()'
        to format the output lines.  It provides basic text and format
        information to display the LineElements. That is, if a
        'LinePair' is element of a merge range, it is highlighted
        accordingly.
        """
        if lina_i is None:                     add_background_color = ""
        elif not self._in_merge_range(lina_i): add_background_color = "" 
        elif self._in_focus_range(lina_i):     add_background_color = Back,YELLOW
        else:                                  add_background_color = Back.BLUE
        return ConsoleUI._format_line_elements(self, lina, lina_i, add_background_color)
            
    def interact(self):
        delta_horizontal = 5 # int(canvas.width / 8)
        delta_vertical   = 5 # int(canvas.height / 8)
        self.set_mode(E_LinePairSelectionMode.PLAIN, verbosity_level=2)
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


