// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: Text as Python prints it -- see 'hwut_pytext.hpp'.
// _____________________________________________________________________________
#include "hwut_pytext.hpp"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/hwut_pytext.h"
}
} }

using namespace hwut::c;

namespace hwut {
namespace pytext {

std::string
repr(double x)
/* RETURN: 'x' as Python's 'repr(float)' writes it -- the shortest decimal
 *         that reads back to the same double; exponential below 1e-4 and
 *         from 1e16 on; 'nan', 'inf', '-inf', '-0.0' as Python.           */
{ char buffer[64]; return pytext_float_repr(buffer, sizeof(buffer), x); }

std::string
repr(bool value)
/* RETURN: "True" or "False".                                               */
{ return pytext_bool(value); }

std::string
repr(const std::string& text)
/* RETURN: the UTF-8 'text' as Python's 'repr(str)' writes it: in the quotes
 *         Python chooses, backslash, that quote and what does not print
 *         escaped. The text ends at its first NUL.                        */
{
    std::string buffer(4 * text.size() + 8, '\0');
    return pytext_str_repr(&buffer[0], buffer.size(), text.c_str());
}

std::string
repr(const char* text)
/* RETURN: as 'repr(std::string(text))' -- a literal is a str, not a bool.  */
{ return repr(std::string(text)); }

std::string
repr(std::nullopt_t)
/* RETURN: "None".                                                          */
{ return "None"; }

std::string
bytes_repr(const std::string& data)
/* RETURN: every byte of 'data' (NULs included) as Python's 'repr(bytes)'
 *         writes them: 'b'...'', each byte from 0x7f on as '\xNN'.        */
{
    std::string buffer(4 * data.size() + 8, '\0');
    return pytext_bytes_repr(&buffer[0], buffer.size(), data.data(), data.size());
}

} // namespace pytext
} // namespace hwut
