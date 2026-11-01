// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: Parse the HOCON subset of the specification language into the
//          ANNOTATED TREE -- the port of 'python/hwut_hocon.py' (read
//          '../python/README-hwut_hocon.txt'): every key, every value and
//          every block carries its file-relative position.
//
//     const { parse, SourceLine } = require(path.join(__dirname, '..', 'hwut_hocon.js'));
//     const lineList = text.split('\n').map((t, i) => new SourceLine(t, i + 1, 0));
//     const [document, faultList] = parse(lineList, 'f.hocon');
//     document.get('a').node.value;  String(faultList[0]);  // 'f.hocon:3:5: SYNTAX: ...'
//
// THE SUBSET: nested objects, lists, numbers (decimal, 0x, 0b, 0o, roman 0r,
// '_' between digits), booleans (true/false/yes/no), the spellings of nothing
// (null/nil/none/nihil, or an empty value), '#' and '//' comments, '=' or ':'
// before a value, a brace directly after a key. A string value is written in
// double quotes; a text of several lines in triple quotes, laid out as a
// docstring ('inspect.cleandoc'). 'include', '${...}' and '+=' are REFUSED by
// name. The parser accumulates faults and recovers at the next line; it
// never throws.
//
// PYTHON'S TYPES IN JS (where node differs): JS has one number. A
// ScalarNode therefore carries 'py_type' -- 'str', 'int', 'float', 'bool' or
// 'NoneType' -- the type Python's parser gives the value, and 'repr()' writes
// the value as Python's '%r' does ('-1500.0' for the float, '42' for the
// int). An int is a JS number where it is a safe integer, a BigInt beyond
// (Python's ints have no bound). Columns count code points, as Python's
// string indices do.
//_____________________________________________________________________________
'use strict';

const path = require('path');
const { floatRepr, strRepr } = require(path.join(__dirname, 'pytext.js'));

const E_ParseFault = Object.freeze({ SYNTAX: 'SYNTAX', REFUSED: 'REFUSED' });

class Position {
    /* RETURN: Position, one place in one file; 1-based, as an editor counts. */
    constructor(line, column) { this.line = line; this.column = column; Object.freeze(this); }

    /* RETURN: string, 'line:column'. */
    toString() { return `${this.line}:${this.column}`; }
}

class ParseFault {
    /* RETURN: ParseFault, one fault of the parse: 'kind' (an E_ParseFault
     *         name), 'file', 'position', 'message'. */
    constructor(kind, file, position, message) {
        this.kind = kind; this.file = file; this.position = position; this.message = message;
        Object.freeze(this);
    }

    /* RETURN: string, 'file:line:column: KIND: message'. */
    toString() { return `${this.file}:${this.position}: ${this.kind}: ${this.message}`; }
}

class SourceLine {
    /* RETURN: SourceLine, one line as the parser reads it, tied to where it
     *         stands on disk; 'column_offset' counts what was removed before
     *         'text' begins. */
    constructor(text, line, column_offset) {
        this.text = text; this.line = line; this.column_offset = column_offset;
        Object.freeze(this);
    }
}

class ScalarNode {
    /* RETURN: ScalarNode, one scalar value -- string, number (or BigInt),
     *         boolean or null -- at 'position'; 'py_type' is the type Python
     *         gives it (inferred where not given: a number that is an integer
     *         is 'int'). */
    constructor(value, position, py_type) {
        this.value    = value;
        this.position = position;
        this.py_type  = py_type || (value === null ? 'NoneType'
                                  : typeof value === 'string'  ? 'str'
                                  : typeof value === 'boolean' ? 'bool'
                                  : typeof value === 'bigint'  ? 'int'
                                  : Number.isInteger(value)    ? 'int' : 'float');
        Object.freeze(this);
    }

    /* RETURN: string, the value as Python's '%r' writes it: "'text'", '42',
     *         '-1500.0', 'True', 'None'. */
    repr() {
        switch (this.py_type) {
        case 'NoneType': return 'None';
        case 'bool':     return this.value ? 'True' : 'False';
        case 'str':      return strRepr(this.value);
        case 'float':    return floatRepr(this.value);
        default:         return String(this.value);
        }
    }
}

class ListNode {
    /* RETURN: ListNode, one list of nodes ('item_list', frozen) at 'position'. */
    constructor(item_list, position) {
        this.item_list = Object.freeze([...item_list]); this.position = position;
        Object.freeze(this);
    }
}

class Entry {
    /* RETURN: Entry, one key with its value inside an object. */
    constructor(key, key_position, node) {
        this.key = key; this.key_position = key_position; this.node = node;
        Object.freeze(this);
    }
}

class ObjectNode {
    /* RETURN: ObjectNode at 'position', its entries in written order. */
    constructor(position, entry_list = []) { this.position = position; this.entry_list = entry_list; }

    /* RETURN: Entry, the entry named 'key'; null, no such entry. */
    get(key) {
        for (const entry of this.entry_list) if (entry.key === key) return entry;
        return null;
    }

    /* RETURN: array of strings, the keys in written order. */
    keys() { return this.entry_list.map(entry => entry.key); }
}

const BOOL_DB  = { true: true, yes: true, false: false, no: false };
const NULL_SET = ['null', 'nil', 'none', 'nihil'];
const SIGN_SET = ['+', '-'];

const DECIMAL_RE = new RegExp('^[-+]?'
    + '(?:[0-9](?:_?[0-9])*(?:\\.(?:[0-9](?:_?[0-9])*)?)?'
    + '|\\.[0-9](?:_?[0-9])*)'
    + '(?:[eE][-+]?[0-9](?:_?[0-9])*)?$');
const RADIX_DB       = { '0x': 16, '0X': 16, '0b': 2, '0B': 2, '0o': 8, '0O': 8 };
const RADIX_PREFIX   = { 16: '0x', 2: '0b', 8: '0o' };
const RADIX_DIGIT_DB = { 16: '0123456789abcdefABCDEF', 2: '01', 8: '01234567' };
const ROMAN_RE       = /^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$/;
const ROMAN_VALUE_DB = { I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000 };

const NOT_A_TOKEN = Symbol('NOT_A_TOKEN');   // a bare token that is none: an unquoted string

const TOKEN_RE        = /[^\s{}\[\]=,:"#]*/uy;
const QUOTED_PLAIN_RE = /([^"\\\n]*)"/y;
const ESCAPE_DB       = { n: '\n', t: '\t', '"': '"', '\\': '\\' };
const TRIPLE_QUOTE    = '"""';
const SURROGATE_RE    = /[\uD800-\uDFFF]/;

/* RETURN: string, the run of token characters in 'text' from index 'i' on
 *         (possibly empty). */
function tokenAt(text, i) {
    TOKEN_RE.lastIndex = i;
    return TOKEN_RE.exec(text)[0];
}

class Cursor {
    /* RETURN: Cursor at the first character of the SourceLine list
     *         'line_list'; every position it reports is file-relative. */
    constructor(line_list) {
        this.line_list = line_list;
        this.line_n    = line_list.length;
        this.i_line    = 0;
        this.i_col     = 0;
        this.text      = line_list.length ? line_list[0].text : '';
    }

    /* RETURN: boolean, no character remains. */
    at_end() { return this.i_line >= this.line_n; }

    /* RETURN: string, the character 'ahead' places from here on this line
     *         (a whole code point); '\n' at this line's end; '' beyond the
     *         last line. */
    peek(ahead = 0) {
        if (this.i_line >= this.line_n) return '';
        const i = this.i_col + ahead;
        if (i >= this.text.length) return '\n';
        return String.fromCodePoint(this.text.codePointAt(i));
    }

    /* RETURN: undefined. Steps one character; line ends step to the next line. */
    advance() {
        if (this.i_line >= this.line_n) return;
        if (this.i_col < this.text.length) this.i_col += this.peek().length;
        else                               this.skip_line();
    }

    /* RETURN: undefined. Steps 'n' code units WITHIN the current line; the
     *         caller has seen that they are there. */
    skip(n) { this.i_col += n; }

    /* RETURN: undefined. Steps to the beginning of the next line. */
    skip_line() {
        this.i_line += 1;
        this.i_col   = 0;
        this.text    = this.i_line < this.line_n ? this.line_list[this.i_line].text : '';
    }

    /* RETURN: Position, file-relative, of the character at the cursor --
     *         columns in code points. */
    position() {
        if (this.i_line >= this.line_n) {
            if (!this.line_list.length) return new Position(1, 1);
            const last = this.line_list[this.line_list.length - 1];
            return new Position(last.line, last.column_offset + codePointLength(last.text) + 1);
        }
        const line = this.line_list[this.i_line];
        const col  = SURROGATE_RE.test(this.text) ? codePointLength(this.text.slice(0, this.i_col)) : this.i_col;
        return new Position(line.line, line.column_offset + col + 1);
    }
}

/* RETURN: integer, the number of code points of 's'. */
function codePointLength(s) {
    if (!SURROGATE_RE.test(s)) return s.length;
    let n = 0;
    for (const _ of s) n += 1;          // eslint-disable-line no-unused-vars
    return n;
}

/* RETURN: [ObjectNode, array of ParseFault] -- the document, every entry of
 *         the outermost level (possibly empty), and every fault found (empty
 *         on a clean parse). 'line_list' are SourceLines; 'file' names the
 *         file for faults. Never throws on any text. */
function parse(line_list, file) {
    const fault_list = [];
    const cursor     = new Cursor(line_list);
    const document   = parseBody(cursor, null, file, fault_list);
    return [document, fault_list];
}

/* RETURN: ObjectNode, the entries up to 'terminator' ('}', or null for the
 *         end of the text). */
function parseBody(cursor, terminator, file, fault_list) {
    const result = new ObjectNode(cursor.position());
    while (true) {
        skipBlank(cursor);
        if (cursor.at_end()) {
            if (terminator !== null)
                fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, cursor.position(),
                                               `unterminated object: '${terminator}' missing`));
            return result;
        }
        const c = cursor.peek();
        if (c === terminator) { cursor.skip(1); return result; }
        if (c === '}') {
            fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, cursor.position(), "unmatched '}'"));
            cursor.skip(1);
        } else {
            parseEntry(cursor, result, file, fault_list);
        }
    }
}

/* RETURN: undefined. Parses one 'key = value' pair into 'object_node';
 *         faults recover at the next line. */
function parseEntry(cursor, object_node, file, fault_list) {
    const key_position = cursor.position();
    const key          = parseKey(cursor, file, fault_list);
    if (key === null) { cursor.skip_line(); return; }

    if (key === 'include') {
        fault_list.push(new ParseFault(E_ParseFault.REFUSED, file, key_position,
            "'include' does not exist here: a specification refers to nothing outside its file"));
        cursor.skip_line();
        return;
    }

    skipSpace(cursor);
    const c = cursor.peek();
    if (c === '=' || c === ':') {
        cursor.skip(1);
        skipSpace(cursor);
    } else if (c === '{') {
        // a brace binds without a sign
    } else if (c === '+' && cursor.peek(1) === '=') {
        fault_list.push(new ParseFault(E_ParseFault.REFUSED, file, cursor.position(), "'+=' does not exist here"));
        cursor.skip_line();
        return;
    } else {
        fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, cursor.position(),
                                       `expected '=', ':' or '{' after key '${key}'`));
        cursor.skip_line();
        return;
    }

    const node = parseValue(cursor, file, fault_list, false);
    if (node === null) return;          // the value parser has recovered already

    if (object_node.get(key) !== null) {
        fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, key_position,
                                       `duplicate key '${key}'; the first stands, this one is refused`));
        return;
    }
    object_node.entry_list.push(new Entry(key, key_position, node));
}

/* RETURN: string, the key; null, no key stands here (fault recorded). */
function parseKey(cursor, file, fault_list) {
    if (cursor.peek() === '"') return parseQuoted(cursor, file, fault_list);
    const text = tokenAt(cursor.text, cursor.i_col);
    if (!text) {
        fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, cursor.position(),
                                       `expected a key, found '${cursor.peek().trim()}'`));
        return null;
    }
    cursor.skip(text.length);
    return text;
}

/* RETURN: ScalarNode | ListNode | ObjectNode, the value here; null, nothing
 *         usable stands here (fault recorded). 'in_list_f' says an empty
 *         value is a fault rather than null. */
function parseValue(cursor, file, fault_list, in_list_f) {
    skipSpace(cursor);
    const position = cursor.position();
    const c = cursor.peek();
    if (c === '{') { cursor.skip(1); return parseBody(cursor, '}', file, fault_list); }
    if (c === '[') { cursor.skip(1); return parseList(cursor, position, file, fault_list); }
    if (c === '"' && cursor.peek(1) === '"' && cursor.peek(2) === '"') {
        const value = parseTripleQuoted(cursor, file, fault_list);
        return value === null ? null : new ScalarNode(value, position, 'str');
    }
    if (c === '"') {
        const value = parseQuoted(cursor, file, fault_list);
        return value === null ? null : new ScalarNode(value, position, 'str');
    }
    if (c === '$' && cursor.peek(1) === '{') {
        fault_list.push(new ParseFault(E_ParseFault.REFUSED, file, position,
            "substitutions '${...}' do not exist here: a specification refers to nothing outside its file"));
        cursor.skip_line();
        return null;
    }
    return parseBare(cursor, position, file, fault_list, in_list_f);
}

/* RETURN: ListNode, the items up to ']' (a fault where it is missing). */
function parseList(cursor, position, file, fault_list) {
    const item_list = [];
    while (true) {
        skipBlank(cursor);
        if (cursor.at_end()) {
            fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, cursor.position(),
                                           "unterminated list: ']' missing"));
            break;
        }
        const c = cursor.peek();
        if (c === ']') { cursor.skip(1); break; }
        if (c === ',') { cursor.skip(1); continue; }
        if (c === '}') {
            //  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' was forgotten.
            fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, cursor.position(),
                                           "unterminated list: ']' missing before '}'"));
            break;
        }
        const beforeLine = cursor.i_line, beforeCol = cursor.i_col;
        const item = parseValue(cursor, file, fault_list, true);
        if (item !== null) item_list.push(item);
        //  NO VALUE READ AND NOTHING CONSUMED: step over the refused character.
        if (item === null && cursor.i_line === beforeLine && cursor.i_col === beforeCol)
            cursor.skip(cursor.peek().length);
    }
    return new ListNode(item_list, position);
}

/* RETURN: string, 'line' with every tab expanded to the next multiple of 8
 *         columns, as Python's 'str.expandtabs()' ('\n' and '\r' restart
 *         the count). */
function expandTabs(text) {
    let out = '', column = 0;
    for (const c of text) {
        if (c === '\t') { const n = 8 - (column % 8); out += ' '.repeat(n); column += n; }
        else if (c === '\n' || c === '\r') { out += c; column = 0; }
        else { out += c; column += 1; }
    }
    return out;
}

/* RETURN: string, 'doc' laid out as Python's 'inspect.cleandoc' lays out a
 *         docstring: tabs expanded, the indentation (in blanks) common to
 *         the lines after the first removed, the first line's leading blanks
 *         removed, empty lines at both ends dropped. */
function cleandoc(doc) {
    const lines = expandTabs(doc).split('\n');
    let margin = Infinity;
    for (const line of lines.slice(1)) {
        const content = line.replace(/^ +/, '').length;
        if (content) margin = Math.min(margin, line.length - content);
    }
    if (lines.length) lines[0] = lines[0].replace(/^ +/, '');
    if (margin < Infinity) for (let i = 1; i < lines.length; i += 1) lines[i] = lines[i].slice(margin);
    while (lines.length && !lines[lines.length - 1]) lines.pop();
    while (lines.length && !lines[0]) lines.shift();
    return lines.join('\n');
}

/* RETURN: string, the text between three double quotes and the next three,
 *         over as many lines as it takes, AS WRITTEN (no escape resolved),
 *         laid out by 'cleandoc'; null, no closing three quotes stand before
 *         the text's end (fault recorded at the opening). */
function parseTripleQuoted(cursor, file, fault_list) {
    const begin = cursor.position();
    cursor.skip(3);
    const piece_list = [];
    while (!cursor.at_end()) {
        const text = cursor.text;
        const end  = text.indexOf(TRIPLE_QUOTE, cursor.i_col);
        if (end >= 0) {
            piece_list.push(text.slice(cursor.i_col, end));
            cursor.i_col = end + 3;
            return cleandoc(piece_list.join('\n'));
        }
        piece_list.push(text.slice(cursor.i_col));
        cursor.skip_line();
    }
    fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, begin,
                                   `unterminated triple-quoted string: closing '"""' missing`));
    return null;
}

/* RETURN: string, the quoted string's content, escapes ('\n', '\t', '\"',
 *         '\\'; any other escaped character stands for itself) resolved;
 *         null, the string is unterminated at its line's end (fault
 *         recorded). */
function parseQuoted(cursor, file, fault_list) {
    const begin = cursor.position();
    const text  = cursor.text;
    let   i     = cursor.i_col + 1;          // past the opening quote

    QUOTED_PLAIN_RE.lastIndex = i;
    const match = QUOTED_PLAIN_RE.exec(text);
    if (match !== null) {
        cursor.i_col = QUOTED_PLAIN_RE.lastIndex;
        return match[1];
    }
    const piece_list = [];
    while (true) {
        if (i >= text.length) {
            fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, begin, 'unterminated string'));
            cursor.i_col = i;
            return null;
        }
        const c = text[i];
        if (c === '"') { cursor.i_col = i + 1; return piece_list.join(''); }
        if (c === '\\') {
            i += 1;
            const escaped = i < text.length ? String.fromCodePoint(text.codePointAt(i)) : '';
            piece_list.push(Object.prototype.hasOwnProperty.call(ESCAPE_DB, escaped) ? ESCAPE_DB[escaped] : escaped);
            i += escaped.length || 1;
        } else {
            piece_list.push(c);
            i += 1;
        }
    }
}

/* RETURN: integer, the index of the first character at or after 'i' in
 *         'text' that is no blank (' ' or tab). */
function blankEnd(text, i) {
    while (i < text.length && (text[i] === ' ' || text[i] === '\t')) i += 1;
    return i;
}

/* RETURN: ScalarNode, the bare token here: a boolean, a number, or one of
 *         the spellings of nothing (an empty value outside a list is null);
 *         null, the token is none of those (fault recorded) -- a string is
 *         written in double quotes. */
function parseBare(cursor, position, file, fault_list, in_list_f) {
    let raw = tokenAt(cursor.text, cursor.i_col);

    //  A SIGN STANDING APART from its digits: '- 0.12'.
    if (SIGN_SET.includes(raw)) {
        const text  = cursor.text;
        const after = tokenAt(text, blankEnd(text, cursor.i_col + 1));
        //  The two must make ONE number: '- -1.5e3' does not (python hwut_hocon).
        if (after && number(after) !== NOT_A_TOKEN && number(raw + after) !== NOT_A_TOKEN) {
            cursor.i_col = blankEnd(text, cursor.i_col + 1) + after.length;
            return scalarOf(number(raw + after), position);
        }
    }
    if (raw.startsWith('${')) {
        fault_list.push(new ParseFault(E_ParseFault.REFUSED, file, cursor.position(),
                                       "substitutions '${...}' do not exist here"));
        cursor.skip_line();
        return null;
    }
    const iComment = raw.indexOf('//');
    if (iComment !== -1) raw = raw.slice(0, iComment);
    cursor.skip(raw.length);

    if (!raw) {
        if (in_list_f) {
            fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, position,
                                           `expected a value, found '${cursor.peek().trim()}'`));
            return null;
        }
        return new ScalarNode(null, position, 'NoneType');     // an empty value is null
    }
    const value = interpret(raw);
    if (value === NOT_A_TOKEN) {
        fault_list.push(new ParseFault(E_ParseFault.SYNTAX, file, position,
                                       `a string is written in double quotes: "${raw}"`));
        return null;
    }
    return scalarOf(value, position);
}

/* RETURN: ScalarNode of 'value' -- [number, 'int'|'float'] from 'number',
 *         or a boolean, or null -- at 'position'. */
function scalarOf(value, position) {
    if (Array.isArray(value)) return new ScalarNode(value[0], position, value[1]);
    return new ScalarNode(value, position);
}

/* RETURN: null, boolean, or [value, 'int'|'float'] -- what the bare text
 *         says; null for the spellings of nothing; NOT_A_TOKEN where it is
 *         no bare token at all (an unquoted string). */
function interpret(raw) {
    if (NULL_SET.includes(raw)) return null;
    if (Object.prototype.hasOwnProperty.call(BOOL_DB, raw)) return BOOL_DB[raw];
    return number(raw);
}

/* RETURN: number or BigInt, the integer 'value' (a BigInt) as JS holds it:
 *         a number where it is a safe integer, the BigInt else. */
function intOf(value) {
    const n = Number(value);
    return Number.isSafeInteger(n) ? n : value;
}

/* RETURN: [value, 'int'|'float'], the number the text spells, in whatever
 *         radix it spells it ('_' enters no value); NOT_A_TOKEN, the text
 *         spells no number. */
function number(raw) {
    const signF = SIGN_SET.includes(raw.slice(0, 1));
    const body  = signF ? raw.slice(1) : raw;
    const sign  = raw.slice(0, 1) === '-' ? -1n : 1n;
    const prefix = body.slice(0, 2);
    if (prefix === '0r' || prefix === '0R') {
        const value = roman(body.slice(2));
        return value === NOT_A_TOKEN ? value : [intOf(sign * BigInt(value)), 'int'];
    }
    if (Object.prototype.hasOwnProperty.call(RADIX_DB, prefix)) {
        const radix = RADIX_DB[prefix];
        const digitText = withoutHelper(body.slice(2), RADIX_DIGIT_DB[radix]);
        if (digitText === null) return NOT_A_TOKEN;
        return [intOf(sign * BigInt(RADIX_PREFIX[radix] + digitText)), 'int'];
    }
    if (!DECIMAL_RE.test(raw)) return NOT_A_TOKEN;
    const text = raw.replace(/_/g, '');
    if (/[.eE]/.test(text)) return [Number(text), 'float'];
    const digits = text.replace(/^[-+]/, '');
    return [intOf((text[0] === '-' ? -1n : 1n) * BigInt(digits)), 'int'];
}

/* RETURN: string, 'text' with every '_' removed; null, the text carries no
 *         digit, a character that is no digit of the radix ('digitSet'), or
 *         an '_' that separates nothing. */
function withoutHelper(text, digitSet) {
    if (!text || text[0] === '_' || text[text.length - 1] === '_') return null;
    if (text.includes('__')) return null;
    const stripped = text.replace(/_/g, '');
    if (!stripped) return null;
    for (const c of stripped) if (!digitSet.includes(c)) return null;
    return stripped;
}

/* RETURN: integer, the number the roman numeral 'text' spells (the strict
 *         form); NOT_A_TOKEN, the text is no roman numeral ('IIII', 'VX'). */
function roman(text) {
    if (!text || !ROMAN_RE.test(text)) return NOT_A_TOKEN;
    let total = 0, previous = 0;
    for (const character of [...text].reverse()) {
        const value = ROMAN_VALUE_DB[character];
        total = value < previous ? total - value : total + value;
        previous = Math.max(previous, value);
    }
    return total;
}

/* RETURN: undefined. Skips blanks and comments on the current line. */
function skipSpace(cursor) {
    const text = cursor.text;
    const n    = text.length;
    let   i    = cursor.i_col;
    while (i < n && (text[i] === ' ' || text[i] === '\t')) i += 1;
    cursor.i_col = i;
    if (i < n && (text[i] === '#' || text.startsWith('//', i))) cursor.skip_line();
}

/* RETURN: undefined. Skips blanks, newlines, commas and comments. */
function skipBlank(cursor) {
    while (cursor.i_line < cursor.line_n) {
        const text = cursor.text;
        const n    = text.length;
        let   i    = cursor.i_col;
        while (i < n && (text[i] === ' ' || text[i] === '\t' || text[i] === ',')) i += 1;
        if (i >= n) { cursor.skip_line(); continue; }
        cursor.i_col = i;
        const c = text[i];
        if (c === '#' || (c === '/' && text.startsWith('//', i))) { cursor.skip_line(); continue; }
        return;
    }
}

module.exports = { parse, E_ParseFault, Position, ParseFault, SourceLine,
                   ScalarNode, ListNode, Entry, ObjectNode, cleandoc };
