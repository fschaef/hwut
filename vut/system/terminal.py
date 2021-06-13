"""SPDX-License: MIT; Project UT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Provide information about the user's interaction console.________________________________________________________________________________

________________________________________________________________________________
"""
import vut.system.core as system

import fcntl, termios, struct, os
from   enum        import Enum, auto
from   collections import namedtuple
from   itertools   import zip_longest

class E_Alignment(Enum):
    RIGHT  = auto()
    LEFT   = auto()
    FIXED  = auto()
    CENTER = auto()

# Format Expression: 'FE'
CellFormat = namedtuple("CellFormat", ("alignment", "width", "string"))

def LEFT(width):
    return CellFormat(E_Alignment.LEFT, width, None)

def RIGHT(width):
    return CellFormat(E_Alignment.RIGHT, width, None)

def CENTER(width):
    return CellFormat(E_Alignment.CENTER, width, None)

class ConsoleCanvas:
   def __init__(self):
       self.height, self.width = size()
       self.__format_list = []
       self.__format_stack = []

   def set_format(self, *format_list):
       def _adapt(x):
           if type(x) == int: return CellFormat(E_Alignment.LEFT, 1, None)
           if type(x) == str: return CellFormat(E_Alignment.FIXED, len(x), x)
           else:              return x
       self.__format_list = list(_adapt(x) for x in format_list)

   def push_format(self, *format_list):
       self.__format_stack.append(self.__format_list)
       self.set_format(*list(format_list))

   def pop_format(self):
       self.__format_list = self.__format_stack.pop()

   def print_line(self, *cells):
       tmp = list(cells)
       print(self.format_line(*tmp))

   def format_line(self, *cells):
       def _iterable(cells, format_list):
           cell_i = 0
           for fe in self.__format_list:
               text, cell_i = _format_cell(fe, cells, cell_i)
               yield text

       return "".join(_iterable(cells, self.__format_list))
                

def size():
    """RETURNS: [0] height = number of rows in terminal
                [1] width  = number of columns in terminal

    This function attemps to access the terminal dimensions in terms of
    characters in multiple ways. Dependent on the operating system and
    the shell that it runs, different approaches are needed. If all fails,
    the default width and height of a terminal is returned.
    """
    result = _size_fixed()
    if result: return result

    result = _size_posix()
    if result: return result
       
    result = _size_windows()
    if result: return result

    result = _size_tput()
    if result: return result

    return (80, 25) # Default: width = 80; height = 25;

__fixed_height_width = None
def set_size_fixed(height, width):
    """Sets the terminal height and width to a fixed value. This prevents
    other methods of system-interactive interactions.

    Set 'height' = None, to disable the fixed size handling.
    """
    global __fixed_height_width
    if height is None:
        __fixed_height_width = None
    else:
        __fixed_height_width = (height, width)

def _size_fixed():
    """RETURNS: [0] height = number of rows in terminal
                [1] width  = number of columns in terminal
                None, in case of no success.
    """
    global __fixed_height_width
    return __fixed_height_width

def _size_windows():
    """RETURNS: [0] height = number of rows in terminal
                [1] width  = number of columns in terminal
                None, in case of no success.
    """
    csbi = system.windows_csbi()
    if not csbi:
        return None

    (_, _, _, _, _, left, top, right, bottom, _, _) = \
    struct.unpack("hhhhHhhhhhh", csbi.raw)

    width  = right - left + 1
    height = bottom - top + 1
    return height, width

def _size_tput():
    """RETURNS: [0] height = number of rows in terminal
                [1] width  = number of columns in terminal
                None, in case of no success.
    """
    try:
       width  = int(system.call("tput", "cols")[0])
       height = int(system.call("tput", "lines")[0])
       return height, width
    except:
       return None

def _size_posix():
    """RETURNS: [0] height = number of rows in terminal
                [1] width  = number of columns in terminal
                None, in case of no success.
    """
    def _get(fd_raw):
        return struct.unpack('hh', fcntl.ioctl(fd_raw, termios.TIOCGWINSZ,'1234'))

    height_width = _get(0)                 # try standard input
    if height_width: return height_width                    
    height_width = _get(1)                 # try standard output
    if height_width: return height_width                    
    height_width = _get(2)                 # try standard error output
    if height_width: return height_width
    try:
        with os.fdopen(os.open(os.ctermid(), os.O_RDONLY)) as fd: # try terminal i/o
            height_width = _get(fd)
    except:
        pass

    if height_width: return height_width

    try:
        return (env['LINES'], env['COLUMNS'])
    except:
        return None

def _format_cell(fe, cells, cell_i):
    if fe.alignment == E_Alignment.FIXED:
        return fe.string, cell_i

    cell = cells[cell_i]
    size = min(fe.width, len(cell))
    if fe.alignment == E_Alignment.CENTER:
        glue_left  = int(fe.width - size) >> 1
        glue_right = fe.width - size - glue_left
        text = "%s%s%s" % (" " * glue_left, cell[:size], " " * glue_right)
    elif fe.alignment == E_Alignment.RIGHT:
        glue = int(fe.width - size)
        text = "%s%s" % (" " * glue, cell[-size:])
    elif fe.alignment == E_Alignment.LEFT:
        glue = int(fe.width - size)
        text = "%s%s" % (cell[:size], " " * glue)
    else:
        assert False
    return text, cell_i + 1

