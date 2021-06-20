"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Interaction with the user's console.

________________________________________________________________________________
"""
import vut.system.core          as     system
import vut.system.terminal_size as     terminal_size
from   vut.external.colorama    import init as colorama_init, Fore, Back, Style

from   enum        import Enum, auto
from   collections import namedtuple
from   itertools   import zip_longest


class E_Alignment(Enum):
    LEFT   = auto()
    CENTER = auto()
    RIGHT  = auto()
    FIXED  = auto()

# Format Expression: 'FE'
CellFormat = namedtuple("CellFormat", ("alignment", "color_code", "width", "string"))

def LEFT(width, color=None):
    return CellFormat(E_Alignment.LEFT, _color_to_code(color), width, None)

def RIGHT(width, color=None):
    return CellFormat(E_Alignment.RIGHT, _color_to_code(color), width, None)

def CENTER(width, color=None):
    return CellFormat(E_Alignment.CENTER, _color_to_code(color), width, None)

def FIXED(string, color=None):
    return CellFormat(E_Alignment.FIXED, _color_to_code(color), len(string), string)

class ConsoleCanvas:
   def __init__(self):
       self.height, self.width = terminal_size.get()
       self.__format_list = []
       self.__format_stack = []
       colorama_init()

   def set_format(self, *format_list):
       self.__format_list = list( format_list)

   def push_format(self, *format_list):
       self.__format_stack.append(self.__format_list)
       self.set_format(*list(format_list))

   def pop_format(self):
       self.__format_list = self.__format_stack.pop()

   def print_line(self, *cell_list):
       tmp = list(cell_list)
       print(self.format_line(*tmp) + _color_reset_all)

   def format_line(self, *cell_list):
       def _iterable(cell_list, format_list):
           cell_i = 0
           for fe in self.__format_list:
               text = _format_cell(fe, cell_list, cell_i)
               yield text
               # 'FIXED' => content is taken out of 'fe' not from cell_list.
               if fe.alignment != E_Alignment.FIXED: cell_i += 1

       return "".join(_iterable(cell_list, self.__format_list))
                

def _format_fixed(fe):
    if fe.alignment == E_Alignment.FIXED:
        return fe.color_code + fe.string
    else:
        return None

def _format_text(fe, content, remaining):
    if fe.alignment == E_Alignment.CENTER:
        pad_left  = int(remaining) >> 1
        pad_right = remaining - pad_left
        text = "%s%s%s" % (" " * pad_left, content, " " * pad_right)
    elif fe.alignment == E_Alignment.RIGHT:
        text = "%s%s" % (" " * remaining, content)
    elif fe.alignment == E_Alignment.LEFT:
        text = "%s%s" % (content, " " * remaining)
    else:
        assert False
    return fe.color_code + text

def _format_plain(fe, cell):
    if fe.alignment == E_Alignment.RIGHT:
        return _format_text(fe, cell[max(0, fe.width - len(cell)):], max(0, fe.width - len(cell)))
    else:
        return _format_text(fe, cell[:min(fe.width, len(cell))], max(0, fe.width - len(cell)))

def _format_color_text_tuple_list(fe, color_text_list):
    def _color(fe, color):
        return fe.color_code if not color else color

    def _do(text, fe, color_text_list):
        # remaining >= 0: cell content too small.
        # => padding is added later.
        for color, sub_text in color_text_list:
            text.append(_color(fe, color) + sub_text)

    text_length = sum(len(sub_text) for _, sub_text in color_text_list)
    text        = []

    if fe.width >= text_length:
        _do(text, fe, color_text_list)
        text.append(fe.color_code)

    elif fe.alignment == E_Alignment.RIGHT: # prune *beginning* of text
        overhead = text_length - fe.width
        for i, entry in enumerate(color_text_list):
            color, sub_text = entry
            if len(sub_text) >= overhead:
                first = _color(fe, color) + sub_text[overhead:]
                break
            overhead = - len(sub_text)
        text.append(first)
        _do(text, fe, color_text_list[i+1:])

    else:                                   # prune *end* of text
        remaining = fe.width
        for i, entry in enumerate(color_text_list):
            color, sub_text = entry
            if len(sub_text) >= remaining:
                last = _color(fe, color) + sub_text[:remaining]
                break
            remaining -= len(sub_text)
        _do(text, fe, color_text_list[:i])
        text.append(last)

    return _format_text(fe, "".join(text), max(0, fe.width - text_length))

def _format_cell(fe, cell_list, cell_i):
   text = _format_fixed(fe)
   if text is not None:  return text

   cell = cell_list[cell_i]
   if type(cell) == str: 
        return _format_plain(fe, cell)
   else:                 
        return _format_color_text_tuple_list(fe, cell)

_color_db = {
    "B": Fore.BLACK,  "R": Fore.RED,  "G": Fore.GREEN,
    "Y": Fore.YELLOW, "U": Fore.BLUE, "M": Fore.MAGENTA, 
    "C": Fore.CYAN,   "W": Fore.WHITE, 
    "b": Back.BLACK,  "r": Back.RED,  "g": Back.GREEN,
    "y": Back.YELLOW, "u": Back.BLUE, "m": Back.MAGENTA, 
    "c": Back.CYAN,   "w": Back.WHITE, 
}

def _color_to_code(color):
    if color is None: return Fore.RESET + Back.RESET
    else:             return "".join(_color_db[code] for code in color)

_color_reset_all = Fore.RESET + Back.RESET
