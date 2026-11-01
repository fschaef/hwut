// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: Parse the HOCON subset of the specification language into the
//          ANNOTATED TREE -- the port of 'python/hwut_hocon.py'
//          (README-hwut_hocon.txt): every key, every value and every block
//          carries its file-relative position.
//
//     use hwut::hwut_hocon::{parse, SourceLine, Node};
//     let line_list: Vec<SourceLine> = text.split('\n').enumerate()
//         .map(|(i, l)| SourceLine::new(l, i as i64 + 1, 0)).collect();
//     let (document, fault_list) = parse(&line_list, "f.hocon");
//
// THE SUBSET: nested objects, lists, numbers (every radix, '_' between
// digits), booleans (true/false/yes/no), the spellings of nothing, '#' and
// '//' comments, '=' or ':' before a value, a brace directly after a key. A
// string value is written in double quotes; a text of several lines in
// triple quotes, laid out as Python's 'inspect.cleandoc' lays it out.
// REFUSED BY NAME: 'include', '${...}', '+='.
//
// The parser accumulates faults and recovers at the next line; it never
// panics on any text. A COLUMN COUNTS CHARACTERS (code points), as Python's.
//
// WHERE RUST DIFFERS: a scalar's value is a 'Value' -- Python's type is its
// variant ('Value::type_name' says 'int', 'float', 'str', 'bool',
// 'NoneType'). An integer is i128; Python's are unbounded, so a literal
// beyond i128 wraps (none of the specification's numbers comes near).
//______________________________________________________________________________
use std::collections::HashSet;
use std::fmt;
use std::sync::OnceLock;

use crate::hwut_pytext::{float_repr, str_repr, PyRepr};

/// What kind a fault is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EParseFault {
    /// The text does not parse.
    Syntax,
    /// A construct that does not exist here, by name.
    Refused,
}

impl EParseFault {
    /// RETURN: &str, the kind's name as Python's enum prints it: 'SYNTAX',
    ///         'REFUSED'.
    pub fn name(&self) -> &'static str {
        match self { EParseFault::Syntax => "SYNTAX", EParseFault::Refused => "REFUSED" }
    }
}

/// One place in one file; 1-based, as an editor counts.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Position {
    pub line:   i64,
    pub column: i64,
}

impl fmt::Display for Position {
    /// RETURN: fmt::Result; 'line:column' was written.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result { write!(f, "{}:{}", self.line, self.column) }
}

/// One fault of the parse, where it stands and what it is.
#[derive(Clone, Debug, PartialEq)]
pub struct ParseFault {
    pub kind:     EParseFault,
    pub file:     String,
    pub position: Position,
    pub message:  String,
}

impl fmt::Display for ParseFault {
    /// RETURN: fmt::Result; 'file:line:column: KIND: message' was written.
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}:{}: {}: {}", self.file, self.position, self.kind.name(), self.message)
    }
}

/// One line as the parser reads it, tied to where it stands on disk;
/// 'column_offset' counts what was removed before 'text' begins.
#[derive(Clone, Debug)]
pub struct SourceLine {
    pub text:          String,
    pub line:          i64,
    pub column_offset: i64,
}

impl SourceLine {
    /// RETURN: SourceLine of 'text' at line 'line', 'column_offset'
    ///         characters removed before it.
    pub fn new(text: &str, line: i64, column_offset: i64) -> SourceLine {
        SourceLine { text: text.to_string(), line, column_offset }
    }
}

/// One scalar's value, Python's type as the variant.
#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    /// The spellings of nothing, and an empty value: Python's None.
    Null,
    Bool(bool),
    Int(i128),
    Float(f64),
    Str(String),
}

impl Value {
    /// RETURN: &str, Python's type name of the value: 'NoneType', 'bool',
    ///         'int', 'float', 'str'.
    pub fn type_name(&self) -> &'static str {
        match self {
            Value::Null => "NoneType", Value::Bool(_) => "bool", Value::Int(_) => "int",
            Value::Float(_) => "float", Value::Str(_) => "str",
        }
    }
}

impl PyRepr for Value {
    /// RETURN: String, the value as Python's 'repr()' writes it.
    fn py_repr(&self) -> String {
        match self {
            Value::Null      => "None".to_string(),
            Value::Bool(b)   => b.py_repr(),
            Value::Int(n)    => n.to_string(),
            Value::Float(x)  => float_repr(*x),
            Value::Str(s)    => str_repr(s),
        }
    }
}

/// One scalar value.
#[derive(Clone, Debug, PartialEq)]
pub struct ScalarNode { pub value: Value, pub position: Position }

/// One list of nodes.
#[derive(Clone, Debug, PartialEq)]
pub struct ListNode { pub item_list: Vec<Node>, pub position: Position }

/// One key with its value inside an object.
#[derive(Clone, Debug, PartialEq)]
pub struct Entry { pub key: String, pub key_position: Position, pub node: Node }

/// One object: ordered entries, duplicate keys refused at parse.
#[derive(Clone, Debug, PartialEq)]
pub struct ObjectNode { pub position: Position, pub entry_list: Vec<Entry> }

impl ObjectNode {
    /// RETURN: Some(&Entry), the entry named 'key'; None, no such entry.
    pub fn get(&self, key: &str) -> Option<&Entry> { self.entry_list.iter().find(|e| e.key == key) }

    /// RETURN: Vec<&str>, the keys in written order.
    pub fn keys(&self) -> Vec<&str> { self.entry_list.iter().map(|e| e.key.as_str()).collect() }
}

/// A value of the tree: a scalar, a list or an object.
#[derive(Clone, Debug, PartialEq)]
pub enum Node {
    Scalar(ScalarNode),
    List(ListNode),
    Object(ObjectNode),
}

const SIGN_SET: [&str; 2] = ["+", "-"];
const NULL_SET: [&str; 4] = ["null", "nil", "none", "nihil"];

/// RETURN: bool, true where 'c' is a blank as Python's regex '\s' says.
fn py_isspace(c: char) -> bool { c.is_whitespace() || ('\x1c'..='\x1f').contains(&c) }

/// RETURN: bool, true where 'c' ends a token: '[\s{}\[\]=,:"#]'.
fn ends_token(c: char) -> bool { py_isspace(c) || "{}[]=,:\"#".contains(c) }

/// Walks the lines character by character; every position it reports is
/// file-relative through the lines' offsets.
struct Cursor<'a> {
    line_list: &'a [SourceLine],
    char_list: Vec<Vec<char>>,
    i_line:    usize,
    i_col:     usize,
}

const EMPTY: &[char] = &[];

impl<'a> Cursor<'a> {
    /// RETURN: Cursor at the first character of 'line_list'.
    fn new(line_list: &'a [SourceLine]) -> Cursor<'a> {
        Cursor { line_list, char_list: line_list.iter().map(|l| l.text.chars().collect()).collect(),
                 i_line: 0, i_col: 0 }
    }

    /// RETURN: &[char], the current line's characters ('' beyond the last).
    fn text(&self) -> &[char] { self.char_list.get(self.i_line).map(|v| v.as_slice()).unwrap_or(EMPTY) }

    /// RETURN: bool, no character remains.
    fn at_end(&self) -> bool { self.i_line >= self.char_list.len() }

    /// RETURN: Option<char>, the character 'ahead' places from here on this
    ///         line; Some('\n') at this line's end; None beyond the last line
    ///         (Python's '').
    fn peek(&self, ahead: usize) -> Option<char> {
        if self.at_end() { return None; }
        Some(*self.text().get(self.i_col + ahead).unwrap_or(&'\n'))
    }

    /// RETURN: nothing; steps 'n' characters WITHIN the current line.
    fn skip(&mut self, n: usize) { self.i_col += n; }

    /// RETURN: nothing; steps to the beginning of the next line.
    fn skip_line(&mut self) { self.i_line += 1; self.i_col = 0; }

    /// RETURN: Position, file-relative, of the character at the cursor.
    fn position(&self) -> Position {
        if self.at_end() {
            match self.line_list.last() {
                None       => Position { line: 1, column: 1 },
                Some(last) => Position { line: last.line,
                                         column: last.column_offset + last.text.chars().count() as i64 + 1 },
            }
        } else {
            let line = &self.line_list[self.i_line];
            Position { line: line.line, column: line.column_offset + self.i_col as i64 + 1 }
        }
    }

    /// RETURN: String, the token at the cursor: the run of characters up to
    ///         the first that binds, opens, closes or separates ('' at the
    ///         line's end).
    fn token_at(&self, i: usize) -> String {
        let text = self.text();
        let mut end = i.min(text.len());
        while end < text.len() && !ends_token(text[end]) { end += 1; }
        text[i.min(text.len())..end].iter().collect()
    }
}

/// RETURN: String, 'c' as Python's 'str.strip()' leaves a character: ''
///         for a blank or nothing.
fn stripped(c: Option<char>) -> String {
    match c { Some(c) if !py_isspace(c) => c.to_string(), _ => String::new() }
}

/// Collects the faults of one parse.
struct Parse<'a> {
    file:       &'a str,
    fault_list: Vec<ParseFault>,
}

impl Parse<'_> {
    /// RETURN: nothing; the fault is recorded.
    fn fault(&mut self, kind: EParseFault, position: Position, message: String) {
        self.fault_list.push(ParseFault { kind, file: self.file.to_string(), position, message });
    }
}

/// RETURN: (ObjectNode, Vec<ParseFault>) -- the document, every entry of the
///         outermost level, possibly empty; and every fault found, empty on
///         a clean parse. 'file' names the file for the faults.
pub fn parse(line_list: &[SourceLine], file: &str) -> (ObjectNode, Vec<ParseFault>) {
    let mut p      = Parse { file, fault_list: Vec::new() };
    let mut cursor = Cursor::new(line_list);
    let document   = parse_body(&mut cursor, None, &mut p);
    (document, p.fault_list)
}

/// RETURN: ObjectNode, the entries up to 'terminator' ('}', or None for the
///         end of the text).
fn parse_body(cursor: &mut Cursor, terminator: Option<char>, p: &mut Parse) -> ObjectNode {
    let mut result = ObjectNode { position: cursor.position(), entry_list: Vec::new() };
    loop {
        skip_blank(cursor);
        if cursor.at_end() {
            if let Some(t) = terminator {
                p.fault(EParseFault::Syntax, cursor.position(), format!("unterminated object: '{}' missing", t));
            }
            return result;
        }
        let c = cursor.peek(0);
        if c.is_some() && c == terminator { cursor.skip(1); return result; }
        if c == Some('}') {
            p.fault(EParseFault::Syntax, cursor.position(), "unmatched '}'".to_string());
            cursor.skip(1);
        } else {
            parse_entry(cursor, &mut result, p);
        }
    }
}

/// RETURN: nothing; one 'key = value' pair is parsed into 'object_node';
///         faults recover at the next line.
fn parse_entry(cursor: &mut Cursor, object_node: &mut ObjectNode, p: &mut Parse) {
    let key_position = cursor.position();
    let key = match parse_key(cursor, p) {
        Some(key) => key,
        None      => { cursor.skip_line(); return; }
    };
    if key == "include" {
        p.fault(EParseFault::Refused, key_position,
                "'include' does not exist here: a specification refers to nothing outside its file".to_string());
        cursor.skip_line();
        return;
    }
    skip_space(cursor);
    match cursor.peek(0) {
        Some('=') | Some(':') => { cursor.skip(1); skip_space(cursor); }
        Some('{') => {}                                     // a brace binds without a sign
        Some('+') if cursor.peek(1) == Some('=') => {
            p.fault(EParseFault::Refused, cursor.position(), "'+=' does not exist here".to_string());
            cursor.skip_line();
            return;
        }
        _ => {
            p.fault(EParseFault::Syntax, cursor.position(),
                    format!("expected '=', ':' or '{{' after key '{}'", key));
            cursor.skip_line();
            return;
        }
    }
    //  NO NODE: the value parser has recovered already; a second skip here
    //  would eat the NEXT line.
    let node = match parse_value(cursor, p, false) { Some(node) => node, None => return };
    if object_node.get(&key).is_some() {
        p.fault(EParseFault::Syntax, key_position,
                format!("duplicate key '{}'; the first stands, this one is refused", key));
        return;
    }
    object_node.entry_list.push(Entry { key, key_position, node });
}

/// RETURN: Some(key); None where no key stands here (fault recorded).
fn parse_key(cursor: &mut Cursor, p: &mut Parse) -> Option<String> {
    if cursor.peek(0) == Some('"') { return parse_quoted(cursor, p); }
    let text = cursor.token_at(cursor.i_col);
    if text.is_empty() {
        p.fault(EParseFault::Syntax, cursor.position(),
                format!("expected a key, found '{}'", stripped(cursor.peek(0))));
        return None;
    }
    cursor.skip(text.chars().count());
    Some(text)
}

/// RETURN: Some(Node), the value here; None where nothing usable stands
///         here (fault recorded). 'in_list_f' makes an empty value a fault
///         rather than null.
fn parse_value(cursor: &mut Cursor, p: &mut Parse, in_list_f: bool) -> Option<Node> {
    skip_space(cursor);
    let position = cursor.position();
    match cursor.peek(0) {
        Some('{') => {
            cursor.skip(1);
            Some(Node::Object(parse_body(cursor, Some('}'), p)))
        }
        Some('[') => {
            cursor.skip(1);
            Some(Node::List(parse_list(cursor, position, p)))
        }
        Some('"') if cursor.peek(1) == Some('"') && cursor.peek(2) == Some('"') => {
            parse_triple_quoted(cursor, p).map(|s| Node::Scalar(ScalarNode { value: Value::Str(s), position }))
        }
        Some('"') => {
            parse_quoted(cursor, p).map(|s| Node::Scalar(ScalarNode { value: Value::Str(s), position }))
        }
        Some('$') if cursor.peek(1) == Some('{') => {
            p.fault(EParseFault::Refused, position,
                    "substitutions '${...}' do not exist here: a specification refers to nothing outside its file"
                    .to_string());
            cursor.skip_line();
            None
        }
        _ => parse_bare(cursor, position, p, in_list_f),
    }
}

/// RETURN: ListNode, the items up to ']'.
fn parse_list(cursor: &mut Cursor, position: Position, p: &mut Parse) -> ListNode {
    let mut item_list = Vec::new();
    loop {
        skip_blank(cursor);
        if cursor.at_end() {
            p.fault(EParseFault::Syntax, cursor.position(), "unterminated list: ']' missing".to_string());
            break;
        }
        match cursor.peek(0) {
            Some(']') => { cursor.skip(1); break; }
            Some(',') => cursor.skip(1),
            Some('}') => {
                //  A BRACE CLOSES THE OBJECT AROUND THE LIST: said once, the
                //  brace left to its owner.
                p.fault(EParseFault::Syntax, cursor.position(), "unterminated list: ']' missing before '}'".to_string());
                break;
            }
            _ => {
                let before = (cursor.i_line, cursor.i_col);
                let item = parse_value(cursor, p, true);
                let none_f = item.is_none();
                if let Some(item) = item { item_list.push(item); }
                //  NO VALUE READ AND NOTHING CONSUMED: step over the character.
                if none_f && (cursor.i_line, cursor.i_col) == before { cursor.skip(1); }
            }
        }
    }
    ListNode { item_list, position }
}

/// RETURN: Some(text) between three double quotes and the next three, over
///         as many lines as it takes, AS WRITTEN (no escape resolved), laid
///         out by 'cleandoc'; None where no closing three quotes stand before
///         the text's end (fault recorded).
fn parse_triple_quoted(cursor: &mut Cursor, p: &mut Parse) -> Option<String> {
    let begin = cursor.position();
    cursor.skip(3);
    let mut piece_list: Vec<String> = Vec::new();
    while !cursor.at_end() {
        let text = cursor.text();
        let from = cursor.i_col.min(text.len());
        let found = (from..text.len().saturating_sub(2)).find(|&i| text[i] == '"' && text[i + 1] == '"' && text[i + 2] == '"');
        if let Some(end) = found {
            piece_list.push(text[from..end].iter().collect());
            cursor.i_col = end + 3;
            return Some(cleandoc(&piece_list.join("\n")));
        }
        piece_list.push(text[from..].iter().collect());
        cursor.skip_line();
    }
    p.fault(EParseFault::Syntax, begin,
            "unterminated triple-quoted string: closing '\"\"\"' missing".to_string());
    None
}

/// RETURN: Some(content) of the string at the cursor, escapes resolved
///         ('\n', '\t', '\"', '\\'; any other escaped character stands for
///         itself); None where it is unterminated at its line's end (fault
///         recorded).
fn parse_quoted(cursor: &mut Cursor, p: &mut Parse) -> Option<String> {
    let begin = cursor.position();
    let text: Vec<char> = cursor.text().to_vec();
    let mut i = cursor.i_col + 1;                           // past the opening quote
    //  THE COMMON CASE, no backslash: the closing quote is found.
    let mut k = i.min(text.len());
    while k < text.len() && text[k] != '"' && text[k] != '\\' && text[k] != '\n' { k += 1; }
    if k < text.len() && text[k] == '"' {
        cursor.i_col = k + 1;
        return Some(text[i.min(text.len())..k].iter().collect());
    }
    let mut piece = String::new();
    loop {
        if i >= text.len() {
            p.fault(EParseFault::Syntax, begin, "unterminated string".to_string());
            cursor.i_col = i;
            return None;
        }
        match text[i] {
            '"' => { cursor.i_col = i + 1; return Some(piece); }
            '\\' => {
                i += 1;
                match text.get(i) {
                    Some('n') => piece.push('\n'),
                    Some('t') => piece.push('\t'),
                    Some(c)   => piece.push(*c),
                    None      => {}
                }
                i += 1;
            }
            c => { piece.push(c); i += 1; }
        }
    }
}

/// RETURN: Some(ScalarNode) of the bare token here -- a boolean, a number,
///         a spelling of nothing, or null for an empty value; None where
///         the token is none of those (fault recorded): a string value is
///         written in double quotes.
fn parse_bare(cursor: &mut Cursor, position: Position, p: &mut Parse, in_list_f: bool) -> Option<Node> {
    let mut raw = cursor.token_at(cursor.i_col);
    //  A SIGN STANDING APART from its digits: '- 0.12'.
    if SIGN_SET.contains(&raw.as_str()) {
        let start = blank_end(cursor.text(), cursor.i_col + 1);
        let after = cursor.token_at(start);
        //  The two must make ONE number: '- -1.5e3' does not (python hwut_hocon).
        if !after.is_empty() && number(&after).is_some() {
            if let Some(value) = number(&format!("{}{}", raw, after)) {
                cursor.i_col = start + after.chars().count();
                return Some(Node::Scalar(ScalarNode { value, position }));
            }
        }
    }
    if raw.starts_with("${") {
        p.fault(EParseFault::Refused, cursor.position(), "substitutions '${...}' do not exist here".to_string());
        cursor.skip_line();
        return None;
    }
    if let Some(i) = raw.find("//") { raw.truncate(i); }
    cursor.skip(raw.chars().count());
    if raw.is_empty() {
        if in_list_f {
            p.fault(EParseFault::Syntax, position, format!("expected a value, found '{}'", stripped(cursor.peek(0))));
            return None;
        }
        return Some(Node::Scalar(ScalarNode { value: Value::Null, position }));   // an empty value is null
    }
    match interpret(&raw) {
        Some(value) => Some(Node::Scalar(ScalarNode { value, position })),
        None => {
            p.fault(EParseFault::Syntax, position, format!("a string is written in double quotes: \"{}\"", raw));
            None
        }
    }
}

/// RETURN: Some(Value), what the bare text says -- Null for the spellings
///         of nothing, a Bool, an Int or a Float; None where it is no bare
///         token at all (an unquoted string, which this language lacks).
fn interpret(raw: &str) -> Option<Value> {
    if NULL_SET.contains(&raw) { return Some(Value::Null); }
    match raw {
        "true" | "yes" => Some(Value::Bool(true)),
        "false" | "no" => Some(Value::Bool(false)),
        _              => number(raw),
    }
}

/// RETURN: Some(Value::Int | Value::Float), the number the text spells, in
///         whatever radix ('0x', '0b', '0o', '0r' roman, decimal); '_' is a
///         visual helper and enters no value. None where it spells none.
fn number(raw: &str) -> Option<Value> {
    let (body, sign): (&str, i128) = match raw.chars().next() {
        Some('+') => (&raw[1..], 1),
        Some('-') => (&raw[1..], -1),
        _         => (raw, 1),
    };
    let prefix: String = body.chars().take(2).collect();
    match prefix.as_str() {
        "0r" | "0R" => return roman(&body[2..]).map(|v| Value::Int(sign * v)),
        "0x" | "0X" | "0b" | "0B" | "0o" | "0O" => {
            let (radix, digit_set) = match &prefix[1..] {
                "x" | "X" => (16, "0123456789abcdefABCDEF"),
                "b" | "B" => (2, "01"),
                _         => (8, "01234567"),
            };
            let digit_text = without_helper(&body[2..], digit_set)?;
            let mut value: i128 = 0;
            for c in digit_text.chars() {
                value = value.wrapping_mul(radix).wrapping_add(c.to_digit(radix as u32).unwrap() as i128);
            }
            return Some(Value::Int(sign.wrapping_mul(value)));
        }
        _ => {}
    }
    if !decimal_f(raw) { return None; }
    let text: String = raw.chars().filter(|c| *c != '_').collect();
    if text.contains('.') || text.contains('e') || text.contains('E') {
        return Some(Value::Float(text.parse::<f64>().unwrap_or(f64::NAN)));
    }
    let (digits, negative_f) = match text.strip_prefix('-') {
        Some(rest) => (rest, true),
        None       => (text.strip_prefix('+').unwrap_or(&text), false),
    };
    let mut value: i128 = 0;
    for c in digits.chars() { value = value.wrapping_mul(10).wrapping_add(c.to_digit(10).unwrap() as i128); }
    Some(Value::Int(if negative_f { value.wrapping_neg() } else { value }))
}

/// RETURN: usize, the end of the digits '[0-9](_?[0-9])*' that begin at
///         'i' of 'c'; 'i' where none begins there.
fn digits_end(c: &[char], i: usize) -> usize {
    if i >= c.len() || !c[i].is_ascii_digit() { return i; }
    let mut k = i + 1;
    loop {
        if k < c.len() && c[k].is_ascii_digit() { k += 1; }
        else if k + 1 < c.len() && c[k] == '_' && c[k + 1].is_ascii_digit() { k += 2; }
        else { return k; }
    }
}

/// RETURN: bool, 'raw' is a decimal number whole:
///         [-+]? (D (\.D?)? | \.D) ([eE][-+]?D)?  with D = [0-9](_?[0-9])*
fn decimal_f(raw: &str) -> bool {
    let c: Vec<char> = raw.chars().collect();
    let mut i = 0;
    if i < c.len() && (c[i] == '+' || c[i] == '-') { i += 1; }
    let k = digits_end(&c, i);
    if k > i {
        i = k;
        if i < c.len() && c[i] == '.' { i = digits_end(&c, i + 1); }
    } else if i < c.len() && c[i] == '.' {
        let k = digits_end(&c, i + 1);
        if k == i + 1 { return false; }
        i = k;
    } else {
        return false;
    }
    if i < c.len() && (c[i] == 'e' || c[i] == 'E') {
        let mut j = i + 1;
        if j < c.len() && (c[j] == '+' || c[j] == '-') { j += 1; }
        let k = digits_end(&c, j);
        if k > j { i = k; }
    }
    i == c.len()
}

/// RETURN: Some(digits), 'text' with every '_' removed; None where it
///         carries no digit, a character that is no digit of this radix
///         ('digit_set'), or an '_' that separates nothing.
fn without_helper(text: &str, digit_set: &str) -> Option<String> {
    if text.is_empty() || text.starts_with('_') || text.ends_with('_') || text.contains("__") { return None; }
    let stripped: String = text.chars().filter(|c| *c != '_').collect();
    if stripped.is_empty() || stripped.chars().any(|c| !digit_set.contains(c)) { return None; }
    Some(stripped)
}

/// RETURN: &HashSet<String>, every text the strict roman form
///         'M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})' matches
///         whole -- 4000 texts, the empty one among them.
fn roman_set() -> &'static HashSet<String> {
    static SET: OnceLock<HashSet<String>> = OnceLock::new();
    SET.get_or_init(|| {
        let group = |one: &str, five: &str, ten: &str| -> Vec<String> {
            let mut result = vec![format!("{}{}", one, ten), format!("{}{}", one, five)];
            for d in ["", five] { for n in 0..4 { result.push(format!("{}{}", d, one.repeat(n))); } }
            result
        };
        let mut set = HashSet::new();
        for m in 0..4 {
            for c in group("C", "D", "M") {
                for x in group("X", "L", "C") {
                    for i in group("I", "V", "X") { set.insert(format!("{}{}{}{}", "M".repeat(m), c, x, i)); }
                }
            }
        }
        set
    })
}

/// RETURN: Some(number) the roman numeral spells; None where the text is no
///         roman numeral of the strict form ('IIII' and 'VX' among them).
fn roman(text: &str) -> Option<i128> {
    if text.is_empty() || !roman_set().contains(text) { return None; }
    let (mut total, mut previous) = (0i128, 0i128);
    for c in text.chars().rev() {
        let value = match c { 'I' => 1, 'V' => 5, 'X' => 10, 'L' => 50, 'C' => 100, 'D' => 500, _ => 1000 };
        total = if value < previous { total - value } else { total + value };
        previous = previous.max(value);
    }
    Some(total)
}

/// RETURN: usize, the index of the first character at or after 'i' that is
///         no blank (' ' or tab).
fn blank_end(text: &[char], mut i: usize) -> usize {
    while i < text.len() && (text[i] == ' ' || text[i] == '\t') { i += 1; }
    i
}

/// RETURN: nothing; blanks and a comment on the current line are skipped.
fn skip_space(cursor: &mut Cursor) {
    let text = cursor.text();
    let i = blank_end(text, cursor.i_col);
    let comment_f = i < text.len() && (text[i] == '#' || (text[i] == '/' && text.get(i + 1) == Some(&'/')));
    cursor.i_col = i;
    if comment_f { cursor.skip_line(); }
}

/// RETURN: nothing; blanks, line ends, commas and comments are skipped.
fn skip_blank(cursor: &mut Cursor) {
    while !cursor.at_end() {
        let text = cursor.text();
        let mut i = cursor.i_col;
        while i < text.len() && (text[i] == ' ' || text[i] == '\t' || text[i] == ',') { i += 1; }
        if i >= text.len() { cursor.skip_line(); continue; }
        let comment_f = text[i] == '#' || (text[i] == '/' && text.get(i + 1) == Some(&'/'));
        cursor.i_col = i;
        if comment_f { cursor.skip_line(); continue; }
        return;
    }
}

/// RETURN: String, 'text' laid out as Python 3.13's 'inspect.cleandoc': tabs
///         expanded (to 8), the blank indentation common to the lines after
///         the first removed, the first line's leading blanks removed, empty
///         lines at both ends dropped.
pub fn cleandoc(text: &str) -> String {
    let mut expanded = String::new();
    let mut column = 0;
    for c in text.chars() {
        match c {
            '\t' => { let n = 8 - column % 8; expanded.push_str(&" ".repeat(n)); column += n; }
            '\n' | '\r' => { expanded.push(c); column = 0; }
            _ => { expanded.push(c); column += 1; }
        }
    }
    let mut lines: Vec<Vec<char>> = expanded.split('\n').map(|l| l.chars().collect()).collect();
    let mut margin = usize::MAX;
    for line in lines.iter().skip(1) {
        let content = line.iter().skip_while(|c| **c == ' ').count();
        if content > 0 { margin = margin.min(line.len() - content); }
    }
    if let Some(first) = lines.first_mut() {
        let n = first.iter().take_while(|c| **c == ' ').count();
        first.drain(..n);
    }
    if margin < usize::MAX {
        for line in lines.iter_mut().skip(1) { let n = margin.min(line.len()); line.drain(..n); }
    }
    while lines.last().is_some_and(|l| l.is_empty()) { lines.pop(); }
    while lines.first().is_some_and(|l| l.is_empty()) { lines.remove(0); }
    lines.iter().map(|l| l.iter().collect::<String>()).collect::<Vec<_>>().join("\n")
}
