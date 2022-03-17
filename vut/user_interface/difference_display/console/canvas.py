"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
from   vut.user_interface.difference_display.console.interaction_mode import InteractionMode
import vut.user_interface.difference_display.console.formatter        as     formatter
import vut.user_interface.difference_display.console.prepare          as     prepare

from   vut.engine.compare.engine.chunk_pair        import ChunkPair
from   vut.engine.compare.engine.chunk_pair_list   import ChunkPairList
from   vut.engine.compare.engine.line_pair         import LinePair
from   vut.engine.compare.engine.line_pair_list    import LinePairList
from   vut.engine.compare.engine.core              import E_PotpourriBorder
from   vut.engine.compare.edit_operations.edit     import E_EditId, Edit

from   vut.external.quex.typed  import typed
from   vut.system.helper        import number_of_decimal_digits
from   vut.system.terminal.core import ConsoleCanvas, LEFT, RIGHT, FIXED, Fore, Back
import vut.system.keyboard      as     keyboard

from   copy import copy
from   math import ceil

E_LinePairSelectionMode = prepare.E_LinePairSelectionMode

class Data:
    def __init__(self, chunk_pair_list):
        self.selection_mode    = E_LinePairSelectionMode.PLAIN
        self.__chunk_pair_list = chunk_pair_list
        self.line_pair_list    = None

    def select_line_pair_list(self, mode, verbosity_level):
        self.selection_mode  = mode
        # Select the line pairs which are relevant for the given selection mode
        self.line_pair_list  = prepare.select(self.selection_mode, 
                                              self.__chunk_pair_list, 
                                              verbosity_level)
        prepare.plug_end(self.line_pair_list)


class ConsoleUI(ConsoleCanvas):
    @typed(chunk_pair_list=ChunkPairList, interaction_mode=type)
    def __init__(self, chunk_pair_list, interaction_mode):
        ConsoleCanvas.__init__(self)
        self.data         = Data(chunk_pair_list)
        self._analogy_db  = chunk_pair_list[-1].analogy_db()

        line_n_width      = number_of_decimal_digits(chunk_pair_list[-1].max_line_n())
        self.format       = formatter.ConsoleCanvasFormatter(line_n_width, 0, self)
        self.cache_db     = {}
        
        self.__begin_line_pair_i = 0
        self.__max_line_length   = 0
        self.set_interaction(interaction_mode)

    def interact(self):
        assert self.interaction is not None
        while 1 + 1 == 2:
            self.do()
            if not self.interaction.do(keyboard.get()):
                return

    def set_interaction(self, interaction_mode):
        self.interaction = interaction_mode(self)
        self.interaction.init()

    @typed(mode=E_LinePairSelectionMode)
    def set_selection_mode(self, mode, verbosity_level=2):
        self.data.select_line_pair_list(mode, verbosity_level)

    def do(self):
        displayed_line_n = self._display_content()
        self._display_fill_empty(displayed_line_n)
        self._display_status_line()

    def _display_content(self):
        if self.height < 1:
            return 0

        L     = len(self.data.line_pair_list)
        begin = self.__begin_line_pair_i
        end   = min(begin + self.height - 1, L)
        if end <= begin:
            return 0

        for lip_i, line_pair in self.data.line_pair_list.enumerate(begin, end):
            formatted = self.cache_db.get(lip_i)
            if formatted is None:
                formatted = self._prepare_LinePair(line_pair, lip_i)
                self.cache_db[lip_i] = formatted
            self.print_line(formatted)

        return end

    def _display_fill_empty(self, diplayed_line_n):
        if diplayed_line_n >= self.height:
            return
        empty_formatted = self._prepare_LinePair(
            prepare.LinePairDecorated(0, 0, LinePair.empty(None)))
        for line_i in range(diplayed_line_n, self.height - 1):
            self.print_line(empty_formatted)

    def _display_status_line(self):
        def _percentage():
            L = len(self.data.line_pair_list)
            if L == 0:     ratio = 1
            else:          ratio = min(L, self.__begin_line_pair_i + self.height) / L
            if ratio == 1: return "100" + "%"
            else:          return "% 3i" % int(ceil(ratio*100)) + "%"

        remainder   = self.width - 3 # '4' spaces
        percentage  = _percentage()
        remainder  -= 4 # percentage: 4 chars

        key_txt, mode_name = self.interaction.get_status_line_content()
        L_key_txt  = len(key_txt)
        if L_key_txt > remainder: key_txt = key_txt[:remainder]
        remainder -= L_key_txt

        L_mode     = len(mode_name)
        if L_mode > remainder: mode_name = mode_name[:remainder]
        remainder -= L_mode

        selection_mode   = self.data.selection_mode.name.lower()
        L_selection_mode = len(selection_mode)
        if L_selection_mode > remainder - 2: selection_mode = selection_mode[:remainder-2]
        remainder -= L_selection_mode + 2

        format_list = [
            FIXED(key_txt, "Bg"), 
            FIXED(" ", "Wg"),
            FIXED(" " * remainder, "Wg"),
            FIXED(mode_name, "Bg"),
            FIXED(" ", "Bg"),
            FIXED("[%s]" % selection_mode, "Bg"),
            FIXED(" ", "Bg"),
            FIXED(percentage, "Bg")
        ]

        lp_list = self.prepare(format_list)
        self.print_line(lp_list)

    def _add_horizontal_offset(self, value):
        if self.__max_line_length - (self.format.text_offset + value) <= 0:
            return
        self.format.add_text_offset(value)
        self.cache_db.clear()
        self.__max_line_length = 0

    def _add_vertical_offset(self, value):
        L         = len(self.data.line_pair_list)
        new_value = self.__begin_line_pair_i + value
        last_i    = L - (self.height - 1) # 1 -> status line
        self.__begin_line_pair_i = max(0, min(new_value, last_i))
        
    def _prepare_LinePair(self, lip, lip_i=None):
        """Displays a formatted line of an association of a subject line with a 
        nominal line.
        """
        self.__max_line_length,  \
        subject_txt,             \
        nominal_txt              = formatter.do_line_elements(self.__max_line_length, lip, lip_i)

        if lip.filler_f:
            line = self.prepare(self.format.filler)
        elif lip.border != E_PotpourriBorder.NONE:
            line = self._prepare_potpourri_border(lip)
        elif lip.subject is None and lip.nominal is None:
            if lip.subject_end_f and lip.nominal_end_f: f = self.format.both_end
            elif lip.subject_end_f:                     f = self.format.subject_end_nominal_empty
            elif lip.nominal_end_f:                     f = self.format.nominal_end_subject_empty
            else:                                       f = self.format.empty
            line = self.prepare(f)
        elif lip.subject is None:
            if lip.subject_end_f: f = self.format.subject_end
            else:                 f = self.format.subject_empty
            line = self.prepare(f, ["%s" % lip.nominal.line_n, nominal_txt])
        elif lip.nominal is None:
            if lip.nominal_end_f: f = self.format.nominal_end
            else:                 f = self.format.nominal_empty
            line = self.prepare(f, [subject_txt, "%s" % lip.subject.line_n])
        else:
            def _line_n(line_n):
                return " " if line_n is None else "%s" % line_n         
            line = self.prepare(self.format.normal, 
                                [ subject_txt, 
                                  _line_n(lip.subject.line_n), 
                                  _line_n(lip.nominal.line_n), 
                                  nominal_txt])
        return line

    def _prepare_potpourri_border(self, lip):
        """Displays the border of a Potpourri region. 

        'begin_f' = True: display the OPENING of a potpourri region.
        else:             display the CLOSING of a potpourri region.
        """
        subject_line_n = "" if lip.subject is None else "%s" % lip.subject.line_n
        nominal_line_n = "" if lip.nominal is None else "%s" % lip.nominal.line_n
        if lip.border == E_PotpourriBorder.BEGIN: f = self.format.potpourri_begin
        else:                                     f = self.format.potpourri_end
        return self.prepare(f, [subject_line_n, nominal_line_n])

