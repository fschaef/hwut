! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: THE FEW CALLS OF LIBC FORTRAN HAS NO WORD FOR -- a process forked,
!          a descriptor duplicated, a variable of the environment set -- as
!          'bind(c)' interfaces (ISO_C_BINDING). Nothing is wrapped: each
!          name is libc's own, and the modules that need them say so.
!
!     use hwut_posix
!     pid = c_fork()
!     call c_setenv("COLUMNS", "300")
!
! Only NON-VARIADIC functions are bound ('creat', not 'open'): a variadic C
! function has a calling convention of its own that 'bind(c)' does not
! promise to meet. 'waitpid's status is decoded here, as <sys/wait.h>'s
! macros decode it on Linux.
! _____________________________________________________________________________
module hwut_posix
    use, intrinsic :: iso_c_binding
    implicit none
    private

    public :: c_fork, c_waitpid, c_creat, c_dup, c_dup2, c_close, c_write, c_mkstemp
    public :: c_exit_now, c_setenv_raw, c_strlen, c_free, c_usleep
    public :: c_text, c_string, c_setenv, exit_code_of, write_line

    interface
        integer(c_int) function c_fork() bind(c, name="fork")
            import :: c_int
        end function
        integer(c_int) function c_waitpid(pid, status, options) bind(c, name="waitpid")
            import :: c_int
            integer(c_int), value :: pid, options
            integer(c_int)        :: status
        end function
        integer(c_int) function c_creat(path, mode) bind(c, name="creat")
            import :: c_int, c_char
            character(kind=c_char), intent(in) :: path(*)
            integer(c_int), value              :: mode
        end function
        integer(c_int) function c_dup(fd) bind(c, name="dup")
            import :: c_int
            integer(c_int), value :: fd
        end function
        integer(c_int) function c_dup2(fd, to) bind(c, name="dup2")
            import :: c_int
            integer(c_int), value :: fd, to
        end function
        integer(c_int) function c_close(fd) bind(c, name="close")
            import :: c_int
            integer(c_int), value :: fd
        end function
        integer(c_ptrdiff_t) function c_write(fd, data, n) bind(c, name="write")
            import :: c_int, c_char, c_size_t, c_ptrdiff_t
            integer(c_int), value              :: fd
            character(kind=c_char), intent(in) :: data(*)
            integer(c_size_t), value           :: n
        end function
        integer(c_int) function c_mkstemp(template) bind(c, name="mkstemp")
            import :: c_int, c_char
            character(kind=c_char), intent(inout) :: template(*)
        end function
        subroutine c_exit_now(status) bind(c, name="_exit")
            import :: c_int
            integer(c_int), value :: status
        end subroutine
        integer(c_int) function c_setenv_raw(name, value, overwrite) bind(c, name="setenv")
            import :: c_int, c_char
            character(kind=c_char), intent(in) :: name(*), value(*)
            integer(c_int), value              :: overwrite
        end function
        integer(c_size_t) function c_strlen(text) bind(c, name="strlen")
            import :: c_size_t, c_ptr
            type(c_ptr), value :: text
        end function
        subroutine c_free(pointer) bind(c, name="free")
            import :: c_ptr
            type(c_ptr), value :: pointer
        end subroutine
        integer(c_int) function c_usleep(microseconds) bind(c, name="usleep")
            import :: c_int
            integer(c_int), value :: microseconds
        end function
    end interface

contains

    pure function c_text(text) result(terminated)
        ! RETURN: 'text' with the NUL a C function wants at its end.
        character(*), intent(in)  :: text
        character(:), allocatable :: terminated
        terminated = text // c_null_char
    end function

    function c_string(pointer, length) result(text)
        ! RETURN: the C text at 'pointer' as a Fortran text -- up to its NUL,
        !         or 'length' bytes where given (a NUL among them kept); ''
        !         for a null pointer.
        type(c_ptr), intent(in)                 :: pointer
        integer(c_size_t), intent(in), optional :: length
        character(:), allocatable               :: text
        character(kind=c_char), pointer         :: byte(:)
        integer(c_size_t)                       :: n, i
        if( .not. c_associated(pointer) ) then
            text = ""; return
        end if
        if( present(length) ) then
            n = length
        else
            n = c_strlen(pointer)
        end if
        call c_f_pointer(pointer, byte, [n])
        allocate(character(n) :: text)
        do i = 1, n
            text(i:i) = byte(i)
        end do
    end function

    subroutine c_setenv(name, value)
        ! RETURN: nothing; the environment variable 'name' holds 'value' --
        !         for this process and every process it starts.
        character(*), intent(in) :: name, value
        integer(c_int)           :: ignored
        ignored = c_setenv_raw(c_text(name), c_text(value), 1_c_int)
    end subroutine

    pure integer function exit_code_of(status)
        ! RETURN: the exit status a child ended with, as 'waitpid' reported
        !         it in 'status'; minus the signal where a signal ended it.
        integer(c_int), intent(in) :: status
        if( iand(status, 127) == 0 ) then
            exit_code_of = iand(ishft(status, -8), 255)
        else
            exit_code_of = -iand(status, 127)
        end if
    end function

    subroutine write_line(fd, text)
        ! RETURN: nothing; 'text' and a newline were written on the
        !         descriptor 'fd', unbuffered.
        integer(c_int), intent(in) :: fd
        character(*), intent(in)   :: text
        integer(c_ptrdiff_t)         :: ignored
        ignored = c_write(fd, text // achar(10), int(len(text) + 1, c_size_t))
    end subroutine

end module hwut_posix
