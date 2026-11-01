/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: TEXT AS PYTHON PRINTS IT -- so a C test and a Python test of the
 *          same module print the same bytes and share one GOOD file by a
 *          '.link' (bookkeeper B-32). The C twin of 'perl/Hwut/PyText.pm'.
 *
 *     pytext_float_repr(0.1)        "0.1"       the shortest text that reads
 *     pytext_float_repr(1e-05)      "1e-05"     back; exponential below 1e-4
 *     pytext_float_repr(1e16)       "1e+16"     and from 1e16 on
 *     pytext_str_repr("it's")       "\"it's\""  Python's choice of quotes
 *     pytext_bytes_repr("\x1b[A",4) "b'\\x1b[A'"
 *     pytext_bool(1)                "True"
 *
 * Every function writes into a buffer the caller owns and returns it; a text
 * longer than the buffer is cut, never overrun.
 * _____________________________________________________________________________
 */
#ifndef HWUT_PYTEXT_H
#define HWUT_PYTEXT_H

#include <stddef.h>

char*       pytext_float_repr(char* buffer, size_t size, double x);
char*       pytext_str_repr(char* buffer, size_t size, const char* text);
char*       pytext_bytes_repr(char* buffer, size_t size, const char* data, size_t length);
const char* pytext_bool(int value);

#endif
