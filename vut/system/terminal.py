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
CellFormat = namedtuple("CellFormat", ("alignment", "color_code", "width", "string", "text_offset"))

def LEFT(width, color=None, text_offset=0):
    return CellFormat(E_Alignment.LEFT, _color_to_code(color), width, None, text_offset)

def RIGHT(width, color=None, text_offset=0):
    return CellFormat(E_Alignment.RIGHT, _color_to_code(color), width, None, text_offset)

def CENTER(width, color=None, text_offset=0):
    return CellFormat(E_Alignment.CENTER, _color_to_code(color), width, None, text_offset)

def FIXED(string, color=None, text_offset=0):
    return CellFormat(E_Alignment.FIXED, _color_to_code(color), len(string), string, text_offset)

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
    L = len(cell)
    W = fe.width
    T = fe.text_offset

    if fe.alignment == E_Alignment.RIGHT: text = cell[max(0, W - L):L-T]
    else:                                 text = cell[T:min(W, L)]

    length = max(0, W - L - T)
    return _format_text(fe, text, length)

def _format_color_text_tuple_list(fe, color_text_list):
    def _color(fe, color):
        return fe.color_code if not color else color

    if fe.text_offset > 0:
        color_text_list = list(_color_text_list_prune_begin(color_text_list, fe.text_offset))
    elif fe.text_offset == 0:
        pass
    elif len(color_text_list):
        # Add some padding at the beginning
        first = color_text_list[0]
        color_text_list = [(first[0], " " * (-fe.text_offset))] + color_text_list

    total_length = sum(len(sub_text) for _, sub_text in color_text_list)
    cut_n        = total_length - fe.width

    if   cut_n <= 0:          
        pass
    elif fe.alignment == E_Alignment.RIGHT: 
        color_text_list = _color_text_list_prune_begin(color_text_list, cut_n)
    else:                                   
        color_text_list = _color_text_list_prune_end(color_text_list, cut_n)

    text = [
        _color(fe, color) + sub_text
        for color, sub_text in color_text_list
    ]
    text.append(fe.color_code)

    return _format_text(fe, "".join(text), max(0, fe.width - total_length))

def _color_text_list_prune_begin(color_text_list, cut_n):
    if cut_n <= 0: 
        yield from color_text_list
    else:
        flush_f = False
        for color, sub_text in color_text_list:
            if flush_f:
                yield color, sub_text
            elif len(sub_text) >= cut_n:
                yield color, sub_text[cut_n:]
                flush_f = True
            else:
                cut_n -= len(sub_text)

def _color_text_list_prune_end(color_text_list, cut_n):
    remaining = sum(len(t) for c, t in color_text_list) - cut_n
    if remaining <= 0: 
        yield from color_text_list
    else:
        for color, sub_text in color_text_list:
            if len(sub_text) >= remaining:
                yield color, sub_text[:remaining]
                break
            remaining -= len(sub_text)
            yield color, sub_text

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
