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

from   vut.engine.constants     import E_Side
from   vut.external.quex.typed  import typed
from   vut.system.helper        import number_of_decimal_digits
from   vut.system.terminal.core import ConsoleCanvas, LEFT, RIGHT, FIXED, Fore, Back
import vut.system.keyboard      as     keyboard

from   copy import copy
from   math import ceil
from   typeguard import typechecked

E_LinePairSelectionMode = prepare.E_LinePairSelectionMode

DEBUG_fh = open("/tmp/tmp.log", "w")

class Data:
    def __init__(self, chunk_pair_list):
        self.selection_mode     = E_LinePairSelectionMode.PLAIN
        self.verbosity          = 2
        self.__chunk_pair_list  = chunk_pair_list
        self.line_pair_list     = None
        self.cache_db           = {}
        self.output_app_name    = "<test app>"
        self.output_choice_name = "<choice>"

    def select(self):
        self.line_pair_list  = prepare.select(self.selection_mode, 
                                              self.__chunk_pair_list, 
                                              self.verbosity)
        # Make sure that the line pairs are lined up at the end.
        prepare.plug_end(self.line_pair_list)
        self.cache_db.clear()

    def iterable(self, begin_lip_i, end_lip_i, reverse=False):
        if not reverse:
            yield from self.line_pair_list[begin_lip_i:end_lip_i]
        else:
            yield from reversed(self.line_pair_list[begin_lip_i:end_lip_i])

    def subject_end_line_n(self):
        try: 
            result = next(lip for lip in reversed(self.line_pair_list) if lip.subject).subject.line_n + 1
        except StopIteration:
            result = None
        return result

    def nominal_end_line_n(self):
        try: 
            result = next(lip for lip in reversed(self.line_pair_list) if lip.nominal).nominal.line_n + 1
        except StopIteration:
            result = None
        return result

class ConsoleUI(ConsoleCanvas):
    @typechecked
    def __init__(self, chunk_pair_list: ChunkPairList, interaction_mode: type):
        ConsoleCanvas.__init__(self)
        self.data        = Data(chunk_pair_list)
        self._analogy_db = chunk_pair_list[-1].analogy_db()

        line_n_width     = number_of_decimal_digits(chunk_pair_list[-1].max_line_n())
        self.format      = formatter.ConsoleCanvasFormatter(line_n_width, 0, self)
        self.displayed_line_pair_n = -1
        
        self.__begin_line_pair_i = 0
        self.__max_character_n   = 0
        self.set_interaction(interaction_mode)
        self.set_selection_mode(E_LinePairSelectionMode.PLAIN, 2)

    def xxx(self):
        begin_subject = self.data.line_pair_list[s_lip_i_0].subject 
        end_subject   = self.data.line_pair_list[s_lip_i_1].subject 
        begin_nominal = self.data.line_pair_list[n_lip_i_0].nominal 
        end_nominal   = self.data.line_pair_list[n_lip_i_1].nominal 
        assert begin_subject is not None
        assert end_subject is not None
        assert begin_nominal is not None
        assert end_nominal is not None
        transfer(begin_subject.line_n, end_subject.line_n, 
                 begin_nominal.line_n, end_nominal.line_n)

    def cursor_init(self):
        if self.format.cursor.virgin():
            lip_i = self._first_displayed_not_good_line_pair()
            if lip_i is None: lip_i = self.__begin_line_pair_i 
            lip_i_subject_end, lip_i_nominal_end = self._last_valid_line_pair_indices()
            self.format.cursor.init(lip_i, lip_i_subject_end, lip_i_nominal_end)
        else:
            self.format.cursor.set_initial_focus()

        self.data.cache_db.clear()

    def cursor_switch_side(self):
        self.format.cursor.switch_side()
        self.data.cache_db.clear()
        return self.format.cursor.focus_side

    def cursor_iterate_focus(self):
        self.format.cursor.iterate_focus()
        self.data.cache_db.clear()

    def cursor_add_line_n(self, delta):
        """ADDS 'delta' to the current cursor position depending on the 
           focus side being 'SUBJECT' or 'NOMINAL'.
        """
        new_lip_i = self.format.cursor.add_lip_i(delta)
        begin, end = self._display_lip_i_begin_end()
        if new_lip_i < begin: self._add_vertical_offset(-2)
        if new_lip_i >= end:  self._add_vertical_offset(2)
        self.data.cache_db.clear()

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
        self.data.selection_mode = mode
        self.data.verbosity      = verbosity_level
        self.data.select()

    def set_verbosity_level(self, verbosity_level):
        self.data.verbosity = verbosity_level
        self.data.select()

    def do(self):
        self._display_header()
        self.displayed_line_pair_n = self._display_content()
        self._display_fill_empty() 
        self._display_status_line()

        self._display_interaction_window()

    def _display_lip_i_begin_end(self):
        L     = len(self.data.line_pair_list)
        begin = self.__begin_line_pair_i
        end   = min(begin + self.height - 1, L)
        return begin, end

    def _display_content(self):
        if self.height < 1:
            return 0

        begin, end = self._display_lip_i_begin_end()
        if end <= begin:
            return 0

        for lip_i, line_pair in self.data.line_pair_list.enumerate(begin, end):
            formatted = self.data.cache_db.get(lip_i)
            if formatted is None:
                formatted = self._prepare_LinePair(lip_i, line_pair)
                self.data.cache_db[lip_i] = formatted
            self.print_line(formatted)

        return end

    def _display_fill_empty(self):
        if self.displayed_line_pair_n >= self.height:
            return
        empty_formatted = self._prepare_LinePair(lip_i=None, lip=None)
        for line_i in range(self.displayed_line_pair_n, self.height - 2):
            self.print_line(empty_formatted)

    def _display_header(self):
        self.print_line(self.format.header(self.data.output_app_name, self.data.output_choice_name))

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
        self.print_line(lp_list, newline_f=False)

    def _add_horizontal_offset(self, value):
        if self.__max_character_n - (self.format.text_offset + value) <= 0:
            return
        self.format.add_text_offset(value)
        self.data.cache_db.clear()
        self.__max_character_n = 0

    def _add_vertical_offset(self, value):
        L         = len(self.data.line_pair_list)
        new_value = self.__begin_line_pair_i + value
        last_i    = L - (self.height - 1) # 1 -> status line
        self.__begin_line_pair_i = max(0, min(new_value, last_i))

    def _first_displayed_not_good_line_pair(self):
        """RETURNS: index of first line pair on screen which is 'not good'.
                    None, if no such pair is currently displayed.
        """
        subject_line_n, nominal_line_n = None, None
        begin = self.__begin_line_pair_i
        end   = begin + self.displayed_line_pair_n
        try:
            return next(i for i in range(begin, end)
                        if not self.data.line_pair_list[i].is_good())
        except StopIteration:
            return None

    def _last_valid_line_pair_indices(self):
        lip_i_subject, lip_i_nominal = None, None
        for lip_i, lip in reversed(list(enumerate(self.data.line_pair_list))):
            if lip.subject is not None:         lip_i_subject = lip_i
            if lip.nominal is not None:         lip_i_nominal = lip_i
            if lip_i_subject and lip_i_nominal: break
        return lip_i_subject, lip_i_nominal
        
    def displayed_last_line_numbers(self):
        """RETURNS: [0] Line number of the last displayed subject's line.
                    [1] respectively for nominal.
                    None, None if no such one exists
        """
        subject_line_n, nominal_line_n = None, None
        for lip in self.data.iterable(self.__begin_line_pair_i, 
                                      self.__begin_line_pair_i + self.displayed_line_pair_n, 
                                      reverse=True):
            if lip.subject and subject_line_n is None: subject_line_n = lip.subject.line_n
            if lip.nominal and nominal_line_n is None: nominal_line_n = lip.nominal.line_n
            if subject_line_n is not None and nominal_line_n is not None:
                 break
        return subject_line_n, nominal_line_n
        
    def _prepare_LinePair(self, lip_i, lip):
        """Displays a formatted line of an association of a subject line with a 
        nominal line.
        """
        if lip_i is None:
            lip = prepare.LinePairDecorated(0, 0, LinePair.empty(None))

        self.__max_character_n = max(self.__max_character_n, lip.max_character_n())
        
        if   lip.filler_f:                                f = self.format.filler
        elif lip.border == E_PotpourriBorder.BEGIN:       f = self.format.potpourri_begin
        elif lip.border == E_PotpourriBorder.END:         f = self.format.potpourri_end
        elif lip.subject is None and lip.nominal is None:
            if   lip.subject_end_f and lip.nominal_end_f: f = self.format.both_end
            elif lip.subject_end_f:                       f = self.format.subject_end_nominal_empty
            elif lip.nominal_end_f:                       f = self.format.nominal_end_subject_empty
            else:                                         f = self.format.empty
        elif lip.subject is None:
            if lip.subject_end_f:                         f = self.format.subject_end
            else:                                         f = self.format.subject_empty
        elif lip.nominal is None:
            if lip.nominal_end_f:                         f = self.format.nominal_end
            else:                                         f = self.format.nominal_empty
        else:                                             f = self.format.normal

        return f(lip_i, lip)

    def _prepare_potpourri_border(self, lip):
        """Displays the border of a Potpourri region. 

        'begin_f' = True: display the OPENING of a potpourri region.
        else:             display the CLOSING of a potpourri region.
        """
        subject_line_n = "" if lip.subject is None else "%s" % lip.subject.line_n
        nominal_line_n = "" if lip.nominal is None else "%s" % lip.nominal.line_n
        return self.prepare(f, [subject_line_n, nominal_line_n])

