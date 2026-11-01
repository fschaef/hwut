! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: TEXT AS PYTHON PRINTS IT -- so a Fortran test and a Python test of
!          the same module print the same bytes and share one GOOD file by a
!          '.link' (bookkeeper B-32). The twin of 'c/hwut_pytext.c'.
!
!     use hwut_pytext
!     repr(0.1_real64)        '0.1'        the shortest text that reads back;
!     repr(1e-5_real64)       '1e-05'      exponential below 1e-4 and from
!     repr(1e16_real64)       '1e+16'      1e16 on
!     repr("it's")            '"it''s"'    Python's choice of quotes
!     repr(.true.)            'True'
!     bytes_repr(ESC//"[A")   "b'\x1b[A'"
!
! 'repr' is ONE NAME FOR EVERY TYPE, as in Python: a generic interface picks
! the specific function by the argument's type.
!
! THE FLOAT: Fortran's G and ES edit descriptors write as many digits as they
! are told, never the fewest that suffice. The algorithm is the C port's:
! the smallest precision whose 'ES' text reads back to the same double, then
! laid out fixed where the decimal point falls in (-4, 16], exponential else.
! gfortran writes 'ES' correctly rounded and reads correctly rounded, which
! is all the algorithm asks.
! _____________________________________________________________________________
module hwut_pytext
    use, intrinsic :: iso_fortran_env, only: real64
    use, intrinsic :: ieee_arithmetic, only: ieee_is_nan, ieee_is_finite
    use hwut_text, only: str
    implicit none
    private

    public :: repr, bytes_repr, float_repr, str_repr, bool_text

    interface repr
        module procedure float_repr, str_repr, bool_text
    end interface

contains

    function float_repr(x) result(text)
        ! RETURN: 'x' as Python's 'repr(float)' writes it -- the shortest
        !         decimal that reads back to the same double, fixed notation
        !         where the decimal point falls in (-4, 16], exponential
        !         else; 'nan', 'inf', '-inf', '0.0', '-0.0' as Python.
        real(real64), intent(in)  :: x
        character(:), allocatable :: text
        character(48)             :: buffer, fmt
        character(:), allocatable :: digits, sign
        real(real64)              :: back
        integer                   :: precision, exponent, point, k, n

        if( ieee_is_nan(x) ) then
            text = "nan"; return
        else if( .not. ieee_is_finite(x) ) then
            text = merge("-inf", " inf", x < 0); text = trim(adjustl(text)); return
        else if( x == 0.0_real64 ) then
            text = merge("-0.0", " 0.0", sign_bit_f(x)); text = trim(adjustl(text)); return
        end if

        do precision = 0, 16
            write(fmt, '(a, i0, a)') "(es40.", precision, "e4)"
            write(buffer, fmt) x
            read(buffer, *) back
            if( back == x ) exit
        end do
        ! buffer: [-]d.[ddd]E[+-]xxxx
        buffer = adjustl(buffer)
        sign   = merge("-", " ", buffer(1:1) == "-")
        sign   = trim(sign)
        k      = len(sign) + 1
        digits = ""
        do while( buffer(k:k) /= "E" )
            if( buffer(k:k) /= "." ) digits = digits // buffer(k:k)
            k = k + 1
        end do
        read(buffer(k + 1:), *) exponent
        n = len(digits)
        do while( n > 1 .and. digits(n:n) == "0" )
            n = n - 1
        end do
        digits = digits(1:n)
        point  = exponent + 1                   ! value = 0.<digits> * 10^point

        if( point > -4 .and. point <= 16 ) then
            if( point <= 0 ) then
                text = sign // "0." // repeat("0", -point) // digits
            else if( point >= n ) then
                text = sign // digits // repeat("0", point - n) // ".0"
            else
                text = sign // digits(1:point) // "." // digits(point + 1:)
            end if
        else
            exponent = point - 1
            text = sign // digits(1:1)
            if( n > 1 ) text = text // "." // digits(2:)
            text = text // "e" // merge("-", "+", exponent < 0)
            if( abs(exponent) < 10 ) text = text // "0"
            text = text // str(abs(exponent))
        end if
    end function

    pure logical function sign_bit_f(x)
        ! RETURN: .true. where the sign bit of 'x' is set -- '-0.0' among
        !         them, which '<' cannot tell from '0.0'; .false. else.
        real(real64), intent(in) :: x
        sign_bit_f = sign(1.0_real64, x) < 0
    end function

    function quoted(s, bytes_f) result(text)
        ! RETURN: 's' in the quotes Python's repr chooses -- single, or
        !         double where it holds a single quote and no double one --
        !         the backslash, that quote and what does not print escaped.
        !         Where 'bytes_f', a 'b' leads and every byte from 0x7f on is
        !         escaped too; a str keeps its UTF-8 as it stands.
        character(*), intent(in)  :: s
        logical, intent(in)       :: bytes_f
        character(:), allocatable :: text
        character                 :: quote
        character(4)              :: hex
        integer                   :: i, c

        quote = "'"
        if( index(s, "'") > 0 .and. index(s, '"') == 0 ) quote = '"'
        text = ""
        if( bytes_f ) text = "b"
        text = text // quote
        do i = 1, len(s)
            c = iachar(s(i:i))
            if( s(i:i) == "\" ) then
                text = text // "\\"
            else if( s(i:i) == quote ) then
                text = text // "\" // quote
            else if( c == 10 ) then
                text = text // "\n"
            else if( c == 9 ) then
                text = text // "\t"
            else if( c == 13 ) then
                text = text // "\r"
            else if( c < 32 .or. c == 127 .or. (bytes_f .and. c >= 128) ) then
                write(hex, '(a, z2.2)') "\x", c
                text = text // to_lower(hex)
            else
                text = text // s(i:i)
            end if
        end do
        text = text // quote
    end function

    pure function to_lower(text) result(lowered)
        ! RETURN: 'text' with every ASCII capital letter made small.
        character(*), intent(in)   :: text
        character(len(text))       :: lowered
        integer                    :: i
        lowered = text
        do i = 1, len(text)
            if( text(i:i) >= "A" .and. text(i:i) <= "Z" ) lowered(i:i) = achar(iachar(text(i:i)) + 32)
        end do
    end function

    function str_repr(text) result(r)
        ! RETURN: the UTF-8 'text' as Python's 'repr(str)' writes it.
        character(*), intent(in)  :: text
        character(:), allocatable :: r
        r = quoted(text, .false.)
    end function

    function bytes_repr(data) result(r)
        ! RETURN: the bytes of 'data' as Python's 'repr(bytes)' writes them.
        character(*), intent(in)  :: data
        character(:), allocatable :: r
        r = quoted(data, .true.)
    end function

    function bool_text(value) result(r)
        ! RETURN: 'True' where 'value', 'False' else -- Python's 'repr(bool)'.
        logical, intent(in)       :: value
        character(:), allocatable :: r
        if( value ) then
            r = "True"
        else
            r = "False"
        end if
    end function

end module hwut_pytext
