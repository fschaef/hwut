"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Interaction with the user's console.

________________________________________________________________________________
"""
import vut.system.core               as     system
import vut.system.terminal.cell      as     cell
from   vut.system.terminal.cell      import E_Alignment
import vut.system.terminal.size      as     terminal_size
from   vut.external.colorama         import init as colorama_init, Fore, Back, Style
from   vut.external.quex.typed       import typed

from   enum        import Enum, auto
from   collections import namedtuple
from   itertools   import zip_longest

_color_db = {
    "B": Fore.BLACK,  "R": Fore.RED,  "G": Fore.GREEN,
    "Y": Fore.YELLOW, "U": Fore.BLUE, "M": Fore.MAGENTA, 
    "C": Fore.CYAN,   "W": Fore.WHITE, 
    "b": Back.BLACK,  "r": Back.RED,  "g":  Back.GREEN,
    "y": Back.YELLOW, "u": Back.BLUE, "m":  Back.MAGENTA, 
    "c": Back.CYAN,   "w": Back.WHITE
}

_color_reset_all = Fore.RESET + Back.RESET

def _color_id_to_code(color):
    """RETURNS: Terminal color for given color (enum of Fore, or Back).
    """
    if color is None: return Fore.RESET + Back.RESET
    else:             return "".join(_color_db[code] for code in color)

# Format Expression: 'FE'
CellFormat = namedtuple("CellFormat", ("alignment", "color_code", "width", "string", "text_offset"))

@typed(width=int)
def LEFT(width, color=None, text_offset=0):
    return CellFormat(E_Alignment.LEFT, _color_id_to_code(color), width, None, text_offset)

@typed(width=int)
def RIGHT(width, color=None, text_offset=0):
    return CellFormat(E_Alignment.RIGHT, _color_id_to_code(color), width, None, text_offset)

@typed(string=str)
def FIXED(string, color=None, text_offset=0):
    return CellFormat(E_Alignment.LEFT, _color_id_to_code(color), len(string), string, text_offset)


class ConsoleCanvas:
   def __init__(self):
       self.height, self.width = terminal_size.get()
       self.height = int(self.height)
       self.width = int(self.width)
       colorama_init()

   def print_line(self, line, newline_f=True):
       if newline_f: print(line + _color_reset_all)
       else:         print(line + _color_reset_all, end="", flush=True)

   @typed(cell_content_list=list)
   def prepare(self, format_list, cell_content_list=[]) -> str:
       """RETURNS: Colored and formatted string. 
       
       Takes the 'format_list' and the according content to produce a colored 
       and formatted string.
       """
       def _iterable(format_list, cell_content_list):
           for fe in format_list:
               if fe.string is None: content = cell_content_list.pop(0)
               else:                 content = None
               yield cell.format(fe, content)

       return "".join(_iterable(format_list, cell_content_list))

