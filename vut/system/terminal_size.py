"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Provide size information OS-independent.

________________________________________________________________________________
"""
import fcntl, termios, struct, os

def get():
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


