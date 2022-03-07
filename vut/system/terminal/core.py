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
    "b": Back.BLACK,  "r": Back.RED,  "g": Back.GREEN,
    "y": Back.YELLOW, "u": Back.BLUE, "m": Back.MAGENTA, 
    "c": Back.CYAN,   "w": Back.WHITE, 
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

@typed(width=int)
def CENTER(width, color=None, text_offset=0):
    return CellFormat(E_Alignment.CENTER, _color_id_to_code(color), width, None, text_offset)

@typed(string=str)
def FIXED(string, color=None, text_offset=0):
    return CellFormat(E_Alignment.FIXED, _color_id_to_code(color), len(string), string, text_offset)

@typed(string=str)
def GLUE(string, color=None, text_offset=0):
    return CellFormat(E_Alignment.GLUE, _color_id_to_code(color), 0, string, text_offset)

class ConsoleCanvas:
   def __init__(self):
       self.height, self.width = terminal_size.get()
       self.height = int(self.height)
       self.width = int(self.width)
       colorama_init()

   def display(self, line):
       print(line + _color_reset_all)

   @typed(cell_content_list=list)
   def prepare(self, format_list, cell_content_list=[]) -> str:
       """RETURNS: Colored and formatted string. 
       
       Takes the 'format_list' and the according content to produce a colored 
       and formatted string.
       """
       def _iterable(cell_content_list, format_list):
           L         = len(cell_content_list)
           content_i = 0
           for fe in format_list:
               if content_i >= L: content = "???"
               else:              content = cell_content_list[content_i]

               yield cell.format(fe, content)

               # 'FIXED' => content is taken out of 'fe' not from cell_list.
               #            else, need to increase the content index.
               if fe.alignment != E_Alignment.FIXED: content_i += 1

       return "".join(_iterable(cell_content_list, format_list))

   def fix_glue(self, *format_list):
       """RETURNS: list of CellFormat-s

       which has the glue inside tranformed into 'FIXED' so that the line fits 
       the horizontal width of the terminal.
       """
       def _expand(fe, width):
           if fe.alignment != E_Alignment.GLUE: return fe

           if fe.string: s = fe.string
           else:         s = " "

           ls         = len(s)
           repetition = int(width / ls)
           remainder  = width - repetition * ls
           glue_str   = s * repetition + s[:remainder]
           return CellFormat(E_Alignment.FIXED, fe.color_code, width, glue_str, fe.text_offset)

       # Determine the width of each 'glue' cell.
       glue_width_db = self.__compute_glue_width_db(list(format_list))

       return [ _expand(fe, glue_width_db.get(i)) for i, fe in enumerate(format_list) ]

   def __compute_glue_width_db(self, format_list):
       """RETURN: map: cell-index --> width of glue cell

       The dictionary contains only entries for glue cells.
       """
       glue_n = sum(cell.alignment == E_Alignment.GLUE for cell in format_list)
       if glue_n == 0:
           return None

       occupied         = sum(cell.width for cell in format_list)
       glue_index_db    = list(index for index, cell in enumerate(format_list) 
                               if cell.alignment == E_Alignment.GLUE)
       remaining_glue   = max(0, self.width - occupied)
       glue_cell_width  = remaining_glue / glue_n

       # 'glue_cell_with' is an integer
       # => 'glue_cell_with * glue_n' is not necessarily == remaining_glue
       # => distribute the remainder over the cells.
       width_array      = [int(glue_cell_width)] * glue_n
       remaining_glue  -= int(glue_cell_width) * glue_n
       i = 0
       while remaining_glue > 0:
           width_array[i%glue_n] += 1
           remaining_glue -= 1
           i += 1
       return dict((glue_index_db[i], width) for i, width in enumerate(width_array))

