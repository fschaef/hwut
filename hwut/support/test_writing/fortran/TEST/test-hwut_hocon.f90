! @hwut {
!     title      = "HOCON parser: subset (A), annotated tree"
!     build      { framework = "make", target = "%.exe" }
!     choices {
!         comments  { features = ["fortran-hocon"] }
!         faults    { features = ["fortran-hocon"] }
!         fuzz      { features = ["fortran-hocon"] }
!         numbers   { features = ["fortran-hocon"] }
!         oneline   { features = ["fortran-hocon"] }
!         positions { features = ["fortran-hocon"] }
!         quoting   { features = ["fortran-hocon"] }
!         refused   { features = ["fortran-hocon"] }
!         scalars   { features = ["fortran-hocon"] }
!         structure { features = ["fortran-hocon"] }
!         triple    { features = ["fortran-hocon"] }
!         unclosed  { features = ["fortran-hocon"] }
!     }
!     interactive = true
! }
!
! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: The Fortran port of 'python/TEST/test-hwut_hocon.py', choice for
!          choice, held against its GOOD files by '.link'. A value prints as
!          Python's '%r (type)' prints it; the fuzz draws the same edits from
!          the same seed ('deterministic_random'), and a parse stopped by its
!          bound counts as a hang. Fortran raises nothing: 'exception' is 0.
!          The texts are Fortran literals: no escape is resolved in them, so
!          a backslash stands for itself.
! _____________________________________________________________________________
module test_hwut_hocon_choices
    use, intrinsic :: iso_fortran_env, only: int64
    use hwut_text
    use hwut_runner
    use hwut_hocon
    use deterministic_random
    implicit none

    character(*), parameter :: Q3 = '"""'

contains

    subroutine banner(label)
        character(*), intent(in) :: label
        call say("")
        call say("--- " // label // " ---")
    end subroutine

    function lines(text, line_offset, column_offset) result(line_list)
        ! RETURN: 'text' split at every newline (an ending one gives a last,
        !         empty line, as Python's 'split'), offsets applied uniformly.
        character(*), intent(in)      :: text
        integer, intent(in), optional :: line_offset, column_offset
        type(SourceLine), allocatable :: line_list(:)
        type(string), allocatable     :: piece(:)
        integer                       :: i
        piece = split_lines(text)
        allocate(line_list(size(piece)))
        do i = 1, size(piece)
            line_list(i)%text = piece(i)%s
            line_list(i)%line = i
            if( present(line_offset) ) line_list(i)%line = i + line_offset
            if( present(column_offset) ) line_list(i)%column_offset = column_offset
        end do
    end function

    recursive subroutine show(document, k, indent)
        ! RETURN: nothing; the annotated tree from the node at position 'k'
        !         was printed, positions included.
        type(HoconDocument), intent(in) :: document
        integer, intent(in)             :: k, indent
        character(:), allocatable       :: pad
        integer                         :: i, c
        pad = repeat(" ", 4 * indent)
        associate( node => document%node(k) )
            select case( node%kind )
            case( OBJECT_NODE )
                call say(pad // "{ at " // node%position%str())
                do i = 1, size(node%child)
                    c = node%child(i)
                    call say(pad // "  key '" // document%node(c)%key // "' at " &
                             // document%node(c)%key_position%str() // " ->")
                    call show(document, c, indent + 1)
                end do
                call say(pad // "}")
            case( LIST_NODE )
                call say(pad // "[ at " // node%position%str())
                do i = 1, size(node%child)
                    call show(document, node%child(i), indent + 1)
                end do
                call say(pad // "]")
            case default
                call say(pad // node%value_repr() // " (" // node%type_name() // ") at " // node%position%str())
            end select
        end associate
    end subroutine

    subroutine run(label, text, line_offset, column_offset)
        ! RETURN: nothing; 'text' was parsed, its tree and faults printed.
        character(*), intent(in)      :: label, text
        integer, intent(in), optional :: line_offset, column_offset
        type(HoconDocument)           :: document
        type(ParseFault), allocatable :: fault(:)
        integer                       :: i
        call banner(label)
        call parse(lines(text, line_offset, column_offset), "f.hocon", document, fault)
        call show(document, document%root, 0)
        do i = 1, size(fault)
            call say("FAULT " // fault(i)%str())
        end do
    end subroutine

    subroutine run_scalars()
        call run("scalars", &
            'a = bare' // NL // &
            'b = "quoted \"x\" and \n"' // NL // &
            'c = 42' // NL // &
            'd = -3.14' // NL // &
            'e = 1e-6' // NL // &
            'f = true' // NL // &
            'g = no' // NL // &
            'h = make %.exe' // NL // &
            'i: "colon-bound"' // NL // &
            'j = null' // NL // &
            'k = nihil' // NL // &
            'l =' // NL)
    end subroutine

    subroutine run_numbers()
        call run("decimal, with sign and exponent", &
            'a = 42' // NL // 'b = -0.12' // NL // 'c = +7e212' // NL // 'd = 6.02e23' // NL // 'e = .5' // NL)
        call run("the visual helper enters no value", &
            'a = 1_000' // NL // 'b = 7_000.5_5' // NL)
        call run("hexadecimal, binary, octal", &
            'a = 0xDEAD_BEEF' // NL // 'b = 0b0111_11_01' // NL // 'c = 0o3124' // NL // 'd = 0XFF' // NL &
            // 'e = -0b1010' // NL)
        call run("roman", &
            'a = 0rIV' // NL // 'b = 0rMCMLXXXIV' // NL // 'c = -0rX' // NL)
        call run("a sign standing apart from its digits", &
            'a = - 0.12' // NL // 'b = + 7' // NL // 'c = - 0xFF' // NL // 'd = - -1.5e3' // NL)
        call run("what spells no number is a string, and carries quotes", &
            'a = 1.2.3' // NL // 'b = 0x' // NL // 'c = 0b012' // NL // 'd = 1__0' // NL // 'e = 0rIIII' // NL &
            // 'f = 0rVX' // NL)
        call run("no arithmetic: this language computes nothing", &
            'a = 5 - 1' // NL)
    end subroutine

    subroutine run_quoting()
        call run("quoted: blanks, comment markers and binders are content", &
            'a = "make %.exe"' // NL // 'b = "not # a comment"' // NL // 'c = "x = y"' // NL // 'd = "yes"' // NL)
        call run("unquoted: refused, and shown in the quotes it wants", &
            'a = make' // NL // 'b = strip.pype' // NL // 'c = [one, two]' // NL // 'd = 1' // NL)
    end subroutine

    subroutine run_structure()
        call run("nesting and key-brace", &
            'outer {' // NL // '    inner = { deep = 1 }' // NL // '    braced { x = 2 }' // NL // '}' // NL)
        call run("lists", &
            'commas   = [one, two, three]' // NL // &
            'newlines = [' // NL // '    1' // NL // '    2' // NL // ']' // NL // &
            'objects  = [ { a = 1 }, { a = 2 } ]' // NL // &
            'empty    = []' // NL)
    end subroutine

    subroutine run_oneline()
        call run("two entries, one line, no comma", 'caps { timeout_sec = 30  network = false }' // NL)
        call run("a quoted value with blanks, beside a following key", 'a { build = "make %.exe"  timeout_sec = 5 }' // NL)
        call run("three entries, one line", 'x { a = 1  b = "two"  c = { d = 3 } }' // NL)
    end subroutine

    subroutine run_comments()
        call run("comments", &
            '# whole line' // NL // 'a = 1   # trailing' // NL // '// slashes too' // NL &
            // 'b = 2   // trailing slashes' // NL // 'c = bare value # comment cut' // NL)
    end subroutine

    subroutine run_refused()
        call run("refused, each by name", &
            'include "other.conf"' // NL // 'a = ${outside.value}' // NL // 'b += appended' // NL // 'd = survives' // NL)
    end subroutine

    subroutine run_triple()
        call run("several lines: indentation and blank ends go", &
            'doc = ' // Q3 // NL // '    First line.' // NL // NL // '      indented more' // NL &
            // '    last line' // NL // '    ' // Q3 // NL // 'after = 1' // NL)
        call run("on one line; beside another entry; in a list", &
            'a = ' // Q3 // 'one line' // Q3 // '  b = 2' // NL // 'c = [' // Q3 // 'x' // Q3 // ', "y"]' // NL)
        call run("as written: a quote, a backslash-n, a comment marker", &
            'a = ' // Q3 // 'says "no" \n # not a comment' // Q3 // NL)
        call run("never closed: a fault, at its beginning", &
            'a = 1' // NL // 'b = ' // Q3 // 'open' // NL // 'c = 2' // NL)
    end subroutine

    subroutine run_faults()
        call run("faults accumulate", &
            'a = 1' // NL // 'a = 2' // NL // 'b = "unterminated' // NL // '}' // NL // 'c {' // NL // '    d = 3' // NL)
    end subroutine

    subroutine run_unclosed()
        call run("a list closed by the object's brace", '@hwut { title = "B" choices = [ }' // NL // 'after = 1' // NL)
        call run("a stray character in a list", 'a = [1, ; 2]' // NL)
    end subroutine

    subroutine run_positions()
        character(*), parameter :: TEXT = '@hwut {' // NL // '    title = "T"' // NL // '}'
        call run("plain: as its own file", TEXT)
        call run("offset: same text, region begins at line 40, 3 columns stripped", TEXT, 39, 3)
    end subroutine

    ! ------------------------------------------------------------------ fuzz
    function mutated(stream, original, alphabet) result(text)
        ! RETURN: 'original' edited by one to four random insertions,
        !         deletions and duplications of a short stretch -- drawn as
        !         Python draws them, one draw at a time.
        type(DeterministicStream), intent(inout) :: stream
        character(*), intent(in)                 :: original
        type(string), intent(in)                 :: alphabet(:)
        character(:), allocatable                :: text, piece
        integer                                  :: edit, edit_n, i, j, how, k
        text   = original
        edit_n = stream%next_int(1, 4)
        do edit = 1, edit_n
            i   = stream%next_int(0, len(text))
            how = stream%next_int(0, 2)
            select case( how )
            case( 0 )
                k     = stream%select(size(alphabet))
                piece = alphabet(k)%s
            case( 1 )
                text = text(:i) // text(i + 2:)
                cycle
            case default
                j     = stream%next_int(0, len(text))
                piece = text(j + 1:min(j + 5, len(text)))
            end select
            text = text(:i) // piece // text(i + 1:)
        end do
    end function

    subroutine run_fuzz()
        integer, parameter            :: FUZZ_INPUT_N = 3000
        type(string)                  :: seed(2), alphabet(26)
        type(DeterministicStream)     :: stream
        type(HoconDocument)           :: document
        type(ParseFault), allocatable :: fault(:)
        character(:), allocatable     :: text, first_hang
        character(12)                 :: label
        integer                       :: n, k, clean, with_faults, hang
        logical                       :: hung
        seed(1)%s = '@hwut {' // NL // '    title    = "T"' // NL // '    choices  = ["a", "b"]' // NL &
                    // '    tolerance { eq_pattern = ["x.*"] }' // NL // '    n        = -1.5e3' // NL &
                    // '    f        = true' // NL // '}' // NL
        seed(2)%s = 'hwut {' // NL // '    target     { clean = "./c.sh" }' // NL &
                    // '    dependency { "a.py" = ["b.py one"] }' // NL // '    ignore     = ["x"]   // comment' // NL &
                    // '    # comment' // NL // '}' // NL
        ! WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few
        ! that it refuses by name, and some ordinary ones.
        alphabet = [string("{"), string("}"), string("["), string("]"), string('"'), string(","), &
                    string("="), string(":"), string("#"), string("/"), string("\"), string("$"), &
                    string(" "), string(NL), string(TAB), string("-"), string("+"), string("."), &
                    string("e"), string("E"), string("0"), string("a"), string(Q3), string("${"), &
                    string("//"), string("+=")]
        stream      = DeterministicStream(4711)
        clean       = 0
        with_faults = 0
        hang        = 0
        do n = 1, FUZZ_INPUT_N
            k    = stream%select(size(seed))
            text = mutated(stream, seed(k)%s, alphabet)
            call parse(lines(text), "f.hocon", document, fault, hung)
            if( hung ) then
                hang = hang + 1
                if( .not. allocated(first_hang) ) first_hang = text
            else if( size(fault) > 0 ) then
                with_faults = with_faults + 1
            else
                clean = clean + 1
            end if
        end do
        call banner(str(FUZZ_INPUT_N) // " mutated headers")
        label = "clean";       call say("    " // label // " " // str(clean))
        label = "with faults"; call say("    " // label // " " // str(with_faults))
        label = "hang";        call say("    " // label // " " // str(hang))
        label = "exception";   call say("    " // label // " " // str(0))      ! Fortran raises nothing
        if( allocated(first_hang) ) call say("FIRST HANG:" // NL // first_hang)
    end subroutine

end module test_hwut_hocon_choices

program test_hwut_hocon
    ! THE CHOICES ARE MODULE PROCEDURES: a procedure pointer to an internal
    ! one would need a trampoline, and with it an executable stack.
    use hwut_runner
    use test_hwut_hocon_choices
    implicit none
    type(HwutRunner) :: runner
    runner = HwutRunner("HOCON parser: subset (A), annotated tree;", [ &
                 HwutChoice("scalars", run_scalars), HwutChoice("numbers", run_numbers), &
                 HwutChoice("quoting", run_quoting), HwutChoice("structure", run_structure), &
                 HwutChoice("oneline", run_oneline), HwutChoice("comments", run_comments), &
                 HwutChoice("refused", run_refused), HwutChoice("triple", run_triple), &
                 HwutChoice("unclosed", run_unclosed), HwutChoice("fuzz", run_fuzz), &
                 HwutChoice("faults", run_faults), HwutChoice("positions", run_positions)])
    call runner%run()
end program test_hwut_hocon
