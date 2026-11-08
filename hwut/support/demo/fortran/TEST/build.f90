! @hwut {
!     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
!     build   { framework = "make", target = "%.exe" }
!     pype    = "build.pypes"
!     same    = true
!     choices = ["serial", "parallel"]
!     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
!                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
!                 "pype-quantity", "pype-anchors-globs-flush"]
!     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
! }
!
! _____________________________________________________________________________
! SUBJECT  the log of a recursive build -- configure, then the directories
!          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
!          a pype system makes of it.
! REQUIREMENT  A parallel build builds what the serial build builds: the same
!              sources, the same warnings, the same archives and the same
!              program, linked from the same parts.
!
! The application only REPORTS the build as it happens, as 'make -w' would.
! The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
! between it and the comparison (hwut runs it; the application prints no
! '<hwut-end>'): 'normalise.pype' takes the job tag of a parallel line away,
! 'build.pype' makes the summary -- see their own comments.
!
! 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.f90.txt' -- a
! '.link' to the Python demonstration's. Serial or parallel, the summary must
! be the same. 'choices' is a list: no choice states anything of its own.
!
! The laws: the compile times sum to under 5 s, and nothing in the log broke
! the build's grammar ('((breaches: 0))').
!
! THE TWO JOBS of 'parallel' are two OpenMP sections; each prints its block
! whole when done ('make -O'), every line tagged with its job.
! _____________________________________________________________________________
module build_log
    use, intrinsic :: iso_fortran_env, only: real64, output_unit
    use hwut_text
    use hwut_posix, only: c_usleep
    implicit none
    private
    public :: serial, parallel

contains

    subroutine compile_lines(name, line_list)
        ! RETURN: nothing; 'line_list' got what building directory 'name'
        !         prints, its sources compiled in the time each takes.
        character(*), intent(in)                 :: name
        type(string), allocatable, intent(inout) :: line_list(:)
        type(string), allocatable                :: source(:)
        character(:), allocatable                :: warning_of, warning, spent
        character(32)                            :: buffer
        real(real64)                             :: took
        integer                                  :: i, ignored
        allocate(source(0))
        warning_of = ""
        select case( name )
        case( "lib" )
            call push(source, "lib/str.c"); call push(source, "lib/num.c"); call push(source, "lib/map.c")
            warning_of = "lib/num.c"
            warning    = "lib/num.c:14:9: warning: unused variable 'n'"
        case( "app/plugins" )
            call push(source, "app/plugins/png.c"); call push(source, "app/plugins/svg.c")
            warning_of = "app/plugins/svg.c"
            warning    = "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"
        case( "app" )
            call push(source, "app/main.c"); call push(source, "app/cli.c")
        end select
        do i = 1, size(source)
            call random_number(took)
            took = 0.04_real64 + 0.08_real64 * took
            ignored = c_usleep(int(took * 1.0e6_real64))
            if( took < 0.1_real64 ) then
                write(buffer, '(i0, " ms")') int(took * 1000.0_real64)
            else
                write(buffer, '(f4.2, " s")') took
            end if
            spent = trim(buffer)
            call push(line_list, "cc -c " // source(i)%s // " -o " &
                      // source(i)%s(1:len(source(i)%s) - 2) // ".o (took " // spent // ")")
            if( source(i)%s == warning_of ) call push(line_list, warning)
        end do
    end subroutine

    function product_of(name) result(line)
        ! RETURN: the line that makes the product of directory 'name'.
        character(*), intent(in)  :: name
        character(:), allocatable :: line
        select case( name )
        case( "lib" );         line = "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o"
        case( "app/plugins" ); line = "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o"
        case default;          line = "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a"
        end select
    end function

    recursive subroutine directory_block(name, level, line_list, inner)
        ! RETURN: nothing; 'line_list' got the block 'make -w' prints for
        !         'name' at 'level', the block of 'inner' nested before the
        !         product.
        character(*), intent(in)                 :: name
        integer, intent(in)                      :: level
        type(string), allocatable, intent(inout) :: line_list(:)
        character(*), intent(in), optional       :: inner
        call push(line_list, "make[" // str(level) // "]: Entering directory '" // name // "'")
        call compile_lines(name, line_list)
        if( present(inner) ) call directory_block(inner, level + 1, line_list)
        call push(line_list, product_of(name))
        call push(line_list, "make[" // str(level) // "]: Leaving directory '" // name // "'")
    end subroutine

    subroutine configure()
        ! RETURN: nothing; prints what 'configure' prints, and that make
        !         enters the top directory.
        call say("configure: checking for cc... cc")
        call say("configure: checking for ar... ar")
        call say("make: Entering directory 'demo'")
        flush(output_unit)
    end subroutine

    subroutine serial()
        ! RETURN: nothing; builds one directory after the other.
        type(string), allocatable :: line_list(:)
        integer                   :: i
        call configure()
        allocate(line_list(0))
        call directory_block("lib", 1, line_list)
        call directory_block("app", 1, line_list, "app/plugins")
        do i = 1, size(line_list)
            call say(line_list(i)%s)
            flush(output_unit)
        end do
        call say("make: Leaving directory 'demo'")
    end subroutine

    subroutine parallel()
        ! RETURN: nothing; builds 'lib' and 'app' at once. Each job prints its
        !         block whole when done, every line tagged with the job;
        !         which job finishes first is the scheduler's.
        type(string), allocatable :: block_1(:), block_2(:)
        integer                   :: i
        call configure()
        !$omp parallel sections num_threads(2) private(i)
        !$omp section
        allocate(block_1(0))
        call directory_block("lib", 1, block_1)
        !$omp critical (output)
        do i = 1, size(block_1)
            call say("job1: " // block_1(i)%s)
            flush(output_unit)
        end do
        !$omp end critical (output)
        !$omp section
        allocate(block_2(0))
        call directory_block("app", 1, block_2, "app/plugins")
        !$omp critical (output)
        do i = 1, size(block_2)
            call say("job2: " // block_2(i)%s)
            flush(output_unit)
        end do
        !$omp end critical (output)
        !$omp end parallel sections
        call say("make: Leaving directory 'demo'")
    end subroutine

end module build_log

program build
    use build_log
    use hwut_text, only: say
    implicit none
    character(16) :: choice

    call random_init(repeatable = .false., image_distinct = .true.)
    call get_command_argument(1, choice)
    select case( trim(choice) )
    case( "serial" );   call serial()
    case( "parallel" ); call parallel()
    case default
        call say("choices: serial, parallel")
        stop 1, quiet = .true.
    end select
end program build
