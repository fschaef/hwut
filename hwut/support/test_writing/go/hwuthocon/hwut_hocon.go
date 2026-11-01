// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// Package hwuthocon parses THE HOCON SUBSET of the specification language
// into the ANNOTATED TREE -- the port of 'python/hwut_hocon.py'
// (README-hwut_hocon.txt): every key, every value and every block carries
// its file-relative position.
//
//	document, faultList := hwuthocon.Parse([]hwuthocon.SourceLine{
//	    {Text: "a = 1", Line: 1}, {Text: `b = "x"`, Line: 2}}, "f.hocon")
//	entry := document.Get("a")          // entry.Node.(*hwuthocon.ScalarNode).Value == int64(1)
//
// THE SUBSET: nested objects, lists, numbers (every radix, '_' between
// digits), booleans (true/false/yes/no), the spellings of nothing, '#' and
// '//' comments, '=' or ':' before a value, a brace directly after a key. A
// STRING VALUE IS WRITTEN IN DOUBLE QUOTES; a text of several lines in
// triple quotes. Refused by name: 'include', '${...}', '+='.
//
// The parser accumulates faults and recovers at the next line; it never
// fails otherwise. The tree, the faults and their words are Python's.
//
// WHERE GO DIFFERS FROM PYTHON:
//
//	a value             'ScalarNode.Value' is nil (None), bool, int64 -- a
//	                    *big.Int where the number is beyond int64, as
//	                    Python's int has no bound -- float64 or string
//	a column            counts CHARACTERS (runes), as Python's str does
//	Python's '\s'       is Unicode's white space: 'pytext.IsSpace'
//
// _____________________________________________________________________________
package hwuthocon

import (
	"fmt"
	"math"
	"math/big"
	"regexp"
	"strconv"
	"strings"

	"hwut/test_writing_support/go/pytext"
)

// EParseFault is the kind of a fault.
type EParseFault int

const (
	SYNTAX  EParseFault = iota + 1 // the text does not parse
	REFUSED                        // a construct that does not exist here, by name
)

// String
//
// RETURN: string, the kind's name -- 'SYNTAX' or 'REFUSED'.
func (self EParseFault) String() string {
	if self == REFUSED {
		return "REFUSED"
	}
	return "SYNTAX"
}

// Position is one place in one file; 1-based, as an editor counts.
type Position struct {
	Line   int
	Column int
}

// String
//
// RETURN: string, 'line:column'.
func (self Position) String() string { return fmt.Sprintf("%d:%d", self.Line, self.Column) }

// ParseFault is one fault of the parse, where it stands and what it is.
type ParseFault struct {
	Kind     EParseFault
	File     string
	Position Position
	Message  string
}

// String
//
// RETURN: string, 'file:line:column: KIND: message'.
func (self ParseFault) String() string {
	return fmt.Sprintf("%s:%s: %s: %s", self.File, self.Position, self.Kind, self.Message)
}

// SourceLine is one line as the parser reads it, tied to where it stands on
// disk; 'ColumnOffset' counts what was removed before 'Text' begins.
type SourceLine struct {
	Text         string
	Line         int
	ColumnOffset int
}

// Node is a ScalarNode, a ListNode or an ObjectNode.
type Node interface {
	NodePosition() Position
}

// ScalarNode is one scalar value: nil, bool, int64 (*big.Int), float64 or
// string.
type ScalarNode struct {
	Value    any
	Position Position
}

// ListNode is one list of nodes.
type ListNode struct {
	ItemList []Node
	Position Position
}

// Entry is one key with its value inside an object.
type Entry struct {
	Key         string
	KeyPosition Position
	Node        Node
}

// ObjectNode is one object: ordered entries, duplicate keys refused at parse.
type ObjectNode struct {
	Position  Position
	EntryList []*Entry
}

// NodePosition
//
// RETURN: Position, where the scalar begins.
func (self *ScalarNode) NodePosition() Position { return self.Position }

// NodePosition
//
// RETURN: Position, where the list's '[' stands.
func (self *ListNode) NodePosition() Position { return self.Position }

// NodePosition
//
// RETURN: Position, where the object begins.
func (self *ObjectNode) NodePosition() Position { return self.Position }

// Get
//
// RETURN: *Entry, the entry named 'key'; nil, where there is no such entry.
func (self *ObjectNode) Get(key string) *Entry {
	for _, entry := range self.EntryList {
		if entry.Key == key {
			return entry
		}
	}
	return nil
}

// Keys
//
// RETURN: []string, the keys in written order.
func (self *ObjectNode) Keys() []string {
	result := make([]string, len(self.EntryList))
	for i, entry := range self.EntryList {
		result[i] = entry.Key
	}
	return result
}

// notAToken is returned where a bare token is none of a boolean, a number
// or a spelling of nothing: an unquoted string. It is a value of its own.
type notATokenType struct{}

var notAToken = notATokenType{}

// String
//
// RETURN: string, how the marker prints where a value carries it.
func (notATokenType) String() string { return "<object object>" }

var boolDb = map[string]bool{"true": true, "yes": true, "false": false, "no": false}

// THE SPELLINGS OF NOTHING: a key bound to one carries the NULL value.
var nullSet = map[string]bool{"null": true, "nil": true, "none": true, "nihil": true}

var decimalRe = regexp.MustCompile(`^[-+]?(?:[0-9](?:_?[0-9])*(?:\.(?:[0-9](?:_?[0-9])*)?)?|\.[0-9](?:_?[0-9])*)(?:[eE][-+]?[0-9](?:_?[0-9])*)?$`)

var radixDb = map[string]int{"0x": 16, "0X": 16, "0b": 2, "0B": 2, "0o": 8, "0O": 8}
var radixDigitDb = map[int]string{16: "0123456789abcdefABCDEF", 2: "01", 8: "01234567"}

var romanRe = regexp.MustCompile(`^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$`)
var romanValueDb = map[rune]int{'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}

var escapeDb = map[rune]rune{'n': '\n', 't': '\t', '"': '"', '\\': '\\'}

// ------------------------------------------------------------------ cursor

// endRune is what 'peek' answers beyond the last line -- Python's ”.
const endRune rune = -1

// cursor walks a list of SourceLines character by character; every
// position it reports is file-relative through the lines' offsets.
type cursor struct {
	lineList []SourceLine
	lineN    int
	iLine    int
	iCol     int
	text     []rune // the current line's characters
}

// newCursor
//
// RETURN: *cursor, at the first character of 'lineList'.
func newCursor(lineList []SourceLine) *cursor {
	self := &cursor{lineList: lineList, lineN: len(lineList)}
	if len(lineList) != 0 {
		self.text = []rune(lineList[0].Text)
	}
	return self
}

// atEnd
//
// RETURN: bool, true where no character remains.
func (self *cursor) atEnd() bool { return self.iLine >= self.lineN }

// peek
//
// RETURN: rune, the character 'ahead' places from here on this line; '\n'
// at this line's end; endRune beyond the last line.
func (self *cursor) peek(ahead int) rune {
	if self.iLine >= self.lineN {
		return endRune
	}
	if i := self.iCol + ahead; i < len(self.text) {
		return self.text[i]
	}
	return '\n'
}

// peekText
//
// RETURN: string, 'peek(0)' stripped as Python's 'str.strip' strips -- ”
// at a line's end and beyond the last line.
func (self *cursor) peekText() string {
	c := self.peek(0)
	if c == endRune {
		return ""
	}
	return pytext.Strip(string(c))
}

// skip
//
// RETURN: nothing; 'n' characters WITHIN the current line are stepped over.
func (self *cursor) skip(n int) { self.iCol += n }

// skipLine
//
// RETURN: nothing; the cursor stands at the beginning of the next line.
func (self *cursor) skipLine() {
	self.iLine++
	self.iCol = 0
	self.text = nil
	if self.iLine < self.lineN {
		self.text = []rune(self.lineList[self.iLine].Text)
	}
}

// position
//
// RETURN: Position, file-relative, of the character at the cursor -- beyond
// the last line, one past that line's end; (1, 1) for no line at all.
func (self *cursor) position() Position {
	if self.iLine >= self.lineN {
		if self.lineN == 0 {
			return Position{1, 1}
		}
		last := self.lineList[self.lineN-1]
		return Position{last.Line, last.ColumnOffset + len([]rune(last.Text)) + 1}
	}
	line := self.lineList[self.iLine]
	return Position{line.Line, line.ColumnOffset + self.iCol + 1}
}

// tokenAt
//
// RETURN: []rune, the TOKEN beginning at 'i' of 'text' -- a key, or a bare
// value: the run up to the first blank or character that binds, opens,
// closes or separates ('{}[]=,:"#'); empty where one stands at 'i'.
func tokenAt(text []rune, i int) []rune {
	j := i
	for j < len(text) && !pytext.IsSpace(text[j]) && !strings.ContainsRune(`{}[]=,:"#`, text[j]) {
		j++
	}
	if i > len(text) {
		return nil
	}
	return text[i:j]
}

// blankEnd
//
// RETURN: int, the index of the first character at or after 'i' of 'text'
// that is no blank (' ', '\t').
func blankEnd(text []rune, i int) int {
	for i < len(text) && (text[i] == ' ' || text[i] == '\t') {
		i++
	}
	return i
}

// hasPrefixAt
//
// RETURN: bool, true where 'text' holds 'prefix' from index 'i' on.
func hasPrefixAt(text []rune, i int, prefix string) bool {
	for k, c := range []rune(prefix) {
		if i+k >= len(text) || text[i+k] != c {
			return false
		}
	}
	return true
}

// ------------------------------------------------------------------- parse

// parser holds one parse's file name and faults.
type parser struct {
	file      string
	faultList []ParseFault
}

// fault
//
// RETURN: nothing; the fault of 'kind' at 'position' saying 'message' was
// recorded.
func (self *parser) fault(kind EParseFault, position Position, message string) {
	self.faultList = append(self.faultList, ParseFault{kind, self.file, position, message})
}

// Parse
//
// RETURN: (*ObjectNode, []ParseFault), the document -- every entry of the
// outermost level, possibly none -- and every fault found, none on a clean
// parse. 'lineList' are the lines, 'file' names the file for faults.
func Parse(lineList []SourceLine, file string) (*ObjectNode, []ParseFault) {
	p := &parser{file: file}
	c := newCursor(lineList)
	document := p.parseBody(c, 0)
	return document, p.faultList
}

// parseBody
//
// RETURN: *ObjectNode, the entries up to 'terminator' ('}', or 0 for the
// end of the text).
func (self *parser) parseBody(c *cursor, terminator rune) *ObjectNode {
	result := &ObjectNode{Position: c.position()}
	for {
		skipBlank(c)
		if c.atEnd() {
			if terminator != 0 {
				self.fault(SYNTAX, c.position(), fmt.Sprintf("unterminated object: '%c' missing", terminator))
			}
			return result
		}
		switch ch := c.peek(0); {
		case terminator != 0 && ch == terminator:
			c.skip(1)
			return result
		case ch == '}':
			self.fault(SYNTAX, c.position(), "unmatched '}'")
			c.skip(1)
		default:
			self.parseEntry(c, result)
		}
	}
}

// parseEntry
//
// RETURN: nothing; one 'key = value' pair was parsed into 'objectNode';
// faults recover at the next line.
func (self *parser) parseEntry(c *cursor, objectNode *ObjectNode) {
	keyPosition := c.position()
	key, found := self.parseKey(c)
	if !found {
		c.skipLine()
		return
	}
	if key == "include" {
		self.fault(REFUSED, keyPosition, "'include' does not exist here: a specification refers to nothing outside its file")
		c.skipLine()
		return
	}
	skipSpace(c)
	switch ch := c.peek(0); {
	case ch == '=' || ch == ':':
		c.skip(1)
		skipSpace(c)
	case ch == '{':
		// a brace binds without a sign
	case ch == '+' && c.peek(1) == '=':
		self.fault(REFUSED, c.position(), "'+=' does not exist here")
		c.skipLine()
		return
	default:
		self.fault(SYNTAX, c.position(), fmt.Sprintf("expected '=', ':' or '{' after key '%s'", key))
		c.skipLine()
		return
	}
	node := self.parseValue(c, false)
	if node == nil {
		//  The value parser has recovered already (line skipped or cursor
		//  at the fault); a second skip here would eat the NEXT line.
		return
	}
	if objectNode.Get(key) != nil {
		self.fault(SYNTAX, keyPosition, fmt.Sprintf("duplicate key '%s'; the first stands, this one is refused", key))
		return
	}
	objectNode.EntryList = append(objectNode.EntryList, &Entry{key, keyPosition, node})
}

// parseKey
//
// RETURN: (string, true), the key; ("", false), no key stands here (fault
// recorded).
func (self *parser) parseKey(c *cursor) (string, bool) {
	if c.peek(0) == '"' {
		return self.parseQuoted(c)
	}
	text := tokenAt(c.text, c.iCol)
	if len(text) == 0 {
		self.fault(SYNTAX, c.position(), fmt.Sprintf("expected a key, found '%s'", c.peekText()))
		return "", false
	}
	c.skip(len(text))
	return string(text), true
}

// parseValue
//
// RETURN: Node, the value here -- *ScalarNode, *ListNode or *ObjectNode;
// nil, nothing usable stands here (fault recorded). 'inListF' says an
// empty value is a fault rather than null.
func (self *parser) parseValue(c *cursor, inListF bool) Node {
	skipSpace(c)
	position := c.position()
	switch ch := c.peek(0); {
	case ch == '{':
		c.skip(1)
		return self.parseBody(c, '}')
	case ch == '[':
		c.skip(1)
		return self.parseList(c, position)
	case ch == '"' && c.peek(1) == '"' && c.peek(2) == '"':
		if value, found := self.parseTripleQuoted(c); found {
			return &ScalarNode{value, position}
		}
		return nil
	case ch == '"':
		if value, found := self.parseQuoted(c); found {
			return &ScalarNode{value, position}
		}
		return nil
	case ch == '$' && c.peek(1) == '{':
		self.fault(REFUSED, position, "substitutions '${...}' do not exist here: a specification refers to nothing outside its file")
		c.skipLine()
		return nil
	}
	if node := self.parseBare(c, position, inListF); node != nil {
		return node
	}
	return nil
}

// parseList
//
// RETURN: *ListNode, the items up to ']'.
func (self *parser) parseList(c *cursor, position Position) *ListNode {
	itemList := []Node{}
	for {
		skipBlank(c)
		if c.atEnd() {
			self.fault(SYNTAX, c.position(), "unterminated list: ']' missing")
			break
		}
		ch := c.peek(0)
		if ch == ']' {
			c.skip(1)
			break
		} else if ch == ',' {
			c.skip(1)
			continue
		} else if ch == '}' {
			//  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' was
			//  forgotten. Said once, and the brace left to its owner.
			self.fault(SYNTAX, c.position(), "unterminated list: ']' missing before '}'")
			break
		}
		beforeLine, beforeCol := c.iLine, c.iCol
		item := self.parseValue(c, true)
		if item != nil {
			itemList = append(itemList, item)
		} else if c.iLine == beforeLine && c.iCol == beforeCol {
			//  NO VALUE READ AND NOTHING CONSUMED: step over the character
			//  the value refused, or the loop never ends.
			c.skip(1)
		}
	}
	return &ListNode{itemList, position}
}

// parseTripleQuoted
//
// RETURN: (string, true), the text between three double quotes and the next
// three, over as many lines as it takes, AS WRITTEN (no escape resolved),
// then laid out as a docstring is ('Cleandoc'); ("", false), no closing
// three quotes stand before the text's end (fault recorded).
func (self *parser) parseTripleQuoted(c *cursor) (string, bool) {
	begin := c.position()
	c.skip(3)
	var pieceList []string
	for !c.atEnd() {
		text := c.text
		end := -1
		for i := c.iCol; i+2 < len(text); i++ {
			if text[i] == '"' && text[i+1] == '"' && text[i+2] == '"' {
				end = i
				break
			}
		}
		if end >= 0 {
			pieceList = append(pieceList, string(text[c.iCol:end]))
			c.iCol = end + 3
			return Cleandoc(strings.Join(pieceList, "\n")), true
		}
		if c.iCol < len(text) {
			pieceList = append(pieceList, string(text[c.iCol:]))
		} else {
			pieceList = append(pieceList, "")
		}
		c.skipLine()
	}
	self.fault(SYNTAX, begin, "unterminated triple-quoted string: closing '\"\"\"' missing")
	return "", false
}

// parseQuoted
//
// RETURN: (string, true), the string's content, escapes resolved;
// ("", false), the string is unterminated at its line's end (fault
// recorded).
func (self *parser) parseQuoted(c *cursor) (string, bool) {
	begin := c.position()
	text := c.text
	i := c.iCol + 1 // past the opening quote
	//  THE COMMON CASE -- no backslash -- is taken in one step.
	j := i
	for j < len(text) && text[j] != '"' && text[j] != '\\' && text[j] != '\n' {
		j++
	}
	if j < len(text) && text[j] == '"' {
		c.iCol = j + 1
		return string(text[i:j]), true
	}
	var piece strings.Builder
	for {
		if i >= len(text) {
			self.fault(SYNTAX, begin, "unterminated string")
			c.iCol = i
			return "", false
		}
		switch ch := text[i]; ch {
		case '"':
			c.iCol = i + 1
			return piece.String(), true
		case '\\':
			i++
			if i < len(text) {
				escaped := text[i]
				if resolved, found := escapeDb[escaped]; found {
					escaped = resolved
				}
				piece.WriteRune(escaped)
			}
			i++
		default:
			piece.WriteRune(ch)
			i++
		}
	}
}

// parseBare
//
// RETURN: *ScalarNode, the bare token here: a boolean, a number, or a
// spelling of nothing -- nothing at all, outside a list, is null; nil, the
// token is none of those (fault recorded): a string value is written in
// double quotes.
func (self *parser) parseBare(c *cursor, position Position, inListF bool) *ScalarNode {
	raw := string(tokenAt(c.text, c.iCol))
	//  A SIGN STANDING APART from its digits: '- 0.12'.
	if raw == "+" || raw == "-" {
		text := c.text
		after := string(tokenAt(text, blankEnd(text, c.iCol+1)))
		//  The two must make ONE number: '- -1.5e3' does not (python hwut_hocon).
		if after != "" && number(after) != notAToken && number(raw+after) != notAToken {
			c.iCol = blankEnd(text, c.iCol+1) + len([]rune(after))
			return &ScalarNode{number(raw + after), position}
		}
	}
	if strings.HasPrefix(raw, "${") {
		self.fault(REFUSED, c.position(), "substitutions '${...}' do not exist here")
		c.skipLine()
		return nil
	}
	if i := strings.Index(raw, "//"); i != -1 {
		raw = raw[:i]
	}
	c.skip(len([]rune(raw)))
	if raw == "" {
		if inListF {
			self.fault(SYNTAX, position, fmt.Sprintf("expected a value, found '%s'", c.peekText()))
			return nil
		}
		return &ScalarNode{nil, position} // an empty value is null
	}
	value := interpret(raw)
	if value == notAToken {
		self.fault(SYNTAX, position, fmt.Sprintf("a string is written in double quotes: \"%s\"", raw))
		return nil
	}
	return &ScalarNode{value, position}
}

// interpret
//
// RETURN: any, what the bare text says -- nil for the spellings of
// nothing, a bool, a number; notAToken where it is no bare token at all
// (an unquoted string, and this language has none).
func interpret(raw string) any {
	if nullSet[raw] {
		return nil
	}
	if value, found := boolDb[raw]; found {
		return value
	}
	return number(raw)
}

// integer
//
// RETURN: any, 'value' as an int64 where it fits, the *big.Int else.
func integer(value *big.Int) any {
	if value.IsInt64() {
		return value.Int64()
	}
	return value
}

// number
//
// RETURN: any, the number the text spells -- int64 (*big.Int beyond it) or
// float64 -- in whatever radix it spells it; '_' is a visual helper and
// enters no value. notAToken, the text spells no number.
func number(raw string) any {
	body, sign := raw, int64(1)
	if strings.HasPrefix(raw, "+") || strings.HasPrefix(raw, "-") {
		body = raw[1:]
	}
	if strings.HasPrefix(raw, "-") {
		sign = -1
	}
	prefix := body
	if len(prefix) > 2 {
		prefix = body[:2]
	}
	if prefix == "0r" || prefix == "0R" {
		value, found := roman(body[2:])
		if !found {
			return notAToken // a refusal is a refusal: it must not be signed
		}
		return sign * int64(value)
	}
	if radix, found := radixDb[prefix]; found {
		digitText, ok := withoutHelper(body[2:], radixDigitDb[radix])
		if !ok {
			return notAToken
		}
		value, _ := new(big.Int).SetString(digitText, radix)
		return integer(value.Mul(value, big.NewInt(sign)))
	}
	if !decimalRe.MatchString(raw) {
		return notAToken
	}
	text := strings.ReplaceAll(raw, "_", "")
	if strings.ContainsAny(text, ".eE") {
		//  OUT OF RANGE IS NO FAULT: Python's 'float' gives inf, or 0.0.
		value, _ := strconv.ParseFloat(text, 64)
		return value
	}
	value, _ := new(big.Int).SetString(text, 10)
	return integer(value)
}

// withoutHelper
//
// RETURN: (string, true), 'text' with every '_' removed; ("", false), the
// text carries no digit, a character that is no digit of 'digitSet', or an
// '_' that separates nothing.
func withoutHelper(text, digitSet string) (string, bool) {
	if text == "" || text[0] == '_' || text[len(text)-1] == '_' || strings.Contains(text, "__") {
		return "", false
	}
	stripped := strings.ReplaceAll(text, "_", "")
	if stripped == "" {
		return "", false
	}
	for _, c := range stripped {
		if !strings.ContainsRune(digitSet, c) {
			return "", false
		}
	}
	return stripped, true
}

// roman
//
// RETURN: (int, true), the number the roman numeral 'text' spells; (0,
// false), the text is no roman numeral -- 'IIII' and 'VX' among them: the
// form is the strict one.
func roman(text string) (int, bool) {
	if text == "" || !romanRe.MatchString(text) {
		return 0, false
	}
	total, previous := 0, 0
	character := []rune(text)
	for i := len(character) - 1; i >= 0; i-- {
		value := romanValueDb[character[i]]
		if value < previous {
			total -= value
		} else {
			total += value
		}
		previous = max(previous, value)
	}
	return total, true
}

// skipSpace
//
// RETURN: nothing; blanks and a comment on the current line were skipped.
func skipSpace(c *cursor) {
	text := c.text
	i := blankEnd(text, c.iCol)
	c.iCol = i
	if i < len(text) && (text[i] == '#' || hasPrefixAt(text, i, "//")) {
		c.skipLine()
	}
}

// skipBlank
//
// RETURN: nothing; blanks, line ends, commas and comments were skipped.
func skipBlank(c *cursor) {
	for c.iLine < c.lineN {
		text := c.text
		i := c.iCol
		for i < len(text) && (text[i] == ' ' || text[i] == '\t' || text[i] == ',') {
			i++
		}
		if i >= len(text) {
			c.skipLine()
			continue
		}
		c.iCol = i
		if text[i] == '#' || hasPrefixAt(text, i, "//") {
			c.skipLine()
			continue
		}
		return
	}
}

// Cleandoc
//
// RETURN: string, 'doc' laid out as Python's 'inspect.cleandoc' lays out a
// docstring: tabs expanded (8), the indentation common to the lines after
// the first removed, the first line's leading blanks removed, blank lines
// at the beginning and the end dropped.
func Cleandoc(doc string) string {
	lineList := strings.Split(expandTabs(doc), "\n")
	margin := math.MaxInt
	for _, line := range lineList[1:] {
		if content := len([]rune(strings.TrimLeft(line, " "))); content != 0 {
			margin = min(margin, len([]rune(line))-content)
		}
	}
	lineList[0] = strings.TrimLeft(lineList[0], " ")
	if margin < math.MaxInt {
		for i := 1; i < len(lineList); i++ {
			line := []rune(lineList[i])
			lineList[i] = string(line[min(margin, len(line)):])
		}
	}
	for len(lineList) != 0 && lineList[len(lineList)-1] == "" {
		lineList = lineList[:len(lineList)-1]
	}
	for len(lineList) != 0 && lineList[0] == "" {
		lineList = lineList[1:]
	}
	return strings.Join(lineList, "\n")
}

// expandTabs
//
// RETURN: string, 'text' with every tab replaced by the blanks up to the
// next column that is a multiple of 8 -- the column counted from the last
// '\n' or '\r', as Python's 'str.expandtabs()'.
func expandTabs(text string) string {
	var out strings.Builder
	column := 0
	for _, c := range text {
		switch c {
		case '\t':
			n := 8 - column%8
			out.WriteString(strings.Repeat(" ", n))
			column += n
		case '\n', '\r':
			out.WriteRune(c)
			column = 0
		default:
			out.WriteRune(c)
			column++
		}
	}
	return out.String()
}
