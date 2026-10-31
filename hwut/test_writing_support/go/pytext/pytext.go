// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package pytext writes values AS PYTHON PRINTS THEM -- so a Go test and a
// Python test of the same module print the same bytes, and share one GOOD
// file by a '.link' (bookkeeper B-32).
//
//	pytext.FloatRepr(0.1)               "0.1"       repr(0.1): the shortest text that reads back
//	pytext.FloatRepr(1e-05)             "1e-05"     exponential below 1e-4 ...
//	pytext.FloatRepr(1e16)              "1e+16"     ... and from 1e16 on
//	pytext.StrRepr("it's")              "\"it's\""  repr(str): Python's quote, Python's escapes
//	pytext.BytesRepr([]byte("\x1b[A"))  "b'\\x1b[A'"
//	pytext.Bool(true)                   "True"
//	pytext.Repr(nil)                    "None"
//	pytext.Repr([]string{"a"})          "['a']"     a slice is a list
//	pytext.Repr(pytext.Tuple{"a"})      "('a',)"    a Tuple is a tuple; one keeps its comma
//	pytext.Str("a")                     "a"         str(): a string unquoted, any other value its repr
//
// Go has one 'int' family and one 'float64', Python 'int' and 'float': a Go
// integer prints as a Python int, a float64 as a Python float -- 'Repr(1.0)'
// is "1.0", 'Repr(1)' is "1".
// _____________________________________________________________________________
package pytext

import (
	"fmt"
	"math"
	"math/big"
	"reflect"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

// Tuple is a Python tuple: printed in parentheses, a tuple of one with its
// trailing comma.
type Tuple []any

// FloatRepr
//
// RETURN: string, 'x' as Python's 'repr(float)' writes it -- the shortest
// decimal that reads back to the same double, in fixed notation where the
// decimal point falls in (-4, 16], exponential ('1e-05', '1.5e+16') else;
// 'nan', 'inf', '-inf', '0.0', '-0.0' for those.
func FloatRepr(x float64) string {
	switch {
	case math.IsNaN(x):
		return "nan"
	case math.IsInf(x, 1):
		return "inf"
	case math.IsInf(x, -1):
		return "-inf"
	case x == 0:
		if math.Signbit(x) {
			return "-0.0"
		}
		return "0.0"
	}
	//  GO'S DIGITS ARE PYTHON'S -- both the shortest that reads back; only
	//  the layout differs ('%g' writes '1e+06' and '100000' where Python
	//  writes '1000000.0' and '100000.0'). The digits and the exponent are
	//  taken from Go, the layout is Python's.
	text := strconv.FormatFloat(x, 'e', -1, 64) // [-]d[.ddd]e[+-]dd
	sign := ""
	if text[0] == '-' {
		sign, text = "-", text[1:]
	}
	i_e := strings.IndexByte(text, 'e')
	digits := strings.Replace(text[:i_e], ".", "", 1)
	exponent, _ := strconv.Atoi(text[i_e+1:])
	digits = strings.TrimRight(digits, "0")
	if digits == "" {
		digits = "0"
	}
	point := exponent + 1 // value = 0.<digits> * 10^point
	n := len(digits)
	if point > -4 && point <= 16 {
		switch {
		case point <= 0:
			return sign + "0." + strings.Repeat("0", -point) + digits
		case point >= n:
			return sign + digits + strings.Repeat("0", point-n) + ".0"
		default:
			return sign + digits[:point] + "." + digits[point:]
		}
	}
	mantissa := digits
	if n > 1 {
		mantissa = digits[:1] + "." + digits[1:]
	}
	e := point - 1
	e_sign := "+"
	if e < 0 {
		e_sign, e = "-", -e
	}
	return fmt.Sprintf("%s%se%s%02d", sign, mantissa, e_sign, e)
}

// quoted
//
// RETURN: string, 'text' in the quotes Python's repr chooses -- single, or
// double where it holds a single quote and no double one -- with the
// backslash, that quote, '\n', '\t', '\r' escaped. Where 'bytes_f', every
// byte outside printable ASCII is '\xNN'; a str escapes what Python's
// 'str.isprintable' refuses: '\xNN' below 0x100, '\uNNNN', '\UNNNNNNNN'.
func quoted(text string, bytes_f bool) string {
	quote := byte('\'')
	if strings.IndexByte(text, '\'') >= 0 && strings.IndexByte(text, '"') < 0 {
		quote = '"'
	}
	var out strings.Builder
	if bytes_f {
		out.WriteByte('b')
	}
	out.WriteByte(quote)
	escape := func(r rune) bool {
		switch r {
		case '\\':
			out.WriteString(`\\`)
		case rune(quote):
			out.WriteByte('\\')
			out.WriteByte(quote)
		case '\n':
			out.WriteString(`\n`)
		case '\t':
			out.WriteString(`\t`)
		case '\r':
			out.WriteString(`\r`)
		default:
			return false
		}
		return true
	}
	if bytes_f {
		for i := 0; i < len(text); i++ {
			c := text[i]
			if escape(rune(c)) {
				continue
			}
			if c < 0x20 || c >= 0x7f {
				fmt.Fprintf(&out, `\x%02x`, c)
			} else {
				out.WriteByte(c)
			}
		}
	} else {
		for i := 0; i < len(text); {
			r, size := utf8.DecodeRuneInString(text[i:])
			if r == utf8.RuneError && size == 1 {
				fmt.Fprintf(&out, `\x%02x`, text[i]) // no str holds it; said as a byte
				i++
				continue
			}
			i += size
			switch {
			case escape(r):
			case r == ' ' || (r >= 0x20 && r < 0x7f) || (r >= 0x7f && unicode.IsPrint(r)):
				out.WriteRune(r)
			case r < 0x100:
				fmt.Fprintf(&out, `\x%02x`, r)
			case r < 0x10000:
				fmt.Fprintf(&out, `\u%04x`, r)
			default:
				fmt.Fprintf(&out, `\U%08x`, r)
			}
		}
	}
	out.WriteByte(quote)
	return out.String()
}

// StrRepr
//
// RETURN: string, 'text' (UTF-8) as Python's 'repr(str)' writes it.
func StrRepr(text string) string { return quoted(text, false) }

// BytesRepr
//
// RETURN: string, 'data' as Python's 'repr(bytes)' writes it -- "b'\x1b[A'".
func BytesRepr(data []byte) string { return quoted(string(data), true) }

// Bool
//
// RETURN: string, "True" where 'value', "False" else.
func Bool(value bool) string {
	if value {
		return "True"
	}
	return "False"
}

// Repr
//
// RETURN: string, 'value' as Python's 'repr' writes the Python value it
// stands for: nil 'None', a bool 'True'/'False', any integer (and a
// *big.Int) as an int, a float as 'FloatRepr', a string as 'StrRepr', a
// []byte as 'BytesRepr', a Tuple as a tuple, any other slice or array as a
// list -- element by element through Repr; a value of another kind as
// fmt's '%v'.
func Repr(value any) string {
	switch v := value.(type) {
	case nil:
		return "None"
	case bool:
		return Bool(v)
	case string:
		return StrRepr(v)
	case []byte:
		return BytesRepr(v)
	case float64:
		return FloatRepr(v)
	case float32:
		return FloatRepr(float64(v))
	case *big.Int:
		return v.String()
	case Tuple:
		if len(v) == 1 {
			return "(" + Repr(v[0]) + ",)"
		}
		return "(" + joined([]any(v)) + ")"
	case fmt.Stringer:
		return v.String()
	}
	reflected := reflect.ValueOf(value)
	switch reflected.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Uintptr:
		return fmt.Sprintf("%d", value)
	case reflect.Float32, reflect.Float64:
		return FloatRepr(reflected.Float())
	case reflect.Bool:
		return Bool(reflected.Bool())
	case reflect.String:
		return StrRepr(reflected.String())
	case reflect.Pointer, reflect.Interface:
		if reflected.IsNil() {
			return "None"
		}
		return Repr(reflected.Elem().Interface())
	case reflect.Slice, reflect.Array:
		if reflected.Kind() == reflect.Slice && reflected.IsNil() {
			return "[]"
		}
		item_list := make([]any, reflected.Len())
		for i := range item_list {
			item_list[i] = reflected.Index(i).Interface()
		}
		return "[" + joined(item_list) + "]"
	}
	return fmt.Sprintf("%v", value)
}

// joined
//
// RETURN: string, the Repr of every item of 'item_list', separated by ', '.
func joined(item_list []any) string {
	text_list := make([]string, len(item_list))
	for i, item := range item_list {
		text_list[i] = Repr(item)
	}
	return strings.Join(text_list, ", ")
}

// Str
//
// RETURN: string, 'value' as Python's 'str' writes it: a string as it
// stands, any other value as 'Repr' writes it.
func Str(value any) string {
	if text, ok := value.(string); ok {
		return text
	}
	return Repr(value)
}

// ------------------------------------------------- Python's str, where it differs

// IsSpace
//
// RETURN: bool, true where 'r' is white space as Python's 'str.isspace' and
// the regular expression '\s' see it -- Go's 'unicode.IsSpace' and the
// separators 0x1c..0x1f.
func IsSpace(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) }

// Strip
//
// RETURN: string, 'text' without the white space ('IsSpace') at both ends --
// Python's 'str.strip()'.
func Strip(text string) string { return strings.TrimFunc(text, IsSpace) }

// SplitLines
//
// RETURN: []string, 'text' cut at every line boundary Python's
// 'str.splitlines()' knows -- '\n', '\r', '\r\n', '\v', '\f', 0x1c..0x1e,
// U+0085, U+2028, U+2029 -- the boundaries dropped; no empty last line
// where the text ends in a boundary; none for an empty text.
func SplitLines(text string) []string {
	var result []string
	begin := 0
	for i := 0; i < len(text); {
		r, size := utf8.DecodeRuneInString(text[i:])
		switch r {
		case '\n', '\r', '\v', '\f', 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029:
			result = append(result, text[begin:i])
			if r == '\r' && i+1 < len(text) && text[i+1] == '\n' {
				size = 2
			}
			begin = i + size
		}
		i += size
	}
	if begin < len(text) {
		result = append(result, text[begin:])
	}
	return result
}

// TypeName
//
// RETURN: string, the name of the Python type 'value' stands for, as
// 'type(value).__name__' gives it: 'NoneType', 'bool', 'int' (every Go
// integer and *big.Int), 'float', 'str', 'bytes', 'tuple', 'list'; Go's
// own type name for any other value.
func TypeName(value any) string {
	switch value.(type) {
	case nil:
		return "NoneType"
	case bool:
		return "bool"
	case string:
		return "str"
	case []byte:
		return "bytes"
	case *big.Int:
		return "int"
	case Tuple:
		return "tuple"
	}
	switch reflect.ValueOf(value).Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return "int"
	case reflect.Float32, reflect.Float64:
		return "float"
	case reflect.Slice, reflect.Array:
		return "list"
	}
	return reflect.TypeOf(value).Name()
}
