// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: TEXT AS PYTHON PRINTS IT -- so a node test and a Python test of the
//          same module print the same bytes, and share one GOOD file by a
//          '.link' (bookkeeper B-32). The port of 'perl/Hwut/PyText.pm' and
//          'c/hwut_pytext.c'.
//
//     floatRepr(1.0)          '1.0'          repr(1.0)
//     floatRepr(0.1)          '0.1'          the shortest text that reads back
//     floatRepr(1e-05)        '1e-05'        exponential below 1e-4 ...
//     floatRepr(1e16)         '1e+16'        ... and from 1e16 on
//     listRepr([3, 1])        '[3, 1]'       numbers bare
//     listRepr(['a'], true)   "['a']"        strings quoted, as repr quotes them
//     tupleRepr(['a'], true)  "('a',)"       a tuple of one keeps its comma
//     bytesRepr("\x1b[A")     "b'\\x1b[A'"   a byte string, as Python's bytes
//     boolText(1)             'True'
//     noneOr(null)            'None'
//
// A float is told from an integer by the caller: JS has one number type,
// Python has two, and only the test knows which one it printed.
//_____________________________________________________________________________
'use strict';

//  WHAT PYTHON'S 'str.isprintable' REFUSES: categories Other and Separator.
const NOT_PRINTABLE_RE = /^[\p{C}\p{Z}]$/u;

/* RETURN: string, 'x' as Python's 'repr(float)' writes it -- the shortest
 *         decimal that reads back to the same double (JS's own shortest
 *         digits), fixed notation where the decimal point falls in (-4, 16],
 *         exponential with a signed two-digit exponent else; 'nan', 'inf',
 *         '-inf', '-0.0' as Python writes them. */
function floatRepr(x) {
    if (Number.isNaN(x))     return 'nan';
    if (x === Infinity)      return 'inf';
    if (x === -Infinity)     return '-inf';
    if (x === 0)             return Object.is(x, -0) ? '-0.0' : '0.0';
    const m = /^(-?)(\d)(?:\.(\d+))?e([-+]\d+)$/.exec(x.toExponential());
    const sign   = m[1];
    let   digits = (m[2] + (m[3] || '')).replace(/0+$/, '') || '0';
    const point  = parseInt(m[4], 10) + 1;     // value = 0.<digits> * 10^point
    if (point > -4 && point <= 16) {
        const n = digits.length;
        if (point <= 0) return sign + '0.' + '0'.repeat(-point) + digits;
        if (point >= n) return sign + digits + '0'.repeat(point - n) + '.0';
        return sign + digits.slice(0, point) + '.' + digits.slice(point);
    }
    const mantissa = digits.length > 1 ? digits[0] + '.' + digits.slice(1) : digits;
    const e        = point - 1;
    return sign + mantissa + 'e' + (e < 0 ? '-' : '+') + String(Math.abs(e)).padStart(2, '0');
}

/* RETURN: string, 's' in the quotes Python's repr chooses -- single, or
 *         double where it holds a single quote and no double one -- the
 *         backslash, that quote and what does not print escaped: '\n', '\t',
 *         '\r', and '\xNN', '\uNNNN', '\UNNNNNNNN' for what Python's
 *         'str.isprintable' refuses (Unicode's categories Other and
 *         Separator, the blank excepted; by node's Unicode tables, which may
 *         be a version apart from Python's for characters assigned lately).
 *         Where 'bytesF', every code below 0x20 or from 0x7f on is '\xNN'. */
function quoted(s, bytesF) {
    const quote = (s.includes("'") && !s.includes('"')) ? '"' : "'";
    let out = '';
    for (const c of s) {
        const n = c.codePointAt(0);
        if      (c === '\\')  out += '\\\\';
        else if (c === quote) out += '\\' + quote;
        else if (c === '\n')  out += '\\n';
        else if (c === '\t')  out += '\\t';
        else if (c === '\r')  out += '\\r';
        else if (bytesF ? (n < 0x20 || n >= 0x7f) : (c !== ' ' && NOT_PRINTABLE_RE.test(c)))
            out += n < 0x100   ? '\\x' + n.toString(16).padStart(2, '0')
                 : n < 0x10000 ? '\\u' + n.toString(16).padStart(4, '0')
                 :               '\\U' + n.toString(16).padStart(8, '0');
        else out += c;
    }
    return quote + out + quote;
}

/* RETURN: string, 's' as Python's 'repr(str)' writes a plain string. */
function strRepr(s) { return quoted(String(s), false); }

/* RETURN: string, the byte string 'b' -- a Buffer, or a string whose
 *         characters are bytes (0..255) -- as Python's 'repr(bytes)' writes
 *         it: "b'\x1b[A'". */
function bytesRepr(b) {
    const s = Buffer.isBuffer(b) ? b.toString('latin1') : String(b);
    return 'b' + quoted(s, true);
}

/* RETURN: string, the array 'list' as Python prints a list -- '[a, b]';
 *         each element quoted as a string where 'stringsF', bare else. */
function listRepr(list, stringsF) {
    return '[' + list.map(x => stringsF ? strRepr(x) : String(x)).join(', ') + ']';
}

/* RETURN: string, the array 'list' as Python prints a tuple -- '()',
 *         "('a',)" for one element, "('a', 'b')"; quoted where 'stringsF'. */
function tupleRepr(list, stringsF) {
    const item = list.map(x => stringsF ? strRepr(x) : String(x));
    if (item.length === 0) return '()';
    if (item.length === 1) return '(' + item[0] + ',)';
    return '(' + item.join(', ') + ')';
}

/* RETURN: string, 'None' where 'value' is null or undefined, String(value) else. */
function noneOr(value) { return value === null || value === undefined ? 'None' : String(value); }

/* RETURN: string, 'True' where 'value' is truthy, 'False' else. */
function boolText(value) { return value ? 'True' : 'False'; }

/* RETURN: number (integral), 'x' rounded as Python's 'round(x)' -- to the
 *         nearest integer, an exact half to the EVEN one. */
function pyRound(x) {
    const f = Math.floor(x), d = x - f;
    if (d < 0.5) return f;
    if (d > 0.5) return f + 1;
    return (f % 2 === 0) ? f : f + 1;
}

module.exports = { floatRepr, strRepr, bytesRepr, listRepr, tupleRepr, noneOr, boolText, pyRound };
