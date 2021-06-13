
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Providing information on system where the app is running.
________________________________________________________________________________
"""

def is_windows():
    try:
        import ctypes.windll
        return True
    except ImportError:
        return False

def is_posix():
    try:
        import posix
        return True
    except ImportError:
        return False

def call(command_line):
    process = subprocess.Popen(["tput", "cols"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    stdout  = proc.communicate(input=None)
    return stdout

res=None
try:
    from ctypes import windll
    STD_ERR_HANDLE    = -12
    stderr_handle  = windll.kernel32.GetStdHandle(STD_ERR_HANDLE) 
    __windows_csbi = ctypes.create_string_buffer(22)
    if not windll.kernel32.GetConsoleScreenBufferInfo(stderr_handle, __windows_csbi):
        __windows_csbi = None
except:
    __windows_csbi = None

def windows_csbi():
    return __windows_csbi
