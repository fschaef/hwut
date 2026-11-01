! _____________________________________________________________________________
! A TERMINAL FILE VIEWER -- the program 'screen.f90' tests; no test itself.
!
!     viewer.exe <file>
!
! Full screen, on the terminal's alternate screen: a title bar (reverse
! video), as many lines of the file as fit, and a status line: the keys flush
! left, the lines shown flush right. Keys: 'j' or down one line further, 'k'
! or up one line back, 'q' quits.
!
! FORTRAN HAS NO WORD FOR A TERMINAL. The raw mode is libc's ('tcgetattr',
! 'cfmakeraw', 'tcsetattr', bound by ISO_C_BINDING; the 'struct termios' is
! held as bytes, never read). The terminal's size is asked of 'stty size':
! libc answers it only through 'ioctl', a variadic function, which 'bind(c)'
! does not promise to call (the port's 'hwut_posix' binds none either). The
! screen is written and the keys read on descriptors 0 and 1 directly, byte
! for byte, as Python's 'os.read' and a flushed 'sys.stdout' do.
! _____________________________________________________________________________
module viewer_terminal
    use, intrinsic :: iso_c_binding
    use hwut_text
    use hwut_posix, only: c_write, c_mkstemp, c_close
    implicit none
    private
    public :: main

    character(*), parameter :: CSI = ESC // "["
    character(*), parameter :: CRLF = achar(13) // achar(10)

    interface
        integer(c_int) function c_tcgetattr(fd, termios) bind(c, name="tcgetattr")
            import :: c_int, c_signed_char
            integer(c_int), value        :: fd
            integer(c_signed_char)       :: termios(*)
        end function
        integer(c_int) function c_tcsetattr(fd, action, termios) bind(c, name="tcsetattr")
            import :: c_int, c_signed_char
            integer(c_int), value              :: fd, action
            integer(c_signed_char), intent(in) :: termios(*)
        end function
        subroutine c_cfmakeraw(termios) bind(c, name="cfmakeraw")
            import :: c_signed_char
            integer(c_signed_char) :: termios(*)
        end subroutine
        integer(c_ptrdiff_t) function c_read(fd, data, n) bind(c, name="read")
            import :: c_int, c_char, c_size_t, c_ptrdiff_t
            integer(c_int), value   :: fd
            character(kind=c_char)  :: data(*)
            integer(c_size_t), value :: n
        end function
    end interface

    integer(c_int), parameter :: TCSANOW = 0, TCSADRAIN = 1
    integer, parameter        :: TERMIOS_BYTES = 256      ! more than 'struct termios' holds

contains

    subroutine put(text)
        ! RETURN: nothing; 'text' was written on the terminal, as it is.
        character(*), intent(in) :: text
        integer(c_ptrdiff_t)     :: ignored
        ignored = c_write(1_c_int, text, int(len(text), c_size_t))
    end subroutine

    subroutine terminal_size(row_n, column_n)
        ! RETURN: nothing; 'row_n' and 'column_n' are the terminal's -- as
        !         'stty size' reads them off standard input; 24 and 80 where
        !         it cannot.
        integer, intent(out)        :: row_n, column_n
        character(kind=c_char, len=32) :: template
        integer                     :: unit, status
        row_n = 24
        column_n = 80
        template = "/tmp/viewer-size-XXXXXX" // c_null_char
        if( c_close(c_mkstemp(template)) /= 0 ) return
        associate( path => template(1:index(template, c_null_char) - 1) )
            call execute_command_line("stty size > " // path, exitstat = status)
            open(newunit = unit, file = path, status = "old", action = "read")
            if( status == 0 ) read(unit, *, iostat = status) row_n, column_n
            close(unit, status = "delete")
        end associate
    end subroutine

    subroutine draw(name, line_list, top, row_n, column_n)
        ! RETURN: nothing; the whole screen is drawn with the file's line
        !         'top' (from 0) first.
        character(*), intent(in) :: name
        type(string), intent(in) :: line_list(:)
        integer, intent(in)      :: top, row_n, column_n
        character(:), allocatable :: title, where, screen
        integer                   :: body_n, shown_n, i
        body_n  = row_n - 2
        shown_n = max(0, min(body_n, size(line_list) - top))
        title = " " // name // repeat(" ", column_n)
        screen = CSI // "H" // CSI // "2J" // CSI // "7m" // title(1:column_n) // CSI // "0m" // CRLF
        do i = top + 1, top + shown_n
            screen = screen // line_list(i)%s(1:min(len(line_list(i)%s), column_n)) // CRLF
        end do
        do i = 1, body_n - shown_n
            screen = screen // CRLF
        end do
        where = "lines " // str(top + 1) // "-" // str(top + shown_n) // " of " // str(size(line_list))
        screen = screen // CSI // str(row_n) // ";1H" // "j k q" &
                 // repeat(" ", max(0, column_n - 1 - 5 - len(where))) // where
        call put(screen)
    end subroutine

    integer function main(path) result(status)
        ! RETURN: 0, once 'q' was pressed.
        character(*), intent(in)      :: path
        type(string), allocatable     :: line_list(:)
        character(4096)               :: buffer
        character(kind=c_char, len=8) :: key
        integer(c_signed_char)        :: saved(TERMIOS_BYTES), raw(TERMIOS_BYTES)
        integer(c_ptrdiff_t)          :: n
        integer                       :: unit, io, top, row_n, column_n
        allocate(line_list(0))
        open(newunit = unit, file = path, status = "old", action = "read")
        do
            read(unit, '(a)', iostat = io) buffer
            if( io /= 0 ) exit
            call push(line_list, trim(buffer))
        end do
        close(unit)
        call terminal_size(row_n, column_n)
        status = c_tcgetattr(0_c_int, saved)
        raw = saved
        call c_cfmakeraw(raw)
        status = c_tcsetattr(0_c_int, TCSANOW, raw)
        call put(CSI // "?1049h")
        top = 0
        do
            call draw(path(index(path, "/", back = .true.) + 1:), line_list, top, row_n, column_n)
            n = c_read(0_c_int, key, 8_c_size_t)
            if( n <= 0 ) exit
            associate( k => key(1:n) )
                if( k == "q" ) then
                    exit
                else if( k == "j" .or. k == CSI // "B" ) then
                    top = min(top + 1, max(0, size(line_list) - (row_n - 2)))
                else if( k == "k" .or. k == CSI // "A" ) then
                    top = max(top - 1, 0)
                end if
            end associate
        end do
        call put(CSI // "?1049l")
        status = c_tcsetattr(0_c_int, TCSADRAIN, saved)
        status = 0
    end function

end module viewer_terminal

program viewer
    use viewer_terminal
    implicit none
    character(4096) :: path

    call get_command_argument(1, path)
    stop main(trim(path)), quiet = .true.
end program viewer
