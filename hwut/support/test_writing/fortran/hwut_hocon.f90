! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: PARSE THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE INTO THE
!          ANNOTATED TREE -- the port of 'python/hwut_hocon.py': every key,
!          every value and every block carries its file-relative position.
!
!     use hwut_hocon
!     type(SourceLine), allocatable :: line(:)        -- text, line, column_offset
!     type(HoconDocument)           :: document
!     type(ParseFault), allocatable :: fault(:)
!     call parse(line, "f.hocon", document, fault)
!     k = document%get(document%root, "a")           -- a node's position, 0: none
!     document%node(k)%i                             -- its value, an int
!
! THE SUBSET, word for word Python's: nested objects, lists, numbers in every
! radix (with '_' as a visual helper, and roman '0rIV'), booleans
! (true/false/yes/no), the spellings of nothing (null/nil/none/nihil), '#'
! and '//' comments, '=' or ':' before a value, a brace directly after a key.
! A STRING VALUE IS WRITTEN IN DOUBLE QUOTES; a text of several lines in
! triple quotes, laid out as 'inspect.cleandoc' lays it out. 'include',
! '${...}' and '+=' are refused by name. The fault messages are Python's,
! character for character.
!
! THE TREE IS AN ARENA: every node stands in ONE array, 'document%node', and
! a list or an object holds its children as POSITIONS in it ('child'). An
! object's child carries the key it is bound to ('key', 'key_position') --
! Python's Entry is the child itself. The kind of a node ('kind') and of a
! scalar's value ('value_kind') are integers; a scalar holds its value in
! the component of its kind ('b', 'i', 'f', 's'). Indices, not pointers: an
! array grows without invalidating one, and nothing is freed node by node.
!
! THE PARSE NEVER RAISES: faults accumulate and the parse recovers at the
! next line. AND IT ENDS: a parse that walks far longer than its text could
! need is stopped -- the text treated as ended -- and says so in 'hung'.
! Python bounds the fuzz's parse by a timer; Fortran has no signal to raise
! one with, and the bound is the parser's own, deterministic.
! _____________________________________________________________________________
module hwut_hocon
    use, intrinsic :: iso_fortran_env, only: int64, real64
    use hwut_text
    use hwut_pytext, only: float_repr, str_repr, bool_text
    implicit none
    private

    public :: parse, cleandoc, Position, ParseFault, SourceLine, HoconNode, HoconDocument
    public :: FAULT_SYNTAX, FAULT_REFUSED, SCALAR_NODE, LIST_NODE, OBJECT_NODE
    public :: VALUE_NULL, VALUE_BOOL, VALUE_INT, VALUE_FLOAT, VALUE_STR

    integer, parameter :: FAULT_SYNTAX = 1, FAULT_REFUSED = 2
    integer, parameter :: SCALAR_NODE = 1, LIST_NODE = 2, OBJECT_NODE = 3
    integer, parameter :: VALUE_NULL = 0, VALUE_BOOL = 1, VALUE_INT = 2, VALUE_FLOAT = 3, VALUE_STR = 4
    integer, parameter :: NOT_A_TOKEN = -1
    character,    parameter :: NONE = achar(0)          ! beyond the last line
    character(*), parameter :: TRIPLE_QUOTE = '"""'

    type :: Position                     ! one place in one file; 1-based
        integer :: line   = 1
        integer :: column = 1
    contains
        procedure :: str => position_str
    end type

    type :: ParseFault
        integer                   :: kind = FAULT_SYNTAX
        character(:), allocatable :: file
        type(Position)            :: position
        character(:), allocatable :: message
    contains
        procedure :: str => fault_str
    end type

    type :: SourceLine                   ! 'column_offset': removed before 'text'
        character(:), allocatable :: text
        integer                   :: line          = 1
        integer                   :: column_offset = 0
    end type

    type :: HoconNode
        integer                   :: kind       = SCALAR_NODE
        type(Position)            :: position
        character(:), allocatable :: key                    ! an object's child: its key
        type(Position)            :: key_position
        integer                   :: value_kind = VALUE_NULL
        logical                   :: b          = .false.
        integer(int64)            :: i          = 0
        real(real64)              :: f          = 0
        character(:), allocatable :: s
        integer, allocatable      :: child(:)               ! a list's items, an object's entries
    contains
        procedure :: value_repr => node_value_repr
        procedure :: type_name  => node_type_name
    end type

    type :: HoconDocument
        type(HoconNode), allocatable :: node(:)
        integer                      :: node_n = 0
        integer                      :: root   = 0
    contains
        procedure :: get  => document_get
        procedure :: keys => document_keys
    end type

    type :: Parser                       ! the cursor, and what the parse built
        type(SourceLine), allocatable :: line_list(:)
        integer                       :: line_n = 0, i_line = 1, i_col = 0     ! i_col: 0-based
        character(:), allocatable     :: text, file
        type(HoconDocument)           :: document
        type(ParseFault), allocatable :: fault(:)
        integer                       :: fault_n = 0, step_n = 0, step_max = 0
        logical                       :: hung_f = .false.
    end type

contains

    ! ============================================================ the records
    function position_str(self) result(text)
        ! RETURN: 'line:column'.
        class(Position), intent(in) :: self
        character(:), allocatable   :: text
        text = str(self%line) // ":" // str(self%column)
    end function

    function fault_str(self) result(text)
        ! RETURN: 'file:line:column: KIND: message'.
        class(ParseFault), intent(in) :: self
        character(:), allocatable     :: text
        text = self%file // ":" // self%position%str() // ": " &
               // trim(merge("SYNTAX ", "REFUSED", self%kind == FAULT_SYNTAX)) // ": " // self%message
    end function

    function node_value_repr(self) result(text)
        ! RETURN: the scalar's value as Python's '%r' prints it.
        class(HoconNode), intent(in) :: self
        character(:), allocatable    :: text
        select case( self%value_kind )
        case( VALUE_BOOL );  text = bool_text(self%b)
        case( VALUE_INT );   text = str(self%i)
        case( VALUE_FLOAT ); text = float_repr(self%f)
        case( VALUE_STR );   text = str_repr(self%s)
        case default;        text = "None"
        end select
    end function

    function node_type_name(self) result(text)
        ! RETURN: the name Python's 'type(value).__name__' gives the scalar's
        !         value: 'str', 'int', 'float', 'bool', 'NoneType'.
        class(HoconNode), intent(in) :: self
        character(:), allocatable    :: text
        select case( self%value_kind )
        case( VALUE_BOOL );  text = "bool"
        case( VALUE_INT );   text = "int"
        case( VALUE_FLOAT ); text = "float"
        case( VALUE_STR );   text = "str"
        case default;        text = "NoneType"
        end select
    end function

    integer function document_get(self, object, key) result(k)
        ! RETURN: the position of the entry 'key' of the object at position
        !         'object'; 0, no such entry.
        class(HoconDocument), intent(in) :: self
        integer, intent(in)              :: object
        character(*), intent(in)         :: key
        integer                          :: i
        do i = 1, size(self%node(object)%child)
            k = self%node(object)%child(i)
            if( len(self%node(k)%key) /= len(key) ) cycle
            if( self%node(k)%key == key ) return
        end do
        k = 0
    end function

    function document_keys(self, object) result(list)
        ! RETURN: the keys of the object at position 'object', in written
        !         order.
        class(HoconDocument), intent(in) :: self
        integer, intent(in)              :: object
        type(string), allocatable        :: list(:)
        integer                          :: i
        allocate(list(0))
        do i = 1, size(self%node(object)%child)
            call push(list, self%node(self%node(object)%child(i))%key)
        end do
    end function

    ! =========================================================== the building
    integer function new_node(p, kind, at) result(k)
        ! RETURN: the position of a new node of 'kind' at 'at' in the arena
        !         -- which doubles where it is full.
        type(Parser), intent(inout)  :: p
        integer, intent(in)          :: kind
        type(Position), intent(in)   :: at
        type(HoconNode), allocatable :: grown(:)
        integer                      :: n
        n = size(p%document%node)
        if( p%document%node_n == n ) then
            allocate(grown(max(16, 2 * n)))
            grown(1:n) = p%document%node(1:n)
            call move_alloc(grown, p%document%node)
        end if
        p%document%node_n = p%document%node_n + 1
        k = p%document%node_n
        p%document%node(k)%kind     = kind
        p%document%node(k)%position = at
        allocate(p%document%node(k)%child(0))
    end function

    subroutine add_fault(p, kind, at, message)
        ! RETURN: nothing; one fault more stands at the end of the list.
        type(Parser), intent(inout)   :: p
        integer, intent(in)           :: kind
        type(Position), intent(in)    :: at
        character(*), intent(in)      :: message
        type(ParseFault), allocatable :: grown(:)
        if( p%fault_n == size(p%fault) ) then
            allocate(grown(max(8, 2 * p%fault_n)))
            grown(1:p%fault_n) = p%fault(1:p%fault_n)
            call move_alloc(grown, p%fault)
        end if
        p%fault_n = p%fault_n + 1
        p%fault(p%fault_n)%kind     = kind
        p%fault(p%fault_n)%file     = p%file
        p%fault(p%fault_n)%position = at
        p%fault(p%fault_n)%message  = message
    end subroutine

    ! ============================================================= the cursor
    logical function at_end(p)
        ! RETURN: .true., no character remains; .false. else.
        type(Parser), intent(in) :: p
        at_end = p%i_line > p%line_n
    end function

    character function peek(p, ahead)
        ! RETURN: the character 'ahead' places from here on this line; NL at
        !         the line's end; NONE beyond the last line.
        type(Parser), intent(in) :: p
        integer, intent(in)      :: ahead
        integer                  :: i
        peek = NONE
        if( at_end(p) ) return
        i = p%i_col + ahead
        if( i < len(p%text) ) then
            peek = p%text(i + 1:i + 1)
        else
            peek = NL
        end if
    end function

    subroutine skip(p, n)
        ! RETURN: nothing; 'n' characters WITHIN the line are stepped over.
        type(Parser), intent(inout) :: p
        integer, intent(in)         :: n
        p%i_col = p%i_col + n
    end subroutine

    subroutine skip_line(p)
        ! RETURN: nothing; the cursor stands at the beginning of the next line.
        type(Parser), intent(inout) :: p
        p%i_line = p%i_line + 1
        p%i_col  = 0
        if( p%i_line <= p%line_n ) then
            p%text = p%line_list(p%i_line)%text
        else
            p%text = ""
        end if
    end subroutine

    function here(p) result(at)
        ! RETURN: the file-relative position of the character at the cursor
        !         -- after the last line's end where every line is read.
        type(Parser), intent(in) :: p
        type(Position)           :: at
        if( at_end(p) ) then
            if( p%line_n == 0 ) return
            at%line   = p%line_list(p%line_n)%line
            at%column = p%line_list(p%line_n)%column_offset + len(p%line_list(p%line_n)%text) + 1
            return
        end if
        at%line   = p%line_list(p%i_line)%line
        at%column = p%line_list(p%i_line)%column_offset + p%i_col + 1
    end function

    function shown(c) result(text)
        ! RETURN: the character 'c' as Python's 'c.strip()' leaves it: ''
        !         for white space and for nothing.
        character, intent(in)     :: c
        character(:), allocatable :: text
        text = strip(c)
        if( c == NONE ) text = ""
    end function

    ! ====================================================== characters, runs
    pure logical function space_f(c)
        ! RETURN: .true. for what Python's '\s' is among the ASCII characters.
        character, intent(in) :: c
        integer               :: k
        k = iachar(c)
        space_f = c == " " .or. (k >= 9 .and. k <= 13) .or. (k >= 28 .and. k <= 31)
    end function

    pure integer function token_length(text, i) result(n)
        ! RETURN: the length of the run '[^\s{}\[\]=,:"#]*' beginning at the
        !         0-based 'i' of 'text' -- 0 where 'i' is at or past its end.
        character(*), intent(in) :: text
        integer, intent(in)      :: i
        integer                  :: k
        k = i + 1
        do while( k <= len(text) )
            if( space_f(text(k:k)) .or. index('{}[]=,:"#', text(k:k)) > 0 ) exit
            k = k + 1
        end do
        n = max(0, k - 1 - i)
    end function

    pure integer function blank_end(text, i) result(k)
        ! RETURN: the 0-based index of the first character at or after 'i'
        !         that is no blank.
        character(*), intent(in) :: text
        integer, intent(in)      :: i
        k = i
        do while( k < len(text) )
            if( text(k + 1:k + 1) /= " " .and. text(k + 1:k + 1) /= TAB ) exit
            k = k + 1
        end do
    end function

    logical function comment_at(text, i)
        ! RETURN: .true. where a comment ('#', '//') begins at the 0-based
        !         'i' of 'text'; .false. else.
        character(*), intent(in) :: text
        integer, intent(in)      :: i
        comment_at = .false.
        if( i >= len(text) ) return
        if( text(i + 1:i + 1) == "#" ) then
            comment_at = .true.
        else if( i + 1 < len(text) ) then
            comment_at = text(i + 1:i + 2) == "//"
        end if
    end function

    subroutine skip_space(p)
        ! RETURN: nothing; blanks and a comment on the current line were
        !         skipped.
        type(Parser), intent(inout) :: p
        p%i_col = blank_end(p%text, p%i_col)
        if( comment_at(p%text, p%i_col) ) call skip_line(p)
    end subroutine

    subroutine skip_blank(p)
        ! RETURN: nothing; blanks, newlines, commas and comments were skipped.
        !         THE BOUND: past 'step_max' calls the text counts as ended
        !         and 'hung_f' says so.
        type(Parser), intent(inout) :: p
        integer                     :: i
        p%step_n = p%step_n + 1
        if( p%step_n > p%step_max ) then
            p%hung_f = .true.
            p%i_line = p%line_n + 1
            p%text   = ""
            return
        end if
        do while( p%i_line <= p%line_n )
            i = p%i_col
            do while( i < len(p%text) )
                if( index(" " // TAB // ",", p%text(i + 1:i + 1)) == 0 ) exit
                i = i + 1
            end do
            if( i >= len(p%text) ) then
                call skip_line(p)
                cycle
            end if
            p%i_col = i
            if( comment_at(p%text, i) ) then
                call skip_line(p)
                cycle
            end if
            return
        end do
    end subroutine

    ! ============================================================ the numbers
    pure integer function digit_run(s, i) result(n)
        ! RETURN: the length of '[0-9](?:_?[0-9])*' at the 1-based 'i' of
        !         's'; 0 where none.
        character(*), intent(in) :: s
        integer, intent(in)      :: i
        integer                  :: k
        n = 0
        if( i > len(s) ) return
        if( .not. digit_f(s(i:i)) ) return
        k = i + 1
        do
            if( k <= len(s) ) then
                if( digit_f(s(k:k)) ) then
                    k = k + 1; cycle
                end if
            end if
            if( k + 1 <= len(s) ) then
                if( s(k:k) == "_" .and. digit_f(s(k + 1:k + 1)) ) then
                    k = k + 2; cycle
                end if
            end if
            exit
        end do
        n = k - i
    end function

    pure logical function digit_f(c)
        ! RETURN: .true. for '0' .. '9'.
        character, intent(in) :: c
        digit_f = c >= "0" .and. c <= "9"
    end function

    pure logical function decimal_f(s)
        ! RETURN: .true. where 's' matches Python's '_DECIMAL_RE' whole:
        !         [-+]? (digits ('.' digits?)? | '.' digits) ([eE] [-+]? digits)?
        character(*), intent(in) :: s
        integer                  :: i, d, k
        decimal_f = .false.
        i = 1
        if( i <= len(s) ) then
            if( s(i:i) == "+" .or. s(i:i) == "-" ) i = i + 1
        end if
        d = digit_run(s, i)
        if( d > 0 ) then
            i = i + d
            if( i <= len(s) ) then
                if( s(i:i) == "." ) then
                    i = i + 1
                    i = i + digit_run(s, i)
                end if
            end if
        else
            if( i > len(s) ) return
            if( s(i:i) /= "." ) return
            d = digit_run(s, i + 1)
            if( d == 0 ) return
            i = i + 1 + d
        end if
        if( i <= len(s) ) then
            if( s(i:i) == "e" .or. s(i:i) == "E" ) then
                k = i + 1
                if( k <= len(s) ) then
                    if( s(k:k) == "+" .or. s(k:k) == "-" ) k = k + 1
                end if
                d = digit_run(s, k)
                if( d == 0 ) return
                i = k + d
            end if
        end if
        decimal_f = i == len(s) + 1
    end function

    pure function roman_of(value) result(text)
        ! RETURN: the canonical roman numeral of 1 <= 'value' <= 3999.
        integer, intent(in)       :: value
        character(:), allocatable :: text
        character(4), parameter   :: DIGIT(0:9, 3) = reshape([character(4) :: &
            "", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", &
            "", "X", "XX", "XXX", "XL", "L", "LX", "LXX", "LXXX", "XC", &
            "", "C", "CC", "CCC", "CD", "D", "DC", "DCC", "DCCC", "CM"], [10, 3])
        text = repeat("M", value / 1000) // trim(DIGIT(mod(value / 100, 10), 3)) &
               // trim(DIGIT(mod(value / 10, 10), 2)) // trim(DIGIT(mod(value, 10), 1))
    end function

    pure integer function roman(text) result(total)
        ! RETURN: the number the roman numeral 'text' spells; NOT_A_TOKEN,
        !         the text is no roman numeral -- 'IIII' and 'VX' among them.
        !         Python's regular expression admits exactly the CANONICAL
        !         numerals of 1 .. 3999: so a text is one where it is the
        !         numeral its own value writes back to.
        character(*), intent(in) :: text
        integer                  :: k, value, previous
        total = NOT_A_TOKEN
        if( len(text) == 0 .or. verify(text, "IVXLCDM") /= 0 ) return
        total    = 0
        previous = 0
        do k = len(text), 1, -1
            select case( text(k:k) )
            case( "I" ); value = 1
            case( "V" ); value = 5
            case( "X" ); value = 10
            case( "L" ); value = 50
            case( "C" ); value = 100
            case( "D" ); value = 500
            case default; value = 1000
            end select
            if( value < previous ) then
                total = total - value
            else
                total = total + value
            end if
            previous = max(previous, value)
        end do
        if( total < 1 .or. total > 3999 ) then
            total = NOT_A_TOKEN
        else if( roman_of(total) /= text .or. len(roman_of(total)) /= len(text) ) then
            total = NOT_A_TOKEN
        end if
    end function

    logical function without_helper(text, digit_set, digits) result(ok_f)
        ! RETURN: .true., 'digits' is 'text' with every '_' removed; .false.,
        !         the text carries no digit, a character no digit of the
        !         radix, or an '_' that separates nothing.
        character(*), intent(in)               :: text, digit_set
        character(:), allocatable, intent(out) :: digits
        ok_f   = .false.
        digits = ""
        if( len(text) == 0 ) return
        if( text(1:1) == "_" .or. text(len(text):len(text)) == "_" .or. index(text, "__") > 0 ) return
        digits = replace_all(text, "_", "")
        if( len(digits) == 0 .or. verify(digits, digit_set) /= 0 ) return
        ok_f = .true.
    end function

    integer function number(raw, i_value, f_value) result(kind)
        ! RETURN: VALUE_INT or VALUE_FLOAT, the number 'raw' spells in
        !         whatever radix it spells it ('_' enters no value), in
        !         'i_value' or 'f_value'; NOT_A_TOKEN, it spells no number.
        !         An integer beyond 64 bits saturates (Python's has none).
        character(*), intent(in)    :: raw
        integer(int64), intent(out) :: i_value
        real(real64), intent(out)   :: f_value
        character(:), allocatable   :: body, digits, set
        integer(int64)              :: sign, d, radix
        integer                     :: k, ios, v
        i_value = 0
        f_value = 0
        kind    = NOT_A_TOKEN
        body    = raw
        sign    = 1
        if( len(raw) > 0 ) then
            if( raw(1:1) == "+" .or. raw(1:1) == "-" ) body = raw(2:)
            if( raw(1:1) == "-" ) sign = -1
        end if
        if( len(body) >= 2 ) then
            select case( body(1:2) )
            case( "0r", "0R" )
                v = roman(body(3:))
                if( v == NOT_A_TOKEN ) return
                i_value = sign * v
                kind    = VALUE_INT
                return
            case( "0x", "0X", "0b", "0B", "0o", "0O" )
                select case( body(2:2) )
                case( "x", "X" ); radix = 16; set = "0123456789abcdefABCDEF"
                case( "b", "B" ); radix = 2;  set = "01"
                case default;     radix = 8;  set = "01234567"
                end select
                if( .not. without_helper(body(3:), set, digits) ) return
                do k = 1, len(digits)
                    d = index("0123456789abcdef", achar(ior(iachar(digits(k:k)), 32))) - 1   ! 'A' -> 'a'
                    if( i_value > (huge(i_value) - d) / radix ) then
                        i_value = huge(i_value)
                    else
                        i_value = i_value * radix + d
                    end if
                end do
                i_value = sign * i_value
                kind    = VALUE_INT
                return
            end select
        end if
        if( .not. decimal_f(raw) ) return
        digits = replace_all(raw, "_", "")
        if( scan(digits, ".eE") > 0 ) then
            read(digits, *, iostat = ios) f_value             ! too large: Infinity, as Python
            kind = VALUE_FLOAT
        else
            read(digits, *, iostat = ios) i_value
            if( ios /= 0 ) i_value = sign * huge(i_value)
            kind = VALUE_INT
        end if
    end function

    ! ============================================================== strings
    function cleandoc(text) result(cleaned)
        ! RETURN: 'text' laid out as Python's 'inspect.cleandoc': tabs
        !         expanded, the blank indentation common to the lines after
        !         the first removed, the first line's leading blanks removed,
        !         empty lines at both ends dropped.
        character(*), intent(in)  :: text
        character(:), allocatable :: cleaned, expanded
        type(string), allocatable :: line(:)
        character(:), allocatable :: held
        integer                   :: i, column, margin, indent, first, last
        expanded = ""
        column   = 0
        do i = 1, len(text)
            if( text(i:i) == TAB ) then
                expanded = expanded // repeat(" ", 8 - mod(column, 8))
                column   = column + 8 - mod(column, 8)
            else
                expanded = expanded // text(i:i)
                column   = column + 1
                if( text(i:i) == NL .or. text(i:i) == achar(13) ) column = 0
            end if
        end do
        line   = split_lines(expanded)
        margin = huge(margin)
        do i = 2, size(line)
            indent = verify(line(i)%s, " ") - 1
            if( indent >= 0 ) margin = min(margin, indent)    ! a line with content
        end do
        indent = verify(line(1)%s, " ")
        if( indent == 0 ) then
            line(1)%s = ""
        else
            held      = line(1)%s(indent:)          ! not in place: a text and its own part
            line(1)%s = held
        end if
        if( margin < huge(margin) ) then
            do i = 2, size(line)
                held      = line(i)%s(min(margin, len(line(i)%s)) + 1:)
                line(i)%s = held
            end do
        end if
        last = size(line)
        do while( last >= 1 )
            if( len(line(last)%s) > 0 ) exit
            last = last - 1
        end do
        first = 1
        do while( first <= last )
            if( len(line(first)%s) > 0 ) exit
            first = first + 1
        end do
        cleaned = join(line(first:last), NL)
    end function

    logical function parse_triple_quoted(p, value) result(ok_f)
        ! RETURN: .true., 'value' is the text between three double quotes
        !         and the next three, over as many lines as it takes, AS
        !         WRITTEN and laid out by 'cleandoc'; .false., no closing
        !         three quotes stand before the end (fault recorded).
        type(Parser), intent(inout)            :: p
        character(:), allocatable, intent(out) :: value
        type(Position)                         :: begin
        type(string), allocatable              :: piece(:)
        integer                                :: k, from
        begin = here(p)
        call skip(p, 3)
        allocate(piece(0))
        ok_f = .false.
        do while( .not. at_end(p) )
            from = min(p%i_col, len(p%text))
            k    = index(p%text(from + 1:), TRIPLE_QUOTE)
            if( k > 0 ) then
                call push(piece, p%text(from + 1:from + k - 1))
                p%i_col = from + k - 1 + 3
                value   = cleandoc(join(piece, NL))
                ok_f    = .true.
                return
            end if
            call push(piece, p%text(from + 1:))
            call skip_line(p)
        end do
        call add_fault(p, FAULT_SYNTAX, begin, "unterminated triple-quoted string: closing '" // TRIPLE_QUOTE // "' missing")
    end function

    logical function parse_quoted(p, value) result(ok_f)
        ! RETURN: .true., 'value' is the string's content, escapes resolved;
        !         .false., the string is unterminated at its line's end
        !         (fault recorded).
        type(Parser), intent(inout)            :: p
        character(:), allocatable, intent(out) :: value
        type(Position)                         :: begin
        integer                                :: i
        character                              :: c, escaped
        begin = here(p)
        value = ""
        i     = p%i_col + 1                     ! 0-based, past the opening quote
        do
            if( i >= len(p%text) ) then
                call add_fault(p, FAULT_SYNTAX, begin, "unterminated string")
                p%i_col = i
                ok_f    = .false.
                return
            end if
            c = p%text(i + 1:i + 1)
            if( c == '"' ) then
                p%i_col = i + 1
                ok_f    = .true.
                return
            else if( c == "\" ) then
                i = i + 1
                if( i < len(p%text) ) then
                    escaped = p%text(i + 1:i + 1)
                    select case( escaped )
                    case( "n" );  value = value // NL
                    case( "t" );  value = value // TAB
                    case default; value = value // escaped
                    end select
                end if
                i = i + 1
            else
                value = value // c
                i     = i + 1
            end if
        end do
    end function

    ! =============================================================== values
    integer function scalar(p, kind, at) result(k)
        ! RETURN: the position of a new scalar node of the value 'kind' at
        !         'at'.
        type(Parser), intent(inout) :: p
        integer, intent(in)         :: kind
        type(Position), intent(in)  :: at
        k = new_node(p, SCALAR_NODE, at)
        p%document%node(k)%value_kind = kind
    end function

    logical function parse_key(p, key) result(ok_f)
        ! RETURN: .true., 'key' is the key standing here; .false., none
        !         stands here (fault recorded).
        type(Parser), intent(inout)            :: p
        character(:), allocatable, intent(out) :: key
        integer                                :: n
        if( peek(p, 0) == '"' ) then
            ok_f = parse_quoted(p, key)
            return
        end if
        n = token_length(p%text, p%i_col)
        if( n == 0 ) then
            call add_fault(p, FAULT_SYNTAX, here(p), "expected a key, found '" // shown(peek(p, 0)) // "'")
            ok_f = .false.
            return
        end if
        key  = p%text(p%i_col + 1:p%i_col + n)
        call skip(p, n)
        ok_f = .true.
    end function

    integer function parse_bare(p, at, in_list_f) result(k)
        ! RETURN: the position of the scalar of the bare token here -- a
        !         boolean, a number, a spelling of nothing; 0, the token is
        !         none of those (fault recorded): a string value is written in
        !         double quotes.
        type(Parser), intent(inout) :: p
        type(Position), intent(in)  :: at
        logical, intent(in)         :: in_list_f
        character(:), allocatable   :: raw, after
        integer(int64)              :: i_value
        real(real64)                :: f_value
        integer                     :: from, n, kind, cut

        n   = token_length(p%text, p%i_col)
        raw = p%text(min(p%i_col, len(p%text)) + 1:min(p%i_col, len(p%text)) + n)
        k   = 0

        ! A SIGN STANDING APART from its digits: '- 0.12'. The two must make
        ! ONE number: '- -1.5e3' does not ('--1.5e3' spells none).
        if( raw == "+" .or. raw == "-" ) then
            if( len(raw) == 1 ) then
                from  = blank_end(p%text, p%i_col + 1)
                n     = token_length(p%text, from)
                after = p%text(min(from, len(p%text)) + 1:min(from, len(p%text)) + n)
                if( len(after) > 0 ) then
                    if( number(after, i_value, f_value) /= NOT_A_TOKEN ) then
                        kind = number(raw // after, i_value, f_value)
                        if( kind /= NOT_A_TOKEN ) then
                            p%i_col = from + len(after)
                            k = scalar(p, kind, at)
                            p%document%node(k)%i = i_value
                            p%document%node(k)%f = f_value
                            return
                        end if
                    end if
                end if
            end if
        end if
        if( starts_with(raw, "${") ) then
            call add_fault(p, FAULT_REFUSED, here(p), "substitutions '${...}' do not exist here")
            call skip_line(p)
            return
        end if
        cut = index(raw, "//")
        if( cut > 0 ) raw = raw(:cut - 1)
        call skip(p, len(raw))

        if( len(raw) == 0 ) then
            if( in_list_f ) then
                call add_fault(p, FAULT_SYNTAX, at, "expected a value, found '" // shown(peek(p, 0)) // "'")
                return
            end if
            k = scalar(p, VALUE_NULL, at)                  ! an empty value is null
            return
        end if
        select case( raw )
        case( "null", "nil", "none", "nihil" )
            k = scalar(p, VALUE_NULL, at)
        case( "true", "yes", "false", "no" )
            k = scalar(p, VALUE_BOOL, at)
            p%document%node(k)%b = raw == "true" .or. raw == "yes"
        case default
            kind = number(raw, i_value, f_value)
            if( kind == NOT_A_TOKEN ) then
                call add_fault(p, FAULT_SYNTAX, at, 'a string is written in double quotes: "' // raw // '"')
                return
            end if
            k = scalar(p, kind, at)
            p%document%node(k)%i = i_value
            p%document%node(k)%f = f_value
        end select
    end function

    recursive integer function parse_list(p, at) result(k)
        ! RETURN: the position of the list of the items up to ']'.
        type(Parser), intent(inout) :: p
        type(Position), intent(in)  :: at
        integer                     :: item, line, column
        character                   :: c
        k = new_node(p, LIST_NODE, at)
        do
            call skip_blank(p)
            if( at_end(p) ) then
                call add_fault(p, FAULT_SYNTAX, here(p), "unterminated list: ']' missing")
                exit
            end if
            c = peek(p, 0)
            if( c == "]" ) then
                call skip(p, 1)
                exit
            else if( c == "," ) then
                call skip(p, 1)
            else if( c == "}" ) then
                ! A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' forgotten.
                call add_fault(p, FAULT_SYNTAX, here(p), "unterminated list: ']' missing before '}'")
                exit
            else
                line   = p%i_line
                column = p%i_col
                item   = parse_value(p, .true.)
                if( item > 0 ) then
                    p%document%node(k)%child = [p%document%node(k)%child, item]
                else if( p%i_line == line .and. p%i_col == column ) then
                    call skip(p, 1)           ! NOTHING CONSUMED: step over what was refused
                end if
            end if
        end do
    end function

    recursive integer function parse_value(p, in_list_f) result(k)
        ! RETURN: the position of the value here -- a scalar, a list or an
        !         object; 0, nothing usable stands here (fault recorded).
        !         'in_list_f': an empty value is a fault, not null.
        type(Parser), intent(inout) :: p
        logical, intent(in)         :: in_list_f
        type(Position)              :: at
        character(:), allocatable   :: value
        character                   :: c
        logical                     :: ok_f
        call skip_space(p)
        at = here(p)
        c  = peek(p, 0)
        k  = 0
        if( c == "{" ) then
            call skip(p, 1)
            k = parse_body(p, "}")
        else if( c == "[" ) then
            call skip(p, 1)
            k = parse_list(p, at)
        else if( c == '"' ) then
            if( peek(p, 1) == '"' .and. peek(p, 2) == '"' ) then
                ok_f = parse_triple_quoted(p, value)
            else
                ok_f = parse_quoted(p, value)
            end if
            if( .not. ok_f ) return
            k = scalar(p, VALUE_STR, at)
            p%document%node(k)%s = value
        else if( c == "$" .and. peek(p, 1) == "{" ) then
            call add_fault(p, FAULT_REFUSED, at, "substitutions '${...}' do not exist here: a specification " &
                                                 // "refers to nothing outside its file")
            call skip_line(p)
        else
            k = parse_bare(p, at, in_list_f)
        end if
    end function

    recursive subroutine parse_entry(p, object)
        ! RETURN: nothing; one 'key = value' pair entered the object at
        !         position 'object', or a fault was recorded and the parse
        !         recovers at the next line.
        type(Parser), intent(inout) :: p
        integer, intent(in)         :: object
        type(Position)              :: key_position, at
        character(:), allocatable   :: key
        character                   :: c
        integer                     :: node
        key_position = here(p)
        if( .not. parse_key(p, key) ) then
            call skip_line(p)
            return
        end if
        if( key == "include" .and. len(key) == 7 ) then
            call add_fault(p, FAULT_REFUSED, key_position, "'include' does not exist here: a specification " &
                                                           // "refers to nothing outside its file")
            call skip_line(p)
            return
        end if
        call skip_space(p)
        c = peek(p, 0)
        if( c == "=" .or. c == ":" ) then
            call skip(p, 1)
            call skip_space(p)
        else if( c == "{" ) then
            continue                                     ! a brace binds without a sign
        else if( c == "+" .and. peek(p, 1) == "=" ) then
            at = here(p)
            call add_fault(p, FAULT_REFUSED, at, "'+=' does not exist here")
            call skip_line(p)
            return
        else
            at = here(p)
            call add_fault(p, FAULT_SYNTAX, at, "expected '=', ':' or '{' after key '" // key // "'")
            call skip_line(p)
            return
        end if
        ! The value parser recovers by itself; a second skip would eat a line.
        node = parse_value(p, .false.)
        if( node == 0 ) return
        if( p%document%get(object, key) /= 0 ) then
            call add_fault(p, FAULT_SYNTAX, key_position, "duplicate key '" // key &
                                                          // "'; the first stands, this one is refused")
            return
        end if
        p%document%node(node)%key          = key
        p%document%node(node)%key_position = key_position
        p%document%node(object)%child      = [p%document%node(object)%child, node]
    end subroutine

    recursive integer function parse_body(p, terminator) result(k)
        ! RETURN: the position of the object of the entries up to
        !         'terminator' -- '}', or NONE for the end of the text.
        type(Parser), intent(inout) :: p
        character, intent(in)       :: terminator
        character                   :: c
        k = new_node(p, OBJECT_NODE, here(p))
        do
            call skip_blank(p)
            if( at_end(p) ) then
                if( terminator /= NONE ) &
                    call add_fault(p, FAULT_SYNTAX, here(p), "unterminated object: '" // terminator // "' missing")
                return
            end if
            c = peek(p, 0)
            if( terminator /= NONE .and. c == terminator ) then
                call skip(p, 1)
                return
            end if
            if( c == "}" ) then
                call add_fault(p, FAULT_SYNTAX, here(p), "unmatched '}'")
                call skip(p, 1)
            else
                call parse_entry(p, k)
            end if
        end do
    end function

    subroutine parse(line_list, file, document, fault_list, hung)
        ! RETURN: nothing; 'document' holds the tree -- 'document%root' the
        !         object of every entry of the outermost level, possibly none
        !         -- and 'fault_list' every fault found, none on a clean
        !         parse. 'file' names the file in the faults. 'hung' is
        !         .true. where the parse was stopped by its bound (see the
        !         head) -- never, for a parser without a fault of its own.
        type(SourceLine), intent(in)               :: line_list(:)
        character(*), intent(in)                   :: file
        type(HoconDocument), intent(out)           :: document
        type(ParseFault), allocatable, intent(out) :: fault_list(:)
        logical, intent(out), optional             :: hung
        type(Parser)                               :: p
        integer                                    :: i, n
        p%line_list = line_list
        p%line_n    = size(line_list)
        p%file      = file
        p%text      = ""
        if( p%line_n > 0 ) p%text = line_list(1)%text
        n = 0
        do i = 1, p%line_n
            n = n + len(line_list(i)%text) + 1
        end do
        p%step_max = 16 * n + 64
        allocate(p%document%node(16), p%fault(8))
        p%document%root = parse_body(p, NONE)
        document   = p%document
        fault_list = p%fault(1:p%fault_n)
        if( present(hung) ) hung = p%hung_f
    end subroutine

end module hwut_hocon
