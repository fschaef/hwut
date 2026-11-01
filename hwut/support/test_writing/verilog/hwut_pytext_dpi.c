/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE DPI-C FACE OF '../c/hwut_pytext.c' for 'hwut_pytext.sv'. What
 *          SystemVerilog cannot print as Python does -- a double's shortest
 *          text, a str or bytes literal's choice of quotes and escapes -- the
 *          C port prints; this file only hands its text over.
 *
 * Every function returns a text in a buffer of its own, valid until its next
 * call: the simulator copies a returned 'string' at once.
 * _____________________________________________________________________________
 */
#include <string.h>
#include "hwut_pytext.h"

#define HWUT_SV_PYTEXT_MAX 65536

const char*
hwut_sv_pytext_float_repr(double x)
/* RETURN: Python's 'repr(x)' -- the shortest text that reads back as 'x'. */
{
    static char buffer[64];
    return pytext_float_repr(buffer, sizeof(buffer), x);
}

const char*
hwut_sv_pytext_str_repr(const char* text)
/* RETURN: Python's 'repr(text)' of the str whose UTF-8 bytes 'text' holds;
 *         cut at 64 KiB.                                                   */
{
    static char buffer[HWUT_SV_PYTEXT_MAX];
    return pytext_str_repr(buffer, sizeof(buffer), text ? text : "");
}

const char*
hwut_sv_pytext_bytes_repr(const char* data)
/* RETURN: Python's 'repr(data)' of the bytes 'data' holds -- "b'...'";
 *         cut at 64 KiB. (A SystemVerilog string holds no zero byte.)      */
{
    static char buffer[HWUT_SV_PYTEXT_MAX];
    if( ! data ) data = "";
    return pytext_bytes_repr(buffer, sizeof(buffer), data, strlen(data));
}
