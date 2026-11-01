! _____________________________________________________________________________
! THE PRODUCER OF 'protocol.sh clean' -- no test, the program the script feeds
! its pype with: five clients talk to a service at once, each an OpenMP
! thread, and the service reports as it happens:
!
!     request <n>       a client asked
!     response <n>      it was answered
!     shutdown          once every client is done
!
! The order of the lines is the scheduler's; every line is flushed as it is
! said, for the pype reads them LIVE. No '<hwut-end>': the pype's '<eof>'
! prints it. 'on_entry' of 'hwut.conf' builds it.
! _____________________________________________________________________________
program producer
    use, intrinsic :: iso_fortran_env, only: real64, output_unit
    use hwut_text, only: say, str
    use hwut_posix, only: c_usleep
    implicit none
    integer      :: n, ignored
    real(real64) :: took(2)

    call random_init(repeatable = .false., image_distinct = .true.)
    !$omp parallel do num_threads(5) private(took, ignored) schedule(static, 1)
    do n = 1, 5
        !$omp critical (draw)
        call random_number(took)
        !$omp end critical (draw)
        ignored = c_usleep(int(took(1) * 0.02_real64 * 1.0e6_real64))
        call said("request " // str(n))
        ignored = c_usleep(int(took(2) * 0.02_real64 * 1.0e6_real64))
        call said("response " // str(n))
    end do
    !$omp end parallel do
    call said("shutdown")

contains

    subroutine said(text)
        ! RETURN: nothing; 'text' is one line on stdout, flushed, whole --
        !         one thread at a time.
        character(*), intent(in) :: text
        !$omp critical (output)
        call say(text)
        flush(output_unit)
        !$omp end critical (output)
    end subroutine

end program producer
