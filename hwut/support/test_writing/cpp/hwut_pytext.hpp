// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: TEXT AS PYTHON PRINTS IT -- so a C++ test and a Python test of the
//          same module print the same bytes and share one GOOD file by a
//          '.link' (bookkeeper B-32). A thin face over '../c/hwut_pytext.c'.
//
//     using hwut::pytext::repr;
//     repr(0.1)                          "0.1"     shortest text that reads back
//     repr(1e-05)                        "1e-05"
//     repr(std::string("it's"))          "\"it's\""
//     hwut::pytext::bytes_repr("\x1b[A") "b'\\x1b[A'"
//     repr(true)                         "True"
//     repr(std::nullopt)                 "None"
//     repr(std::vector<int>{1, 2})       "[1, 2]"
//     tuple_repr(std::vector<std::string>{"a"})    "('a',)"
// _____________________________________________________________________________
#ifndef HWUT_PYTEXT_HPP
#define HWUT_PYTEXT_HPP

#include <optional>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

namespace hwut {
namespace pytext {

std::string repr(double x);
std::string repr(bool value);
std::string repr(const std::string& text);
std::string repr(const char* text);
std::string repr(std::nullopt_t);
std::string bytes_repr(const std::string& data);

template <class T>
typename std::enable_if<std::is_integral<T>::value && ! std::is_same<T, bool>::value, std::string>::type
repr(T x)
/* RETURN: the integer 'x' as Python's 'repr(int)' writes it -- its decimal. */
{ return std::to_string(x); }

template <class T> std::string repr(const std::optional<T>& x);
template <class T> std::string repr(const std::vector<T>& list);
template <class... T> std::string repr(const std::tuple<T...>& tuple);

template <class T>
std::string
repr(const std::optional<T>& x)
/* RETURN: 'None' where 'x' is empty; 'repr' of its value else.             */
{ return x ? repr(*x) : std::string("None"); }

template <class T>
std::string
repr(const std::vector<T>& list)
/* RETURN: 'list' as Python prints a list: '[a, b]', each element by 'repr'. */
{
    std::string result = "[";
    for(size_t i = 0; i < list.size(); ++i) result += (i ? ", " : "") + repr(list[i]);
    return result + "]";
}

template <class T>
std::string
tuple_repr(const std::vector<T>& list)
/* RETURN: 'list' as Python prints a tuple of it: '(a, b)', '(a,)', '()'.   */
{
    std::string result = "(";
    for(size_t i = 0; i < list.size(); ++i) result += (i ? ", " : "") + repr(list[i]);
    return result + (list.size() == 1 ? ",)" : ")");
}

template <class... T>
std::string
repr(const std::tuple<T...>& tuple)
/* RETURN: 'tuple' as Python prints a tuple: '(1, 'a')', '(1,)', '()'.      */
{
    std::string result = "(";
    size_t      i      = 0;
    std::apply([&](const auto&... x) { ((result += (i++ ? ", " : "") + repr(x)), ...); }, tuple);
    return result + (sizeof...(T) == 1 ? ",)" : ")");
}

} // namespace pytext
} // namespace hwut

#endif
