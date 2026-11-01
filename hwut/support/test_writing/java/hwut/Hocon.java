/* SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE, PARSED INTO THE
 *          ANNOTATED TREE -- the port of 'python/hwut_hocon.py'
 *          (README-hwut_hocon.txt): every key, every value and every block
 *          carries its file-relative position.
 *
 *     Hocon.Result r = Hocon.parse(List.of(new Hocon.SourceLine("a = 1", 1, 0)), "f.hocon");
 *     r.document()     the outermost object, entries in written order
 *     r.faultList()    every fault; empty on a clean parse -- it NEVER throws
 *
 * THE SUBSET: nested objects, lists, numbers in every radix ('0x', '0b',
 * '0o', '0r' roman; '_' between digits), booleans (true/false/yes/no), the
 * spellings of nothing (null, nil, none, nihil; an empty value), '#' and '//'
 * comments, '=' or ':' before a value, a brace directly after a key. A STRING
 * VALUE IS WRITTEN IN DOUBLE QUOTES; a text of several lines in triple quotes,
 * as written, laid out as a docstring ('inspect.cleandoc'). 'include',
 * '${...}' and '+=' are refused by name.
 *
 * A SCALAR'S VALUE is what Python's would be: String, Boolean, Long (an
 * integer beyond 64 bits: BigInteger), Double, or null. 'PyText.repr' and
 * 'PyText.typeName' print it as Python prints it. A column counts CHARACTERS
 * (code points), as Python's does.
 * _____________________________________________________________________________
 */
package hwut;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class Hocon {
    private Hocon() {}

    /** WHAT A FAULT IS -- Python's 'E_ParseFault'. */
    public enum FaultKind {
        SYNTAX,     // the text does not parse
        REFUSED     // a construct that does not exist here, by name
    }

    /** One place in one file; 1-based, as an editor counts. */
    public record Position(int line, int column) {
        /** RETURN: String, 'line:column'. */
        @Override public String toString() { return line + ":" + column; }
    }

    /** One fault of the parse, where it stands and what it is. */
    public record ParseFault(FaultKind kind, String file, Position position, String message) {
        /** RETURN: String, 'file:line:column: KIND: message'. */
        @Override public String toString() { return file + ":" + position + ": " + kind.name() + ": " + message; }
    }

    /** One line as the parser reads it, tied to where it stands on disk;
     *  'columnOffset' counts what was removed before 'text' begins. */
    public record SourceLine(String text, int line, int columnOffset) {}

    /** A node of the annotated tree: scalar, list or object. */
    public sealed interface Node permits ScalarNode, ListNode, ObjectNode {
        /** RETURN: Position, where the node begins. */
        Position position();
    }

    /** One scalar value: String, Boolean, Long or BigInteger, Double, null. */
    public record ScalarNode(Object value, Position position) implements Node {}

    /** One list of nodes. */
    public record ListNode(List<Node> itemList, Position position) implements Node {}

    /** One key with its value inside an object. */
    public record Entry(String key, Position keyPosition, Node node) {}

    /** One object: ordered entries, duplicate keys refused at parse. */
    public static final class ObjectNode implements Node {
        private final Position    position;
        private final List<Entry> entryList = new ArrayList<>();

        /** RETURN: ObjectNode at 'position', without entries. */
        public ObjectNode(Position position) { this.position = position; }

        /** RETURN: Position, where the object begins. */
        @Override public Position position() { return position; }

        /** RETURN: List of Entry, the entries in written order; unmodifiable. */
        public List<Entry> entryList() { return Collections.unmodifiableList(entryList); }

        /** RETURN: Entry, the entry named 'key'; null where there is none. */
        public Entry get(String key) {
            for (Entry entry : entryList) if (entry.key().equals(key)) return entry;
            return null;
        }

        /** RETURN: List of String, the keys in written order. */
        public List<String> keys() {
            List<String> result = new ArrayList<>();
            for (Entry entry : entryList) result.add(entry.key());
            return result;
        }
    }

    /** What 'parse' returns: the document and every fault. */
    public record Result(ObjectNode document, List<ParseFault> faultList) {}

    private static final Map<String, Boolean> BOOL_DB  = Map.of("true", true, "yes", true, "false", false, "no", false);
    private static final Set<String>          NULL_SET = Set.of("null", "nil", "none", "nihil");

    private static final Pattern DECIMAL_RE = Pattern.compile(
        "[-+]?(?:[0-9](?:_?[0-9])*(?:\\.(?:[0-9](?:_?[0-9])*)?)?|\\.[0-9](?:_?[0-9])*)(?:[eE][-+]?[0-9](?:_?[0-9])*)?");
    private static final Pattern ROMAN_RE   = Pattern.compile("M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})");
    //  A TOKEN -- a key, or a bare value -- runs to the first character that
    //  binds, opens, closes or separates; blanks end it too.
    private static final Pattern TOKEN_RE   = Pattern.compile("[^\\s{}\\[\\]=,:\"#]*", Pattern.UNICODE_CHARACTER_CLASS);
    private static final Pattern QUOTED_PLAIN_RE = Pattern.compile("([^\"\\\\\\n]*)\"");

    //  Returned where a bare token is none of the known forms.
    private static final Object NOT_A_TOKEN = new Object() {
        @Override public String toString() { return "<not a token>"; }
    };

    private static final String TRIPLE_QUOTE = "\"\"\"";

    /** Walks the SourceLines character by character; every position it
     *  reports is file-relative through the lines' offsets. */
    private static final class Cursor {
        final List<SourceLine> lineList;
        final int              lineN;
        int                    iLine, iCol;
        String                 text;

        Cursor(List<SourceLine> lineList) {
            this.lineList = lineList;
            this.lineN    = lineList.size();
            this.text     = lineList.isEmpty() ? "" : lineList.get(0).text();
        }

        /** RETURN: boolean, true where no character remains. */
        boolean atEnd() { return iLine >= lineN; }

        /** RETURN: String, the character 'ahead' places from here on this
         *          line; "\n" at this line's end; "" beyond the last line. */
        String peek(int ahead) {
            if (iLine >= lineN) return "";
            int i = iCol + ahead;
            return i < text.length() ? String.valueOf(text.charAt(i)) : "\n";
        }

        /** RETURN: String, 'peek(0)'. */
        String peek() { return peek(0); }

        /** RETURN: String, the whole character (code point) here, as a fault
         *          message shows it; "\n" at the line's end, "" at the end. */
        String peekCharacter() {
            if (iLine >= lineN) return "";
            return iCol < text.length() ? new String(Character.toChars(text.codePointAt(iCol))) : "\n";
        }

        /** RETURN: nothing; 'n' characters skipped WITHIN the current line. */
        void skip(int n) { iCol += n; }

        /** RETURN: nothing; the cursor stands at the next line's beginning. */
        void skipLine() {
            iLine += 1;
            iCol   = 0;
            text   = iLine < lineN ? lineList.get(iLine).text() : "";
        }

        /** RETURN: Position, file-relative, of the character at the cursor;
         *          past the last line, the place behind its last character. */
        Position position() {
            if (iLine >= lineN) {
                if (lineList.isEmpty()) return new Position(1, 1);
                SourceLine last = lineList.get(lineN - 1);
                return new Position(last.line(), last.columnOffset() + last.text().codePointCount(0, last.text().length()) + 1);
            }
            SourceLine line = lineList.get(iLine);
            return new Position(line.line(), line.columnOffset() + text.codePointCount(0, iCol) + 1);
        }
    }

    /** RETURN: Result -- [0] the document, every entry of the outermost
     *          level, possibly none; [1] every fault found, empty on a clean
     *          parse. Never throws on any text. 'file' names the file for
     *          faults. */
    public static Result parse(List<SourceLine> lineList, String file) {
        List<ParseFault> faultList = new ArrayList<>();
        Cursor           cursor    = new Cursor(lineList);
        ObjectNode       document  = parseBody(cursor, null, file, faultList);
        return new Result(document, faultList);
    }

    /** RETURN: ObjectNode, the entries up to 'terminator' ("}", or null for
     *          the end of the text). */
    private static ObjectNode parseBody(Cursor cursor, String terminator, String file, List<ParseFault> faultList) {
        ObjectNode result = new ObjectNode(cursor.position());
        while (true) {
            skipBlank(cursor);
            if (cursor.atEnd()) {
                if (terminator != null)
                    faultList.add(new ParseFault(FaultKind.SYNTAX, file, cursor.position(),
                                                 "unterminated object: '" + terminator + "' missing"));
                return result;
            }
            String c = cursor.peek();
            if (c.equals(terminator)) {
                cursor.skip(1);
                return result;
            } else if (c.equals("}")) {
                faultList.add(new ParseFault(FaultKind.SYNTAX, file, cursor.position(), "unmatched '}'"));
                cursor.skip(1);
            } else {
                parseEntry(cursor, result, file, faultList);
            }
        }
    }

    /** RETURN: nothing; one 'key = value' pair parsed into 'objectNode';
     *          faults recover at the next line. */
    private static void parseEntry(Cursor cursor, ObjectNode objectNode, String file, List<ParseFault> faultList) {
        Position keyPosition = cursor.position();
        String   key         = parseKey(cursor, file, faultList);
        if (key == null) {
            cursor.skipLine();
            return;
        }
        if (key.equals("include")) {
            faultList.add(new ParseFault(FaultKind.REFUSED, file, keyPosition,
                                         "'include' does not exist here: a specification refers to nothing outside its file"));
            cursor.skipLine();
            return;
        }
        skipSpace(cursor);
        String c = cursor.peek();
        if (c.equals("=") || c.equals(":")) {
            cursor.skip(1);
            skipSpace(cursor);
        } else if (c.equals("{")) {
            // a brace binds without a sign
        } else if (c.equals("+") && cursor.peek(1).equals("=")) {
            faultList.add(new ParseFault(FaultKind.REFUSED, file, cursor.position(), "'+=' does not exist here"));
            cursor.skipLine();
            return;
        } else {
            faultList.add(new ParseFault(FaultKind.SYNTAX, file, cursor.position(),
                                         "expected '=', ':' or '{' after key '" + key + "'"));
            cursor.skipLine();
            return;
        }
        Node node = parseValue(cursor, file, faultList, false);
        //  The value parser has recovered already (line skipped or cursor at
        //  the fault); a second skip here would eat the NEXT line.
        if (node == null) return;
        if (objectNode.get(key) != null) {
            faultList.add(new ParseFault(FaultKind.SYNTAX, file, keyPosition,
                                         "duplicate key '" + key + "'; the first stands, this one is refused"));
            return;
        }
        objectNode.entryList.add(new Entry(key, keyPosition, node));
    }

    /** RETURN: String, the key here; null where no key stands here (fault
     *          recorded). */
    private static String parseKey(Cursor cursor, String file, List<ParseFault> faultList) {
        if (cursor.peek().equals("\"")) return parseQuoted(cursor, file, faultList);
        String text = token(cursor.text, cursor.iCol);
        if (text.isEmpty()) {
            faultList.add(new ParseFault(FaultKind.SYNTAX, file, cursor.position(),
                                         "expected a key, found '" + cursor.peekCharacter().strip() + "'"));
            return null;
        }
        cursor.skip(text.length());
        return text;
    }

    /** RETURN: Node, the value here -- scalar, list or object; null where
     *          nothing usable stands here (fault recorded). 'inListF': an
     *          empty value is a fault, not null -- no key it could belong to. */
    private static Node parseValue(Cursor cursor, String file, List<ParseFault> faultList, boolean inListF) {
        skipSpace(cursor);
        Position position = cursor.position();
        String   c        = cursor.peek();
        if (c.equals("{")) {
            cursor.skip(1);
            return parseBody(cursor, "}", file, faultList);
        } else if (c.equals("[")) {
            cursor.skip(1);
            return parseList(cursor, position, file, faultList);
        } else if (c.equals("\"") && cursor.peek(1).equals("\"") && cursor.peek(2).equals("\"")) {
            String value = parseTripleQuoted(cursor, file, faultList);
            return value == null ? null : new ScalarNode(value, position);
        } else if (c.equals("\"")) {
            String value = parseQuoted(cursor, file, faultList);
            return value == null ? null : new ScalarNode(value, position);
        } else if (c.equals("$") && cursor.peek(1).equals("{")) {
            faultList.add(new ParseFault(FaultKind.REFUSED, file, position,
                                         "substitutions '${...}' do not exist here: a specification refers to nothing outside its file"));
            cursor.skipLine();
            return null;
        }
        return parseBare(cursor, position, file, faultList, inListF);
    }

    /** RETURN: ListNode, the items up to ']' -- or up to the '}' of the
     *          object around it, or the end, each said once as a fault. */
    private static ListNode parseList(Cursor cursor, Position position, String file, List<ParseFault> faultList) {
        List<Node> itemList = new ArrayList<>();
        while (true) {
            skipBlank(cursor);
            if (cursor.atEnd()) {
                faultList.add(new ParseFault(FaultKind.SYNTAX, file, cursor.position(), "unterminated list: ']' missing"));
                break;
            }
            String c = cursor.peek();
            if (c.equals("]")) {
                cursor.skip(1);
                break;
            } else if (c.equals(",")) {
                cursor.skip(1);
            } else if (c.equals("}")) {
                //  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' was
                //  forgotten. Said once, the brace left to its owner.
                faultList.add(new ParseFault(FaultKind.SYNTAX, file, cursor.position(),
                                             "unterminated list: ']' missing before '}'"));
                break;
            } else {
                int  beforeLine = cursor.iLine, beforeCol = cursor.iCol;
                Node item = parseValue(cursor, file, faultList, true);
                if (item != null) itemList.add(item);
                //  NO VALUE READ AND NOTHING CONSUMED: step over the character
                //  the value refused, or the loop never ends.
                if (item == null && cursor.iLine == beforeLine && cursor.iCol == beforeCol) cursor.skip(1);
            }
        }
        return new ListNode(Collections.unmodifiableList(itemList), position);
    }

    /** RETURN: String, the text between three double quotes and the next
     *          three, over as many lines as it takes, AS WRITTEN (no escape
     *          resolved), laid out as a docstring ('cleandoc'); null where no
     *          closing three quotes stand before the end (fault recorded). */
    private static String parseTripleQuoted(Cursor cursor, String file, List<ParseFault> faultList) {
        Position begin = cursor.position();
        cursor.skip(3);
        List<String> pieceList = new ArrayList<>();
        while (!cursor.atEnd()) {
            String text = cursor.text;
            int    end  = cursor.iCol <= text.length() ? text.indexOf(TRIPLE_QUOTE, cursor.iCol) : -1;
            if (end >= 0) {
                pieceList.add(text.substring(cursor.iCol, end));
                cursor.iCol = end + 3;
                return cleandoc(String.join("\n", pieceList));
            }
            pieceList.add(cursor.iCol <= text.length() ? text.substring(cursor.iCol) : "");
            cursor.skipLine();
        }
        faultList.add(new ParseFault(FaultKind.SYNTAX, file, begin,
                                     "unterminated triple-quoted string: closing '\"\"\"' missing"));
        return null;
    }

    /** RETURN: String, the quoted string's content, escapes ('\n', '\t',
     *          '\"', '\\'; any other character stands for itself) resolved;
     *          null where it is unterminated at its line's end (fault
     *          recorded, the cursor at the line's end). */
    private static String parseQuoted(Cursor cursor, String file, List<ParseFault> faultList) {
        Position begin = cursor.position();
        String   text  = cursor.text;
        int      i     = cursor.iCol + 1;                    // past the opening quote
        Matcher  plain = QUOTED_PLAIN_RE.matcher(text);
        plain.region(Math.min(i, text.length()), text.length());
        if (plain.lookingAt()) {
            cursor.iCol = plain.end();
            return plain.group(1);
        }
        StringBuilder piece = new StringBuilder();
        while (true) {
            if (i >= text.length()) {
                faultList.add(new ParseFault(FaultKind.SYNTAX, file, begin, "unterminated string"));
                cursor.iCol = i;
                return null;
            }
            char c = text.charAt(i);
            if (c == '"') {
                cursor.iCol = i + 1;
                return piece.toString();
            } else if (c == '\\') {
                i += 1;
                String escaped = i < text.length() ? String.valueOf(text.charAt(i)) : "";
                switch (escaped) {
                    case "n" -> piece.append('\n');
                    case "t" -> piece.append('\t');
                    default  -> piece.append(escaped);              // '"', '\\', anything
                }
                i += 1;
            } else {
                piece.append(c);
                i += 1;
            }
        }
    }

    /** RETURN: ScalarNode, the bare token here -- a boolean, a number, or a
     *          spelling of nothing; null where it is none of those (fault
     *          recorded): a string value is written in double quotes. */
    private static ScalarNode parseBare(Cursor cursor, Position position, String file, List<ParseFault> faultList,
                                        boolean inListF) {
        String raw = token(cursor.text, cursor.iCol);
        //  A SIGN STANDING APART from its digits: '- 0.12'; where nothing but
        //  blanks lies between it and a number, the two are one number.
        if (raw.equals("+") || raw.equals("-")) {
            String text  = cursor.text;
            int    start = blankEnd(text, cursor.iCol + 1);
            String after = token(text, start);
            //  The two must make ONE number: '- -1.5e3' does not (python hwut_hocon).
            if (!after.isEmpty() && number(after) != NOT_A_TOKEN && number(raw + after) != NOT_A_TOKEN) {
                cursor.iCol = start + after.length();
                return new ScalarNode(number(raw + after), position);
            }
        }
        if (raw.startsWith("${")) {
            faultList.add(new ParseFault(FaultKind.REFUSED, file, cursor.position(), "substitutions '${...}' do not exist here"));
            cursor.skipLine();
            return null;
        }
        int comment = raw.indexOf("//");
        if (comment != -1) raw = raw.substring(0, comment);
        cursor.skip(raw.length());
        if (raw.isEmpty()) {
            if (inListF) {
                faultList.add(new ParseFault(FaultKind.SYNTAX, file, position,
                                             "expected a value, found '" + cursor.peekCharacter().strip() + "'"));
                return null;
            }
            return new ScalarNode(null, position);                 // an empty value is null
        }
        Object value = interpret(raw);
        if (value == NOT_A_TOKEN) {
            faultList.add(new ParseFault(FaultKind.SYNTAX, file, position,
                                         "a string is written in double quotes: \"" + raw + "\""));
            return null;
        }
        return new ScalarNode(value, position);
    }

    /** RETURN: Object, what the bare text says -- null for the spellings of
     *          nothing, Boolean, an integer or Double; NOT_A_TOKEN where it is
     *          no bare token at all (an unquoted string). */
    private static Object interpret(String raw) {
        if (NULL_SET.contains(raw)) return null;
        if (BOOL_DB.containsKey(raw)) return BOOL_DB.get(raw);
        return number(raw);
    }

    /** RETURN: Object, the number the text spells, in whatever radix -- Long
     *          (BigInteger beyond 64 bits) or Double; '_' enters no value;
     *          NOT_A_TOKEN where it spells no number. */
    private static Object number(String raw) {
        boolean signF = raw.startsWith("+") || raw.startsWith("-");
        String  body  = signF ? raw.substring(1) : raw;
        boolean minus = raw.startsWith("-");
        String  head  = body.length() >= 2 ? body.substring(0, 2) : body;
        if (head.equals("0r") || head.equals("0R")) {
            BigInteger value = roman(body.substring(2));
            //  A refusal is a refusal: it must not be signed.
            return value == null ? NOT_A_TOKEN : integer(minus ? value.negate() : value);
        }
        int radix = switch (head) {
            case "0x", "0X" -> 16;
            case "0b", "0B" -> 2;
            case "0o", "0O" -> 8;
            default         -> 0;
        };
        if (radix != 0) {
            String digitText = withoutHelper(body.substring(2), radix);
            if (digitText == null) return NOT_A_TOKEN;
            BigInteger value = new BigInteger(digitText, radix);
            return integer(minus ? value.negate() : value);
        }
        if (!DECIMAL_RE.matcher(raw).matches()) return NOT_A_TOKEN;
        String text = raw.replace("_", "");
        if (text.contains(".") || text.contains("e") || text.contains("E")) return Double.parseDouble(text);
        return integer(new BigInteger(text));
    }

    /** RETURN: Object, 'value' as a Long where it fits 64 bits, else the
     *          BigInteger itself. */
    private static Object integer(BigInteger value) {
        return value.bitLength() < 64 ? (Object) value.longValue() : value;
    }

    /** RETURN: String, 'text' with every '_' removed; null where it carries
     *          no digit, a character that is no digit of 'radix', or an '_'
     *          that separates nothing. */
    private static String withoutHelper(String text, int radix) {
        if (text.isEmpty() || text.startsWith("_") || text.endsWith("_")) return null;
        if (text.contains("__"))                                           return null;
        String stripped = text.replace("_", "");
        if (stripped.isEmpty()) return null;
        String digitSet = switch (radix) { case 16 -> "0123456789abcdefABCDEF"; case 2 -> "01"; default -> "01234567"; };
        for (int i = 0; i < stripped.length(); ++i) if (digitSet.indexOf(stripped.charAt(i)) < 0) return null;
        return stripped;
    }

    /** RETURN: BigInteger, the number the roman numeral spells; null where
     *          the text is no roman numeral of the strict form ('IIII', 'VX'
     *          are none). */
    private static BigInteger roman(String text) {
        if (text.isEmpty() || !ROMAN_RE.matcher(text).matches()) return null;
        int total = 0, previous = 0;
        for (int i = text.length() - 1; i >= 0; --i) {
            int value = switch (text.charAt(i)) {
                case 'I' -> 1; case 'V' -> 5; case 'X' -> 10; case 'L' -> 50;
                case 'C' -> 100; case 'D' -> 500; default -> 1000;
            };
            total    = value < previous ? total - value : total + value;
            previous = Math.max(previous, value);
        }
        return BigInteger.valueOf(total);
    }

    /** RETURN: String, the token that begins at 'i' in 'text' (possibly
     *          empty; empty also where 'i' is past the end). */
    private static String token(String text, int i) {
        if (i > text.length()) return "";
        Matcher m = TOKEN_RE.matcher(text);
        m.region(i, text.length());
        return m.lookingAt() ? m.group() : "";
    }

    /** RETURN: int, the index of the first character at or after 'i' that
     *          is no blank (' ' or '\t'). */
    private static int blankEnd(String text, int i) {
        int n = text.length();
        while (i < n && (text.charAt(i) == ' ' || text.charAt(i) == '\t')) ++i;
        return i;
    }

    /** RETURN: nothing; blanks skipped on the current line; a comment ('#'
     *          or '//') skips the rest of the line. */
    private static void skipSpace(Cursor cursor) {
        String text = cursor.text;
        int    n    = text.length();
        int    i    = cursor.iCol;
        while (i < n && (text.charAt(i) == ' ' || text.charAt(i) == '\t')) ++i;
        cursor.iCol = i;
        if (i < n && (text.charAt(i) == '#' || text.startsWith("//", i))) cursor.skipLine();
    }

    /** RETURN: nothing; blanks, line ends, commas and comments skipped. */
    private static void skipBlank(Cursor cursor) {
        while (cursor.iLine < cursor.lineN) {
            String text = cursor.text;
            int    n    = text.length();
            int    i    = cursor.iCol;
            while (i < n && (text.charAt(i) == ' ' || text.charAt(i) == '\t' || text.charAt(i) == ',')) ++i;
            if (i >= n) {
                cursor.skipLine();
                continue;
            }
            cursor.iCol = i;
            char c = text.charAt(i);
            if (c == '#' || (c == '/' && text.startsWith("//", i))) {
                cursor.skipLine();
                continue;
            }
            return;
        }
    }

    /** RETURN: String, 'doc' laid out as Python's 'inspect.cleandoc' (3.13)
     *          lays out a docstring: tabs expanded to columns of 8, the first
     *          line's leading blanks removed, the blanks common to the
     *          following non-blank lines removed from each of them, blank
     *          lines at the beginning and the end dropped. */
    public static String cleandoc(String doc) {
        List<String> lines = new ArrayList<>(List.of(expandTabs(doc).split("\n", -1)));
        int margin = Integer.MAX_VALUE;
        for (int i = 1; i < lines.size(); ++i) {
            String line    = lines.get(i);
            int    content = line.length() - leadingBlanks(line);
            if (content > 0) margin = Math.min(margin, line.length() - content);
        }
        if (!lines.isEmpty()) lines.set(0, lines.get(0).substring(leadingBlanks(lines.get(0))));
        if (margin < Integer.MAX_VALUE)
            for (int i = 1; i < lines.size(); ++i) {
                String line = lines.get(i);
                lines.set(i, line.substring(Math.min(margin, line.length())));
            }
        while (!lines.isEmpty() && lines.get(lines.size() - 1).isEmpty()) lines.remove(lines.size() - 1);
        while (!lines.isEmpty() && lines.get(0).isEmpty()) lines.remove(0);
        return String.join("\n", lines);
    }

    /** RETURN: int, the number of ' ' at the beginning of 'line'. */
    private static int leadingBlanks(String line) {
        int i = 0;
        while (i < line.length() && line.charAt(i) == ' ') ++i;
        return i;
    }

    /** RETURN: String, 'text' with every tab replaced by the blanks up to the
     *          next column of 8 -- columns counted from each '\n' or '\r'
     *          (Python's 'str.expandtabs()'). */
    private static String expandTabs(String text) {
        StringBuilder out = new StringBuilder();
        int column = 0;
        for (int i = 0; i < text.length(); ) {
            int c = text.codePointAt(i);
            i += Character.charCount(c);
            if (c == '\t')                 { int n = 8 - column % 8; out.append(" ".repeat(n)); column += n; }
            else if (c == '\n' || c == '\r') { out.append((char) c); column = 0; }
            else                           { out.appendCodePoint(c); column += 1; }
        }
        return out.toString();
    }
}
