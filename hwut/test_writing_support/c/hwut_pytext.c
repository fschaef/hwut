/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: Text as Python prints it -- see 'hwut_pytext.h'.
 * _____________________________________________________________________________
 */
#include "hwut_pytext.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char*
pytext_float_repr(char* buffer, size_t size, double x)
/* RETURN: buffer, 'x' as Python's 'repr(float)' writes it -- the shortest
 *         decimal that reads back to the same double, fixed notation where
 *         the decimal point falls in (-4, 16], exponential else.          */
{
    char   text[40], digits[40];
    int    precision, exponent, point, n, i;
    char*  p;
    const char* sign;

    if( isnan(x) )         { snprintf(buffer, size, "nan");  return buffer; }
    if( isinf(x) )         { snprintf(buffer, size, x < 0 ? "-inf" : "inf"); return buffer; }
    if( x == 0.0 )         { snprintf(buffer, size, signbit(x) ? "-0.0" : "0.0"); return buffer; }

    for(precision = 0; precision <= 16; ++precision) {
        snprintf(text, sizeof(text), "%.*e", precision, x);
        if( strtod(text, NULL) == x ) break;
    }
    /* text: [-]d[.ddd]e[+-]xx */
    sign = text[0] == '-' ? "-" : "";
    p    = text + (text[0] == '-');
    n    = 0;
    for(; *p && *p != 'e'; ++p) if( *p != '.' ) digits[n++] = *p;
    digits[n] = '\0';
    exponent = atoi(p + 1);
    while( n > 1 && digits[n - 1] == '0' ) digits[--n] = '\0';
    point = exponent + 1;                     /* value = 0.<digits> * 10^point */

    if( point > -4 && point <= 16 ) {
        char out[64]; int k = 0;
        if( point <= 0 ) {
            k += sprintf(out + k, "0.");
            for(i = 0; i < -point; ++i) out[k++] = '0';
            k += sprintf(out + k, "%s", digits);
        } else if( point >= n ) {
            k += sprintf(out + k, "%s", digits);
            for(i = 0; i < point - n; ++i) out[k++] = '0';
            k += sprintf(out + k, ".0");
        } else {
            memcpy(out, digits, (size_t)point); k = point;
            out[k++] = '.';
            k += sprintf(out + k, "%s", digits + point);
        }
        out[k] = '\0';
        snprintf(buffer, size, "%s%s", sign, out);
    } else {
        int e = point - 1;
        if( n > 1 ) snprintf(buffer, size, "%s%c.%se%c%02d", sign, digits[0], digits + 1,
                             e < 0 ? '-' : '+', abs(e));
        else        snprintf(buffer, size, "%s%ce%c%02d", sign, digits[0],
                             e < 0 ? '-' : '+', abs(e));
    }
    return buffer;
}

static char*
_quoted(char* buffer, size_t size, const char* s, size_t length, int bytes_f)
/* RETURN: buffer, 's' in the quotes Python's repr chooses -- single, or double
 *         where it holds a single quote and no double one -- the backslash,
 *         that quote and what does not print escaped. Where 'bytes_f', every
 *         byte from 0x7f on is escaped too; a str keeps UTF-8 as it stands. */
{
    size_t i, k = 0;
    int    single_f = memchr(s, '\'', length) != NULL;
    int    double_f = memchr(s, '"',  length) != NULL;
    char   quote    = (single_f && ! double_f) ? '"' : '\'';
    char   piece[8];

    if( size == 0 ) return buffer;
#   define PUT(text) do { const char* q_ = (text);                        \
                          while( *q_ && k + 1 < size ) buffer[k++] = *q_++; } while(0)
    if( bytes_f ) PUT("b");
    piece[0] = quote; piece[1] = '\0'; PUT(piece);
    for(i = 0; i < length; ++i) {
        unsigned char c = (unsigned char)s[i];
        if     ( c == '\\' )  PUT("\\\\");
        else if( c == (unsigned char)quote ) { piece[0] = '\\'; piece[1] = quote; piece[2] = '\0'; PUT(piece); }
        else if( c == '\n' )  PUT("\\n");
        else if( c == '\t' )  PUT("\\t");
        else if( c == '\r' )  PUT("\\r");
        else if( c < 0x20 || c == 0x7f || (bytes_f && c >= 0x80) ) {
            snprintf(piece, sizeof(piece), "\\x%02x", c); PUT(piece);
        }
        else { piece[0] = (char)c; piece[1] = '\0'; PUT(piece); }
    }
    piece[0] = quote; piece[1] = '\0'; PUT(piece);
#   undef PUT
    buffer[k] = '\0';
    return buffer;
}

char*
pytext_str_repr(char* buffer, size_t size, const char* text)
/* RETURN: buffer, the UTF-8 'text' as Python's 'repr(str)' writes it.     */
{ return _quoted(buffer, size, text, strlen(text), 0); }

char*
pytext_bytes_repr(char* buffer, size_t size, const char* data, size_t length)
/* RETURN: buffer, 'length' bytes of 'data' as Python's 'repr(bytes)'.     */
{ return _quoted(buffer, size, data, length, 1); }

const char*
pytext_bool(int value)
/* RETURN: "True" where 'value' is not 0, "False" else.                    */
{ return value ? "True" : "False"; }
