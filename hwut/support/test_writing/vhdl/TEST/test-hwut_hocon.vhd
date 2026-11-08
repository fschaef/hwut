-- @hwut {
--     title      = "HOCON parser: subset (A), annotated tree"
--     build      { framework = "make", target = "%.exe" }
--     choices {
--         comments  { features = ["vhdl-hocon"] }
--         faults    { features = ["vhdl-hocon"] }
--         fuzz      { features = ["vhdl-hocon"] }
--         numbers   { features = ["vhdl-hocon"] }
--         oneline   { features = ["vhdl-hocon"] }
--         positions { features = ["vhdl-hocon"] }
--         quoting   { features = ["vhdl-hocon"] }
--         refused   { features = ["vhdl-hocon"] }
--         scalars   { features = ["vhdl-hocon"] }
--         structure { features = ["vhdl-hocon"] }
--         triple    { features = ["vhdl-hocon"] }
--         unclosed  { features = ["vhdl-hocon"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The VHDL port of 'python/TEST/test-hwut_hocon.py', choice for
--          choice, held against its GOOD files by '.link'. A value prints as
--          Python's '%r (type)' prints it; the fuzz draws the same edits from
--          the same seed ('deterministic_random', VHDL's own) and bounds every
--          parse by a timer.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_runner.all;
use work.hwut_pytext.all;
use work.hwut_hocon.all;
use work.deterministic_random.all;

entity test_hwut_hocon is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
end entity;

architecture test of test_hwut_hocon is
    constant Q : string := """";                        -- one double quote

    procedure banner(label_text : string) is
    begin print(""); print("--- " & label_text & " ---"); end procedure;

    procedure show(variable node : inout HoconNodeAccess; indent : natural := 0) is
        -- RETURN: nothing; the annotated tree is printed, positions included.
        constant pad : string(1 to 4 * indent) := (others => ' ');
    begin
        case node.kind is
            when HOCON_OBJECT =>
                print(pad & "{ at " & to_string(node.position));
                for i in node.entry'range loop
                    print(pad & "  key '" & node.entry(i).key.all & "' at " & to_string(node.entry(i).key_position) & " ->");
                    show(node.entry(i).node, indent + 1);
                end loop;
                print(pad & "}");
            when HOCON_LIST =>
                print(pad & "[ at " & to_string(node.position));
                for i in node.item'range loop show(node.item(i), indent + 1); end loop;
                print(pad & "]");
            when HOCON_SCALAR =>
                print(pad & node.value_repr.all & " (" & node.type_name.all & ") at " & to_string(node.position));
        end case;
    end procedure;

    procedure run(label_text : string; text : string; line_offset : integer := 0; column_offset : integer := 0) is
        -- RETURN: nothing; 'text' is parsed -- split at every LF, an ending
        --         one giving a last, empty line, as Python's 'split' -- its
        --         tree and faults printed.
        variable document : HoconNodeAccess;
        variable faults   : HoconFaultVectorAccess;
    begin
        banner(label_text);
        parse(text & LF, "f.hocon", document, faults, line_offset, column_offset);
        show(document);
        for i in faults'range loop print("FAULT " & faults(i).text.all); end loop;
        free(document); free(faults);
    end procedure;

    procedure run_scalars is
    begin
        run("scalars",
            "a = bare" & LF &
            "b = " & Q & "quoted \" & Q & "x\" & Q & " and \n" & Q & LF &
            "c = 42" & LF &
            "d = -3.14" & LF &
            "e = 1e-6" & LF &
            "f = true" & LF &
            "g = no" & LF &
            "h = make %.exe" & LF &
            "i: " & Q & "colon-bound" & Q & LF &
            "j = null" & LF &
            "k = nihil" & LF &
            "l =" & LF);
    end procedure;

    procedure run_numbers is
    begin
        run("decimal, with sign and exponent",
            "a = 42" & LF & "b = -0.12" & LF & "c = +7e212" & LF & "d = 6.02e23" & LF & "e = .5" & LF);
        run("the visual helper enters no value",
            "a = 1_000" & LF & "b = 7_000.5_5" & LF);
        run("hexadecimal, binary, octal",
            "a = 0xDEAD_BEEF" & LF & "b = 0b0111_11_01" & LF & "c = 0o3124" & LF & "d = 0XFF" & LF & "e = -0b1010" & LF);
        run("roman",
            "a = 0rIV" & LF & "b = 0rMCMLXXXIV" & LF & "c = -0rX" & LF);
        run("a sign standing apart from its digits",
            "a = - 0.12" & LF & "b = + 7" & LF & "c = - 0xFF" & LF & "d = - -1.5e3" & LF);
        run("what spells no number is a string, and carries quotes",
            "a = 1.2.3" & LF & "b = 0x" & LF & "c = 0b012" & LF & "d = 1__0" & LF & "e = 0rIIII" & LF & "f = 0rVX" & LF);
        run("no arithmetic: this language computes nothing",
            "a = 5 - 1" & LF);
    end procedure;

    procedure run_quoting is
    begin
        run("quoted: blanks, comment markers and binders are content",
            "a = " & Q & "make %.exe" & Q & LF & "b = " & Q & "not # a comment" & Q & LF
            & "c = " & Q & "x = y" & Q & LF & "d = " & Q & "yes" & Q & LF);
        run("unquoted: refused, and shown in the quotes it wants",
            "a = make" & LF & "b = strip.pype" & LF & "c = [one, two]" & LF & "d = 1" & LF);
    end procedure;

    procedure run_structure is
    begin
        run("nesting and key-brace",
            "outer {" & LF & "    inner = { deep = 1 }" & LF & "    braced { x = 2 }" & LF & "}" & LF);
        run("lists",
            "commas   = [one, two, three]" & LF &
            "newlines = [" & LF & "    1" & LF & "    2" & LF & "]" & LF &
            "objects  = [ { a = 1 }, { a = 2 } ]" & LF &
            "empty    = []" & LF);
    end procedure;

    procedure run_oneline is
    begin
        run("two entries, one line, no comma", "caps { timeout_sec = 30  network = false }" & LF);
        run("a quoted value with blanks, beside a following key",
            "a { build = " & Q & "make %.exe" & Q & "  timeout_sec = 5 }" & LF);
        run("three entries, one line", "x { a = 1  b = " & Q & "two" & Q & "  c = { d = 3 } }" & LF);
    end procedure;

    procedure run_comments is
    begin
        run("comments",
            "# whole line" & LF & "a = 1   # trailing" & LF & "// slashes too" & LF
            & "b = 2   // trailing slashes" & LF & "c = bare value # comment cut" & LF);
    end procedure;

    procedure run_refused is
    begin
        run("refused, each by name",
            "include " & Q & "other.conf" & Q & LF & "a = ${outside.value}" & LF & "b += appended" & LF
            & "d = survives" & LF);
    end procedure;

    procedure run_triple is
        constant QQQ : string := Q & Q & Q;
    begin
        run("several lines: indentation and blank ends go",
            "doc = " & QQQ & LF & "    First line." & LF & LF & "      indented more" & LF & "    last line" & LF
            & "    " & QQQ & LF & "after = 1" & LF);
        run("on one line; beside another entry; in a list",
            "a = " & QQQ & "one line" & QQQ & "  b = 2" & LF & "c = [" & QQQ & "x" & QQQ & ", " & Q & "y" & Q & "]" & LF);
        run("as written: a quote, a backslash-n, a comment marker",
            "a = " & QQQ & "says " & Q & "no" & Q & " \n # not a comment" & QQQ & LF);
        run("never closed: a fault, at its beginning",
            "a = 1" & LF & "b = " & QQQ & "open" & LF & "c = 2" & LF);
    end procedure;

    procedure run_faults is
    begin
        run("faults accumulate",
            "a = 1" & LF & "a = 2" & LF & "b = " & Q & "unterminated" & LF & "}" & LF & "c {" & LF & "    d = 3" & LF);
    end procedure;

    procedure run_unclosed is
    begin
        run("a list closed by the object's brace", "@hwut { title = " & Q & "B" & Q & " choices = [ }" & LF & "after = 1" & LF);
        run("a stray character in a list", "a = [1, ; 2]" & LF);
    end procedure;

    procedure run_positions is
        constant text : string := "@hwut {" & LF & "    title = " & Q & "T" & Q & LF & "}";
    begin
        run("plain: as its own file", text);
        run("offset: same text, region begins at line 40, 3 columns stripped", text, 39, 3);
    end procedure;

    -- -------------------------------------------------------------------- fuzz
    constant FUZZ_SEED_0 : string :=
        "@hwut {" & LF &
        "    title    = " & Q & "T" & Q & LF &
        "    choices  = [" & Q & "a" & Q & ", " & Q & "b" & Q & "]" & LF &
        "    tolerance { eq_pattern = [" & Q & "x.*" & Q & "] }" & LF &
        "    n        = -1.5e3" & LF &
        "    f        = true" & LF &
        "}" & LF;
    constant FUZZ_SEED_1 : string :=
        "hwut {" & LF &
        "    target     { clean = " & Q & "./c.sh" & Q & " }" & LF &
        "    dependency { " & Q & "a.py" & Q & " = [" & Q & "b.py one" & Q & "] }" & LF &
        "    ignore     = [" & Q & "x" & Q & "]   // comment" & LF &
        "    # comment" & LF &
        "}" & LF;
    constant FUZZ_INPUT_N  : positive := 3000;
    constant FUZZ_BOUND_US : positive := 500000;        -- one parse takes well under a millisecond

    function normal(text : string) return string is
        -- RETURN: string, 'text' indexed from 1.
        constant result : string(1 to text'length) := text;
    begin return result; end function;

    procedure mutated(variable stream : inout DeterministicStream; original : string; variable text : inout line) is
        -- RETURN: nothing; 'text' is 'original' edited by one to four random
        --         insertions, deletions and duplications of a short stretch.
        --  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a
        --  few that it refuses by name, and some ordinary ones.
        variable alphabet : line_vector(0 to 25) := (
            new string'("{"), new string'("}"), new string'("["), new string'("]"), new string'(Q),
            new string'(","), new string'("="), new string'(":"), new string'("#"), new string'("/"),
            new string'("\"), new string'("$"), new string'(" "), new string'("" & LF), new string'("" & HT),
            new string'("-"), new string'("+"), new string'("."), new string'("e"), new string'("E"),
            new string'("0"), new string'("a"), new string'(Q & Q & Q), new string'("${"), new string'("//"),
            new string'("+="));
        variable n, i, j, edit_n : natural;
        variable piece           : line;
        variable next_text       : line;
    begin
        text   := new string'(normal(original));
        edit_n := stream.next_int(1, 4);
        for edit in 1 to edit_n loop
            n := text'length;
            i := stream.next_int(0, n);
            case stream.next_int(0, 2) is
                when 0 =>
                    piece := new string'(alphabet(stream.select_index(alphabet'length)).all);
                when 1 =>
                    if i < n then
                        next_text := new string'(normal(text(1 to i) & text(i + 2 to n)));
                        deallocate(text); text := next_text;
                    end if;
                    next;
                when others =>
                    j     := stream.next_int(0, n);
                    piece := new string'(text(j + 1 to minimum(j + 5, n)));
            end case;
            next_text := new string'(normal(text(1 to i) & piece.all & text(i + 1 to n)));
            deallocate(text); deallocate(piece);
            text := next_text;
        end loop;
        for k in alphabet'range loop deallocate(alphabet(k)); end loop;
    end procedure;

    procedure run_fuzz is
        variable stream      : DeterministicStream;
        variable text        : line;
        variable first_hang  : line;
        variable document    : HoconNodeAccess;
        variable faults      : HoconFaultVectorAccess;
        variable clean, with_faults, hang, exception : natural := 0;
    begin
        stream.init(4711);
        for k in 1 to FUZZ_INPUT_N loop
            if stream.select_index(2) = 0 then mutated(stream, FUZZ_SEED_0, text);
            else                               mutated(stream, FUZZ_SEED_1, text);
            end if;
            parse(text.all & LF, "f.hocon", document, faults, bound_us => FUZZ_BOUND_US);
            if document = null then                     -- the tree of a hung parse is lost
                hang := hang + 1;
                if first_hang = null then first_hang := new string'(text.all); end if;
            elsif faults'length > 0 then with_faults := with_faults + 1;
            else                         clean       := clean + 1;
            end if;
            free(document); free(faults); deallocate(text);
        end loop;
        banner(integer'image(FUZZ_INPUT_N) & " mutated headers");
        print("    " & ljust("clean", 12)       & " " & integer'image(clean));
        print("    " & ljust("with faults", 12) & " " & integer'image(with_faults));
        print("    " & ljust("hang", 12)        & " " & integer'image(hang));
        print("    " & ljust("exception", 12)   & " " & integer'image(exception));   -- VHDL raises nothing: always 0
        if first_hang /= null then print("FIRST HANG:" & LF & first_hang.all); end if;
    end procedure;
begin
    main : process
        variable runner : HwutRunner;
    begin
        runner.init(HWUT_ARGC, HWUT_ARGV1, "HOCON parser: subset (A), annotated tree;");
        runner.add("scalars"); runner.add("numbers"); runner.add("quoting"); runner.add("structure");
        runner.add("oneline"); runner.add("comments"); runner.add("refused"); runner.add("triple");
        runner.add("unclosed"); runner.add("fuzz"); runner.add("faults"); runner.add("positions");
        while runner.dispatch loop
            if    runner.choice = "scalars"   then run_scalars;
            elsif runner.choice = "numbers"   then run_numbers;
            elsif runner.choice = "quoting"   then run_quoting;
            elsif runner.choice = "structure" then run_structure;
            elsif runner.choice = "oneline"   then run_oneline;
            elsif runner.choice = "comments"  then run_comments;
            elsif runner.choice = "refused"   then run_refused;
            elsif runner.choice = "triple"    then run_triple;
            elsif runner.choice = "unclosed"  then run_unclosed;
            elsif runner.choice = "fuzz"      then run_fuzz;
            elsif runner.choice = "faults"    then run_faults;
            elsif runner.choice = "positions" then run_positions;
            end if;
            runner.choice_done;
        end loop;
        wait;
    end process;
end architecture;
