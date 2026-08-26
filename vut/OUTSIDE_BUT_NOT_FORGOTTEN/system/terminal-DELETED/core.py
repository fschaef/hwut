"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Interaction with the user's console.

________________________________________________________________________________
"""
from   vut.external.colorama           import Fore, Back
from   vut.system.terminal.cell        import StaticCell
from   vut.system.terminal.styled_text import CellFormat, E_Alignment

from   typeguard   import typechecked

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

def LEFT(width, color=None, text_offset=0) -> CellFormat:
    return CellFormat(
        width       = width,
        alignment   = E_Alignment.LEFT,
        color_code  = _color_id_to_code(color),
        text_offset = text_offset,
    )

def RIGHT(width, color=None, text_offset=0) -> CellFormat:
    return CellFormat(
        width       = width,
        alignment   = E_Alignment.RIGHT,
        color_code  = _color_id_to_code(color),
        text_offset = text_offset,
    )

def FIXED(string, color=None, text_offset=0):
    fmt = CellFormat(
        width       = len(string),
        alignment   = E_Alignment.LEFT,
        color_code  = _color_id_to_code(color),
        text_offset = text_offset,
    )
    return StaticCell(fmt, string)
