"""SPDX-License: MIT; Project UT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Provide information about the user's interaction console.________________________________________________________________________________

________________________________________________________________________________
"""
import ut.system.core as system

import fcntl, termios, struct, os
from   enum import Enum

class E_Alignment(Enum):
    RIGHT  = 0
    LEFT   = 1

# Format Expression: 'FE'
FE = namedtuple("FE", ("alignment", "width"))

class ConsoleCanvas:
   def __init__(self):
       self.width, self.height = size()
       self.__format_list = []

   @typed(format_list=[FE])
   def set_format(self, format_list):
       self.__format_list = format_list

   def prepare(self, cells):
       def _iterable(cells, format_list):
           for cell, fe in izip(cells, format_list):
               size = max(fe.width, cell.length())
               if   fe.alignment == E_Alignment.LEFT:
                   yield cell[:size]
               elif fe.alignment == E_Alignment.RIGHT:
                   yield cell[-size:]
               else:
                   pass
       return "".join(_iterable(cells, self.__format_list)
                

def size():
    """RETURNS: [0] width of terminal
                [1] height of terminal

    This function attemps to access the terminal dimensions in terms of
    characters in multiple ways. Dependent on the operating system and
    the shell that it runs, different approaches are needed. If all fails,
    the default width and height of a terminal is returned.
    """
    result = _size_posix()
    if result: return result
       
    result = _size_windows():
    if result: return result

    result = _size_tput()
    if result: return result

    return (80, 25) # Default: width = 80; height = 25;

def _size_windows():
    """RETURNS: [0] width of terminal
                [1] height of terminal
                None, in case of no success.
    """
    csbi = system.windows_csbi()
    if not csbi:
        return None

    (_, _, _, _, _, left, top, right, bottom, _, _) = \
    struct.unpack("hhhhHhhhhhh", csbi.raw)

    width  = right - left + 1
    height = bottom - top + 1
    return width, height

def _size_tput():
    """RETURNS: [0] width of terminal
                [1] height of terminal
                None, in case of no success.
    """
    try:
       width  = int(system.call("tput", "cols")[0])
       height = int(system.call("tput", "lines")[0])
       return width, height
    except:
       return None

def _size_posix():
    """RETURNS: [0] width of terminal
                [1] height of terminal
                None, in case of no success.
    """

    # (1) Try to get it quickly from TTY
    width_height = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if width_height:
        return int(width_height[1]), int(width_height[0])

    # (2) Try to get it through terminal device
    try:
        with os.fdopen(os.open(os.ctermid(), os.O_RDONLY)) as fd:
            return struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,'1234'))
    except:
        return None

    # (3) Try to get it through environment variables
    try:
        return (env['LINES'], env['COLUMNS'])
    except:
        return None

