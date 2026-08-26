"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE:
"""
import sys
import tty
import os
import termios

class Key:
   BACKSPACE   = 127 
   RETURN      = 10 
   SPACE       = 32 
   TABULATOR   = 9 
   ESCAPE      = 27 
   ARROW_UP    = 65 
   ARROW_DOWN  = 66 
   ARROW_RIGHT = 67 
   ARROW_LEFT  = 68 

def get():
    backup = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    b = os.read(sys.stdin.fileno(), 3).decode()
    if len(b) == 3:
        result = b[2]
    else:
        result = b 

    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, backup)
    return result

