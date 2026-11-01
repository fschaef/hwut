! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: TEXTS OF ANY LENGTH, AND LISTS OF THEM -- what Python's 'str' and
!         'list[str]' are to the other modules. Fortran's own character
!         variable has ONE length for every element of an array, so a list
!         of texts is an array of 'string', each holding a deferred-length
!         'character(:), allocatable'.
!
!     use hwut_text
!     type(string), allocatable :: list(:)
!     list = [string("beta"), string("alpha")]
!     call sort_strings(list)                    -- by code point, as Python
!     print '(a)', join(list, ", ")              -- 'alpha, beta'
!     print '(a)', str(42)                       -- '42'
!     call say("one line")                       -- on stdout, no leading blank
!
! THE COMPARISON IS PYTHON'S: code point by code point, a text that is a
! prefix of another sorting first. Fortran's '<' pads the shorter text with
! blanks, which would sort 'a' and 'a ' as equal -- 'text_lt' does not.
! _____________________________________________________________________________
module hwut_text
    use, intrinsic :: iso_fortran_env, only: int32, int64, output_unit
    implicit none
    private

    public :: string, str, join, sort_strings, text_lt, text_index, push, say
    public :: strip, starts_with, replace_all, split_lines, char_count, NL, TAB, ESC

    character(*), parameter :: NL  = achar(10)
    character(*), parameter :: TAB = achar(9)
    character(*), parameter :: ESC = achar(27)

    type :: string
        character(:), allocatable :: s
    end type

    interface str
        module procedure str_int32, str_int64
    end interface

    interface push
        module procedure push_text, push_string
    end interface

contains

    pure function str_int32(i) result(text)
        ! RETURN: the decimal text of 'i', a leading '-' where negative and
        !         no blank -- Python's 'str(int)'.
        integer(int32), intent(in) :: i
        character(:), allocatable  :: text
        text = str_int64(int(i, int64))
    end function

    pure function str_int64(i) result(text)
        ! RETURN: the decimal text of 'i', a leading '-' where negative and
        !         no blank -- Python's 'str(int)'.
        integer(int64), intent(in) :: i
        character(:), allocatable  :: text
        character(24)              :: buffer
        write(buffer, '(i0)') i
        text = trim(buffer)
    end function

    pure function join(list, separator) result(text)
        ! RETURN: the texts of 'list' one after the other, 'separator'
        !         between two; '' for an empty list -- Python's
        !         'separator.join(list)'.
        type(string), intent(in)  :: list(:)
        character(*), intent(in)  :: separator
        character(:), allocatable :: text
        integer                   :: i
        text = ""
        do i = 1, size(list)
            if( i > 1 ) text = text // separator
            text = text // list(i)%s
        end do
    end function

    pure logical function text_lt(a, b)
        ! RETURN: .true. where 'a' sorts before 'b' by code point, a prefix
        !         first -- Python's '<' on str; .false., else.
        character(*), intent(in) :: a, b
        integer                  :: i
        do i = 1, min(len(a), len(b))
            if( a(i:i) /= b(i:i) ) then
                text_lt = iachar(a(i:i)) < iachar(b(i:i))
                return
            end if
        end do
        text_lt = len(a) < len(b)
    end function

    pure subroutine sort_strings(list)
        ! RETURN: nothing; 'list' is sorted by 'text_lt', equal texts keeping
        !         their order (an insertion sort: the lists are short).
        type(string), intent(inout) :: list(:)
        type(string)                :: held
        integer                     :: i, j
        do i = 2, size(list)
            held = list(i)
            j    = i - 1
            do while( j >= 1 )
                if( .not. text_lt(held%s, list(j)%s) ) exit
                list(j + 1) = list(j)
                j = j - 1
            end do
            list(j + 1) = held
        end do
    end subroutine

    pure integer function text_index(list, text)
        ! RETURN: the position of the first element of 'list' equal to
        !         'text' (lengths compared too); 0 where none is.
        type(string), intent(in) :: list(:)
        character(*), intent(in) :: text
        integer                  :: i
        do i = 1, size(list)
            if( len(list(i)%s) == len(text) ) then
                if( list(i)%s == text ) then
                    text_index = i
                    return
                end if
            end if
        end do
        text_index = 0
    end function

    pure subroutine push_text(list, text)
        ! RETURN: nothing; 'text' stands at the end of 'list', which is
        !         allocated where it was not -- Python's 'append'.
        type(string), allocatable, intent(inout) :: list(:)
        character(*), intent(in)                 :: text
        type(string), allocatable                :: grown(:)
        integer                                  :: n
        ! NOT 'list = [list, string(text)]': gfortran 13 builds a structure
        ! constructor of a text whose length is not a constant wrongly inside
        ! an array constructor (valgrind: writes beyond the block).
        n = 0
        if( allocated(list) ) n = size(list)
        allocate(grown(n + 1))
        if( n > 0 ) grown(1:n) = list
        grown(n + 1)%s = text
        call move_alloc(grown, list)
    end subroutine

    pure subroutine push_string(list, element)
        ! RETURN: nothing; 'element' stands at the end of 'list'.
        type(string), allocatable, intent(inout) :: list(:)
        type(string), intent(in)                 :: element
        call push_text(list, element%s)
    end subroutine

    subroutine say(text)
        ! RETURN: nothing; 'text' and a newline are written on stdout --
        !         Python's 'print(text)', no blank put before it.
        character(*), intent(in) :: text
        write(output_unit, '(a)') text
    end subroutine

    pure function strip(text) result(stripped)
        ! RETURN: 'text' without the white space (blank, \t \n \v \f \r) at
        !         both its ends -- Python's 'str.strip()'.
        character(*), intent(in)  :: text
        character(:), allocatable :: stripped
        integer                   :: first, last
        first = 1
        last  = len(text)
        do while( first <= last )
            if( .not. white_f(text(first:first)) ) exit
            first = first + 1
        end do
        do while( last >= first )
            if( .not. white_f(text(last:last)) ) exit
            last = last - 1
        end do
        stripped = text(first:last)
    end function

    pure logical function white_f(c)
        ! RETURN: .true. where 'c' is white space for 'strip'; .false. else.
        character, intent(in) :: c
        white_f = c == " " .or. (iachar(c) >= 9 .and. iachar(c) <= 13)
    end function

    pure logical function starts_with(text, prefix)
        ! RETURN: .true. where 'text' begins with 'prefix'; .false. else.
        character(*), intent(in) :: text, prefix
        starts_with = .false.
        if( len(text) < len(prefix) ) return
        starts_with = text(1:len(prefix)) == prefix
    end function

    pure function replace_all(text, old, new) result(replaced)
        ! RETURN: 'text' with every 'old' (not empty) replaced by 'new',
        !         left to right -- Python's 'str.replace'.
        character(*), intent(in)  :: text, old, new
        character(:), allocatable :: replaced
        integer                   :: i, k
        replaced = ""
        i        = 1
        do
            k = index(text(i:), old)
            if( k == 0 ) exit
            replaced = replaced // text(i:i + k - 2) // new
            i        = i + k - 1 + len(old)
        end do
        replaced = replaced // text(i:)
    end function

    pure function split_lines(text) result(list)
        ! RETURN: the pieces of 'text' between newlines -- an ending newline
        !         gives a last, empty piece; '' gives one empty piece --
        !         Python's 'text.split("\n")'.
        character(*), intent(in)  :: text
        type(string), allocatable :: list(:)
        integer                   :: i, k
        allocate(list(0))
        i = 1
        do
            k = index(text(i:), NL)
            if( k == 0 ) exit
            call push(list, text(i:i + k - 2))
            i    = i + k
        end do
        call push(list, text(i:))
    end function

    pure integer function char_count(text)
        ! RETURN: the number of CHARACTERS of the UTF-8 'text' -- what
        !         Python's 'len(str)' and '%-6s' count, not its bytes.
        character(*), intent(in) :: text
        integer                  :: i
        char_count = 0
        do i = 1, len(text)
            if( iand(iachar(text(i:i)), 192) /= 128 ) char_count = char_count + 1
        end do
    end function

end module hwut_text
