// @hwut {
//     title      = "HOCON parser: subset (A), annotated tree"
//     build      { framework = "make", executable = "%.exe"
//                  caps { memory_mb = 2048 } }
//     choices {
//         comments  { features = ["sv-hocon"] }
//         faults    { features = ["sv-hocon"] }
//         fuzz      { features = ["sv-hocon"] }
//         numbers   { features = ["sv-hocon"] }
//         oneline   { features = ["sv-hocon"] }
//         positions { features = ["sv-hocon"] }
//         quoting   { features = ["sv-hocon"] }
//         refused   { features = ["sv-hocon"] }
//         scalars   { features = ["sv-hocon"] }
//         structure { features = ["sv-hocon"] }
//         triple    { features = ["sv-hocon"] }
//         unclosed  { features = ["sv-hocon"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The SystemVerilog port of 'python/TEST/test-hwut_hocon.py', choice
//          for choice, held against its GOOD files by '.link'. A value prints
//          as Python's '%r (type)' prints it; the fuzz draws the same edits
//          from the same seed ('deterministic_random') and bounds every parse
//          by a timer.
// _____________________________________________________________________________
import hwut_runner::*;
import hwut_pytext::*;
import hwut_hocon::*;
import deterministic_random::*;

class Test extends HwutRunner;
    localparam int FUZZ_INPUT_N = 3000;
    localparam int FUZZ_BOUND_US = 500000;      // one parse takes well under a millisecond

    function new();
        // RETURN: the runner of this test.
        super.new("HOCON parser: subset (A), annotated tree;",
                  '{"scalars", "numbers", "quoting", "structure", "oneline", "comments", "refused",
                    "triple", "unclosed", "fuzz", "faults", "positions"});
    endfunction

    function void banner(string label);
        // RETURN: nothing; the section heading is printed.
        $display("");
        $display("--- %s ---", label);
    endfunction

    function void lines(string text, ref SourceLine line_list[$], input int line_offset = 0,
                        input int column_offset = 0);
        // RETURN: nothing; 'line_list' holds 'text' split at every newline
        //         (an ending one gives a last, empty line, as Python's
        //         'split'), offsets applied uniformly.
        int begin_ = 0;
        line_list = {};
        for (int i = 0; i <= text.len(); i++) begin
            if (i < text.len() && text[i] != "\n") continue;
            line_list.push_back(SourceLine::make(i > begin_ ? text.substr(begin_, i - 1) : string'(""),
                                                 line_list.size() + 1 + line_offset, column_offset));
            begin_ = i + 1;
        end
    endfunction

    function void show(Node node, int indent = 0);
        // RETURN: nothing; the annotated tree is printed, positions included.
        string     pad = "";
        ObjectNode object_;
        ListNode   list_;
        ScalarNode scalar;
        for (int i = 0; i < indent; i++) pad = {pad, "    "};
        if ($cast(object_, node)) begin
            $display("%s{ at %s", pad, object_.position.to_string());
            foreach (object_.entry_list[i]) begin
                $display("%s  key '%s' at %s ->", pad, object_.entry_list[i].key, object_.entry_list[i].key_position.to_string());
                show(object_.entry_list[i].node, indent + 1);
            end
            $display("%s}", pad);
        end else if ($cast(list_, node)) begin
            $display("%s[ at %s", pad, list_.position.to_string());
            foreach (list_.item_list[i]) show(list_.item_list[i], indent + 1);
            $display("%s]", pad);
        end else begin
            void'($cast(scalar, node));
            $display("%s%s (%s) at %s", pad, scalar.value_repr(), scalar.type_name(), scalar.position.to_string());
        end
    endfunction

    function void parsed(string label, string text, int line_offset = 0, int column_offset = 0);
        // RETURN: nothing; 'text' is parsed, its tree and faults printed.
        SourceLine line_list[$] = {};
        Fault      fault_list[$] = {};
        ObjectNode document;
        banner(label);
        lines(text, line_list, line_offset, column_offset);
        document = parse(line_list, "f.hocon", fault_list);
        show(document);
        foreach (fault_list[i]) $display("FAULT %s", fault_list[i].to_string());
    endfunction

    function void test_scalars();
        // RETURN: nothing; every scalar shape.
        parsed("scalars", {
            "a = bare\n",
            "b = \"quoted \\\"x\\\" and \\n\"\n",
            "c = 42\n",
            "d = -3.14\n",
            "e = 1e-6\n",
            "f = true\n",
            "g = no\n",
            "h = make %.exe\n",
            "i: \"colon-bound\"\n",
            "j = null\n",
            "k = nihil\n",
            "l =\n"});
    endfunction

    function void test_numbers();
        // RETURN: nothing; every radix, the helper, and the split sign.
        parsed("decimal, with sign and exponent", {
            "a = 42\n", "b = -0.12\n", "c = +7e212\n", "d = 6.02e23\n", "e = .5\n"});
        parsed("the visual helper enters no value", {
            "a = 1_000\n", "b = 7_000.5_5\n"});
        parsed("hexadecimal, binary, octal", {
            "a = 0xDEAD_BEEF\n", "b = 0b0111_11_01\n", "c = 0o3124\n", "d = 0XFF\n", "e = -0b1010\n"});
        parsed("roman", {
            "a = 0rIV\n", "b = 0rMCMLXXXIV\n", "c = -0rX\n"});
        parsed("a sign standing apart from its digits", {
            "a = - 0.12\n", "b = + 7\n", "c = - 0xFF\n", "d = - -1.5e3\n"});
        parsed("what spells no number is a string, and carries quotes", {
            "a = 1.2.3\n", "b = 0x\n", "c = 0b012\n", "d = 1__0\n", "e = 0rIIII\n", "f = 0rVX\n"});
        parsed("no arithmetic: this language computes nothing",
            "a = 5 - 1\n");
    endfunction

    function void test_quoting();
        // RETURN: nothing; the quoted string, and the unquoted word.
        parsed("quoted: blanks, comment markers and binders are content", {
            "a = \"make %.exe\"\n", "b = \"not # a comment\"\n", "c = \"x = y\"\n", "d = \"yes\"\n"});
        parsed("unquoted: refused, and shown in the quotes it wants", {
            "a = make\n", "b = strip.pype\n", "c = [one, two]\n", "d = 1\n"});
    endfunction

    function void test_structure();
        // RETURN: nothing; objects, lists, nesting.
        parsed("nesting and key-brace", {
            "outer {\n", "    inner = { deep = 1 }\n", "    braced { x = 2 }\n", "}\n"});
        parsed("lists", {
            "commas   = [one, two, three]\n",
            "newlines = [\n", "    1\n", "    2\n", "]\n",
            "objects  = [ { a = 1 }, { a = 2 } ]\n",
            "empty    = []\n"});
    endfunction

    function void test_oneline();
        // RETURN: nothing; entries sharing a line, without commas.
        parsed("two entries, one line, no comma", "caps { timeout_sec = 30  network = false }\n");
        parsed("a quoted value with blanks, beside a following key", "a { build = \"make %.exe\"  timeout_sec = 5 }\n");
        parsed("three entries, one line", "x { a = 1  b = \"two\"  c = { d = 3 } }\n");
    endfunction

    function void test_comments();
        // RETURN: nothing; both comment forms, whole-line and trailing.
        parsed("comments", {
            "# whole line\n", "a = 1   # trailing\n", "// slashes too\n", "b = 2   // trailing slashes\n",
            "c = bare value # comment cut\n"});
    endfunction

    function void test_refused();
        // RETURN: nothing; the three constructs that do not exist here.
        parsed("refused, each by name", {
            "include \"other.conf\"\n", "a = ${outside.value}\n", "b += appended\n", "d = survives\n"});
    endfunction

    function void test_triple();
        // RETURN: nothing; the text of several lines.
        parsed("several lines: indentation and blank ends go", {
            "doc = \"\"\"\n", "    First line.\n", "\n", "      indented more\n", "    last line\n",
            "    \"\"\"\n", "after = 1\n"});
        parsed("on one line; beside another entry; in a list", {
            "a = \"\"\"one line\"\"\"  b = 2\n", "c = [\"\"\"x\"\"\", \"y\"]\n"});
        parsed("as written: a quote, a backslash-n, a comment marker",
            "a = \"\"\"says \"no\" \\n # not a comment\"\"\"\n");
        parsed("never closed: a fault, at its beginning", {
            "a = 1\n", "b = \"\"\"open\n", "c = 2\n"});
    endfunction

    function void test_faults();
        // RETURN: nothing; faults accumulate; the parse completes.
        parsed("faults accumulate", {
            "a = 1\n", "a = 2\n", "b = \"unterminated\n", "}\n", "c {\n", "    d = 3\n"});
    endfunction

    function void test_unclosed();
        // RETURN: nothing; a list whose ']' was forgotten ENDS: the brace
        //         closes the object, the fault is said once.
        parsed("a list closed by the object's brace", {
            "@hwut { title = \"B\" choices = [ }\n", "after = 1\n"});
        parsed("a stray character in a list", "a = [1, ; 2]\n");
    endfunction

    // ------------------------------------------------------------------ fuzz
    function string slice(string text, int from, int to);
        // RETURN: Python's 'text[from:to]': the characters from 'from' up to
        //         'to' excluded, both bounded by the text's length.
        if (to > text.len()) to = text.len();
        if (from >= to) return "";
        return text.substr(from, to - 1);
    endfunction

    function string mutated(DeterministicStream stream, string text, string alphabet[$]);
        // RETURN: 'text' edited by one to four random insertions, deletions
        //         and duplications of a short stretch -- Python's draws, in
        //         Python's order.
        longint edit_n = stream.next_int(1, 4);
        for (longint edit = 0; edit < edit_n; edit++) begin
            int     i    = int'(stream.next_int(0, text.len()));
            longint what = stream.next_int(0, 2);           // drawn once: a 'case' may read its
            case (what)                                     // expression once per item
                0:       text = {slice(text, 0, i), stream.select(alphabet), slice(text, i, text.len())};
                1:       text = {slice(text, 0, i), slice(text, i + 1, text.len())};
                default: begin
                    int j = int'(stream.next_int(0, text.len()));
                    text = {slice(text, 0, i), slice(text, j, j + 5), slice(text, i, text.len())};
                end
            endcase
        end
        return text;
    endfunction

    function void test_fuzz();
        // RETURN: nothing; every mutated header ends and answers faults --
        //         only the counts are printed.
        string seed_list[$] = '{
            {"@hwut {\n",
             "    title    = \"T\"\n",
             "    choices  = [\"a\", \"b\"]\n",
             "    tolerance { eq_pattern = [\"x.*\"] }\n",
             "    n        = -1.5e3\n",
             "    f        = true\n",
             "}\n"},
            {"hwut {\n",
             "    target     { clean = \"./c.sh\" }\n",
             "    dependency { \"a.py\" = [\"b.py one\"] }\n",
             "    ignore     = [\"x\"]   // comment\n",
             "    # comment\n",
             "}\n"}};
        //  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a
        //  few that it refuses by name, and some ordinary ones.
        string alphabet[$] = '{
            "{", "}", "[", "]", "\"", ",", "=", ":", "#", "/", "\\", "$", " ", "\n", "\t", "-", "+", ".",
            "e", "E", "0", "a", "\"\"\"", "${", "//", "+="};
        DeterministicStream stream = new(4711);
        int                 clean = 0, with_faults = 0, hang = 0, exception = 0;
        string              first_hang = "";
        bit                 first_hang_f = 0;
        for (int k = 0; k < FUZZ_INPUT_N; k++) begin
            string     text = mutated(stream, stream.select(seed_list), alphabet);
            SourceLine line_list[$] = {};
            Fault      fault_list[$] = {};
            bit        hang_f;
            ObjectNode document;
            lines(text, line_list);
            document = parse_bounded(line_list, "f.hocon", fault_list, FUZZ_BOUND_US, hang_f);
            if (hang_f) begin
                hang += 1;
                if (!first_hang_f) begin first_hang = text; first_hang_f = 1; end
            end
            else if (fault_list.size()) with_faults += 1;
            else                        clean += 1;
        end
        banner($sformatf("%0d mutated headers", FUZZ_INPUT_N));
        $display("    %s %0d", padded("clean", 12), clean);
        $display("    %s %0d", padded("with faults", 12), with_faults);
        $display("    %s %0d", padded("hang", 12), hang);
        $display("    %s %0d", padded("exception", 12), exception);     // SystemVerilog raises nothing: always 0
        if (first_hang_f) begin
            $display("FIRST HANG:");
            $display("%s", first_hang);
        end
    endfunction

    function void test_positions();
        // RETURN: nothing; offsets carried: the same text reported at its
        //         place in a larger file, as an unwrapped header would be.
        string text = {"@hwut {\n", "    title = \"T\"\n", "}"};
        parsed("plain: as its own file", text);
        parsed("offset: same text, region begins at line 40, 3 columns stripped", text, 39, 3);
    endfunction

    virtual task play(string choice);
        // RETURN: nothing; the choice 'choice' ran.
        case (choice)
            "scalars":   test_scalars();
            "numbers":   test_numbers();
            "quoting":   test_quoting();
            "structure": test_structure();
            "oneline":   test_oneline();
            "comments":  test_comments();
            "refused":   test_refused();
            "triple":    test_triple();
            "unclosed":  test_unclosed();
            "fuzz":      test_fuzz();
            "faults":    test_faults();
            "positions": test_positions();
        endcase
    endtask
endclass

module test_hwut_hocon;
    initial begin
        Test test = new();
        test.run();
    end
endmodule
