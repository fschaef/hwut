/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: TEXT AS PYTHON PRINTS IT -- so a Java test and a Python test of the
 *          same module print the same bytes, and share one GOOD file by a
 *          '.link' (bookkeeper B-32). The port of 'c/hwut_pytext.c' and
 *          'perl/Hwut/PyText.pm'.
 *
 *     PyText.floatRepr(0.1)          "0.1"         repr(0.1)
 *     PyText.floatRepr(1e-05)        "1e-05"       exponential below 1e-4 ...
 *     PyText.floatRepr(1e16)         "1e+16"       ... and from 1e16 on
 *     PyText.strRepr("it's")         "\"it's\""    repr(str)
 *     PyText.bytesRepr(b)            "b'\\x1b[A'"  repr(bytes)
 *     PyText.repr(List.of(3, 1))     "[3, 1]"      a List is a list
 *     PyText.repr(new Object[]{"a"}) "('a',)"      an Object[] is a tuple
 *     PyText.repr(null)              "None"        Boolean: True / False
 *
 * Java's 'Double.toString' gives the SHORTEST digits that read back (JDK 19
 * on, as Python's 'repr' does) but not Python's layout: '1.0E-5' against
 * '1e-05'. 'floatRepr' takes the digits and lays them out as Python does.
 * _____________________________________________________________________________
 */
package hwut;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.Collection;
import java.util.Map;

public final class PyText {
    private PyText() {}

    /** RETURN: String, 'x' as Python's 'repr(float)' writes it -- the shortest
     *          decimal that reads back to the same double, fixed notation
     *          where the decimal point falls in (-4, 16], exponential else
     *          ('1e-05', '1e+16', 'nan', 'inf', '-0.0'). Never fails. */
    public static String floatRepr(double x) {
        if (Double.isNaN(x))      return "nan";
        if (Double.isInfinite(x)) return x < 0 ? "-inf" : "inf";
        if (x == 0.0)             return (1.0 / x < 0) ? "-0.0" : "0.0";
        String sign = x < 0 ? "-" : "";
        //  THE SHORTEST DIGITS ARE JAVA'S OWN (JDK 19 on: the shortest text
        //  that reads back, the closest one among equally short); only the
        //  layout is Python's. 'd.dddE-5' or 'ddd.ddd'.
        String text = Double.toString(Math.abs(x));
        int    e    = text.indexOf('E');
        String mantissa = e < 0 ? text : text.substring(0, e);
        int    exponent = e < 0 ? 0 : Integer.parseInt(text.substring(e + 1));
        int    dot      = mantissa.indexOf('.');
        String digits   = mantissa.substring(0, dot) + mantissa.substring(dot + 1);
        int    point    = dot + exponent;          // value = 0.<digits> * 10^point
        int    lead = 0;
        while (lead < digits.length() - 1 && digits.charAt(lead) == '0') { ++lead; --point; }
        digits = digits.substring(lead);
        int end = digits.length();
        while (end > 1 && digits.charAt(end - 1) == '0') --end;
        digits = digits.substring(0, end);
        //  JAVA KEEPS A SECOND DIGIT where one would read back but two come
        //  closer ('4.9E-324'); Python keeps the one ('5e-324').
        if (digits.length() == 2) {
            String one = oneDigit(Math.abs(x), digits, point);
            if (one != null) {
                if (one.length() == 2) { digits = one.substring(0, 1); point += 1; }
                else                     digits = one;
            }
        }
        int n = digits.length();

        StringBuilder out = new StringBuilder(sign);
        if (point > -4 && point <= 16) {
            if (point <= 0)      out.append("0.").append("0".repeat(-point)).append(digits);
            else if (point >= n) out.append(digits).append("0".repeat(point - n)).append(".0");
            else                 out.append(digits, 0, point).append('.').append(digits, point, n);
        } else {
            int ex = point - 1;
            out.append(digits.charAt(0));
            if (n > 1) out.append('.').append(digits, 1, n);
            out.append('e').append(ex < 0 ? '-' : '+');
            String magnitude = Integer.toString(Math.abs(ex));
            if (magnitude.length() < 2) out.append('0');
            out.append(magnitude);
        }
        return out.toString();
    }

    /** RETURN: String, the one digit d -- "10" where it carries -- for
     *          which d * 10^(point - 1) reads back to 'x' (the nearer of the
     *          two around 'digits'' first digit, where both do); null where
     *          no one-digit decimal reads back. 'x' > 0; 'digits' is Java's
     *          two-digit shortest, x ~ 0.<digits> * 10^point. */
    private static String oneDigit(double x, String digits, int point) {
        int        low   = digits.charAt(0) - '0';
        BigDecimal exact = new BigDecimal(x);
        String     best  = null;
        BigDecimal bestGap = null;
        for (int d = low; d <= low + 1; ++d) {
            if (d == 0) continue;
            BigDecimal candidate = BigDecimal.valueOf(d).scaleByPowerOfTen(point - 1);
            if (candidate.doubleValue() != x) continue;
            BigDecimal gap = candidate.subtract(exact).abs();
            if (best == null || gap.compareTo(bestGap) < 0) { best = Integer.toString(d); bestGap = gap; }
        }
        return best;
    }

    /** RETURN: String, 'text' as Python's 'repr(str)' writes it -- single
     *          quotes, or double ones where it holds a single quote and no
     *          double one; backslash, that quote, '\t', '\n', '\r' escaped,
     *          what Python does not print as '\xhh', '\\uhhhh' or
     *          '\Uhhhhhhhh'; every other character as it stands. */
    public static String strRepr(String text) {
        char quote = (text.indexOf('\'') >= 0 && text.indexOf('"') < 0) ? '"' : '\'';
        StringBuilder out = new StringBuilder();
        out.append(quote);
        for (int i = 0; i < text.length(); ) {
            int c = text.codePointAt(i);
            i += Character.charCount(c);
            if      (c == '\\')  out.append("\\\\");
            else if (c == quote) out.append('\\').append(quote);
            else if (c == '\t')  out.append("\\t");
            else if (c == '\n')  out.append("\\n");
            else if (c == '\r')  out.append("\\r");
            else if (c < 0x20 || c == 0x7f) out.append(String.format("\\x%02x", c));
            else if (c < 0x7f || printable(c)) out.appendCodePoint(c);
            else if (c < 0x100)   out.append(String.format("\\x%02x", c));
            else if (c < 0x10000) out.append(String.format("\\u%04x", c));
            else                  out.append(String.format("\\U%08x", c));
        }
        return out.append(quote).toString();
    }

    /** RETURN: boolean, true where Python's 'str.isprintable' holds for the
     *          code point 'c' (not a control, format, surrogate, private,
     *          unassigned or separator character -- the blank excepted). */
    private static boolean printable(int c) {
        if (c == ' ') return true;
        switch (Character.getType(c)) {
            case Character.CONTROL: case Character.FORMAT: case Character.SURROGATE:
            case Character.PRIVATE_USE: case Character.UNASSIGNED:
            case Character.LINE_SEPARATOR: case Character.PARAGRAPH_SEPARATOR:
            case Character.SPACE_SEPARATOR:
                return false;
            default:
                return true;
        }
    }

    /** RETURN: String, the bytes 'data' as Python's 'repr(bytes)' writes them
     *          -- "b'\x1b[A'": printable ASCII as it stands, '\t', '\n',
     *          '\r', the backslash and the quote escaped, every other byte
     *          as '\xhh'. */
    public static String bytesRepr(byte[] data) {
        boolean single = false, dual = false;
        for (byte b : data) { if (b == '\'') single = true; if (b == '"') dual = true; }
        char quote = (single && !dual) ? '"' : '\'';
        StringBuilder out = new StringBuilder("b");
        out.append(quote);
        for (byte b : data) {
            int c = b & 0xFF;
            if      (c == '\\')  out.append("\\\\");
            else if (c == quote) out.append('\\').append(quote);
            else if (c == '\t')  out.append("\\t");
            else if (c == '\n')  out.append("\\n");
            else if (c == '\r')  out.append("\\r");
            else if (c < 0x20 || c >= 0x7f) out.append(String.format("\\x%02x", c));
            else out.append((char) c);
        }
        return out.append(quote).toString();
    }

    /** RETURN: String, "True" for true, "False" for false. */
    public static String bool(boolean value) { return value ? "True" : "False"; }

    /** RETURN: String, 'value' as Python's 'repr' writes the value it stands
     *          for: null 'None'; Boolean 'True'/'False'; Double and Float by
     *          'floatRepr'; an integer type and BigInteger in decimal;
     *          BigDecimal by 'floatRepr' of its double; String by 'strRepr';
     *          byte[] by 'bytesRepr'; a Collection as a list '[a, b]'; an
     *          Object[] as a tuple '(a, b)', '(a,)' for one; a Map as a dict
     *          '{k: v}'; anything else by its 'toString'. */
    public static String repr(Object value) {
        if (value == null)                return "None";
        if (value instanceof Boolean b)   return bool(b);
        if (value instanceof Double d)    return floatRepr(d);
        if (value instanceof Float f)     return floatRepr(f.doubleValue());
        if (value instanceof BigDecimal d) return floatRepr(d.doubleValue());
        if (value instanceof String s)    return strRepr(s);
        if (value instanceof Character c) return strRepr(c.toString());
        if (value instanceof byte[] b)    return bytesRepr(b);
        if (value instanceof Collection<?> c) return join("[", c.toArray(), "]", false);
        if (value instanceof Object[] a)  return join("(", a, ")", a.length == 1);
        if (value instanceof Map<?, ?> m) {
            StringBuilder out = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> e : m.entrySet()) {
                if (!first) out.append(", ");
                out.append(repr(e.getKey())).append(": ").append(repr(e.getValue()));
                first = false;
            }
            return out.append('}').toString();
        }
        return value.toString();
    }

    /** RETURN: String, 'value' as Python's 'str' writes it: a String as it
     *          stands, everything else as 'repr' writes it. */
    public static String str(Object value) {
        return value instanceof String s ? s : repr(value);
    }

    /** RETURN: String, the name of the Python type 'value' stands for --
     *          'NoneType', 'bool', 'int', 'float', 'str', 'bytes', 'list',
     *          'tuple', 'dict'; the Java class's simple name for anything
     *          else. */
    public static String typeName(Object value) {
        if (value == null)                       return "NoneType";
        if (value instanceof Boolean)            return "bool";
        if (value instanceof Double || value instanceof Float
            || value instanceof BigDecimal)      return "float";
        if (value instanceof Number)             return "int";
        if (value instanceof String || value instanceof Character) return "str";
        if (value instanceof byte[])             return "bytes";
        if (value instanceof Collection<?>)      return "list";
        if (value instanceof Object[])           return "tuple";
        if (value instanceof Map<?, ?>)          return "dict";
        return value.getClass().getSimpleName();
    }

    /** RETURN: String, the tuple of 'items' as Python prints it -- '()',
     *          "('a',)", "('a', 'b')". */
    public static String tupleRepr(Collection<?> items) {
        return join("(", items.toArray(), ")", items.size() == 1);
    }

    /** RETURN: String, 'text' filled with blanks on the right to 'width'
     *          CHARACTERS (code points), as Python's '%-6s' counts; 'text'
     *          itself where it is as long or longer. */
    public static String ljust(String text, int width) {
        int n = text.codePointCount(0, text.length());
        return n >= width ? text : text + " ".repeat(width - n);
    }

    /** RETURN: String, 'text' filled with blanks on the left to 'width'
     *          characters (code points), as Python's '%6s' counts. */
    public static String rjust(String text, int width) {
        int n = text.codePointCount(0, text.length());
        return n >= width ? text : " ".repeat(width - n) + text;
    }

    /** RETURN: byte[], 'text' encoded as UTF-8 -- Python's 'str.encode()'. */
    public static byte[] utf8(String text) { return text.getBytes(StandardCharsets.UTF_8); }

    /** RETURN: String, the items' 'repr' between 'open' and 'close',
     *          separated by ', '; a trailing ',' after a single item where
     *          'oneComma'. */
    private static String join(String open, Object[] items, String close, boolean oneComma) {
        StringBuilder out = new StringBuilder(open);
        for (int i = 0; i < items.length; ++i) {
            if (i > 0) out.append(", ");
            out.append(repr(items[i]));
        }
        if (oneComma) out.append(',');
        return out.append(close).toString();
    }
}
