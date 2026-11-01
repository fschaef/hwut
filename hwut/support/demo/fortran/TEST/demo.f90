! @hwut {
!     title   = "Demo: what hwut tolerates, and where it is said"
!     build   { framework = "make", executable = "%.exe" }
!     choices {
!         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
!         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
!                       tolerance {
!                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
!                           numeric_ratio = 0.01
!                       } }
!         constraints { features = ["demo-passes-on-every-run", "constraints"]
!                       tolerance {
!                           constraints = ["load >= 0 and load <= 100",
!                                          "even % 2 == 0",
!                                          "twice == 2 * once"]
!                       } }
!         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
!         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
!         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
!         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
!                       tolerance { nothing = ["[.]+"] } }
!         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
!                       tolerance { analogy = ["{", "}"] } }
!         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
!     }
! }
!
! _____________________________________________________________________________
! A TEST APPLICATION OF HWUT, FOR READING -- 'demo.py' of the Python
! demonstration, in Fortran, choice for choice.
!
!     hwut.run                    builds 'demo.exe' by the Makefile ('build'
!                                 in the header above), runs every choice
!                                 below, compares with GOOD/
!     hwut.play demo.f90 plain    runs one choice and records it in OUT/
!     hwut.accept demo.f90 plain  blesses that recording as GOOD; it runs
!                                 nothing
!     hwut.config.show demo.f90   prints what hwut READ from the header above
!
! The header above is the whole configuration: a title, the build, and one
! scope per choice. hwut calls 'demo.exe <choice>' and compares what it
! prints on stdout with 'GOOD/demo.f90--<choice>.txt' -- a '.link' to the
! Python demonstration's GOOD: the same words. '<hwut-end>' closes the
! stream.
!
! Every run is seeded by the clock ('random_init', Fortran 2018), so the
! output differs from run to run -- and every choice passes anyway. WHY, per
! choice, is said in 'demo.py' and in README.txt; in short:
!
! plain        nothing varies; the output must equal GOOD, line by line.
! tolerance    'eq_pattern' (a greeting at random), 'numeric_ratio' (a value
!              from [19.91, 20.09]).
! constraints  '((name: value))' bound, judged by the header's laws.
! race         '##! potpourri': three OpenMP threads print as they finish.
! analogies    '((x))': handles drawn per run, consistent throughout.
! pool         '##! potpourri subset duplicates': four threads, twelve jobs.
! progress     'nothing': lines of dots count as no line.
! lisp         'analogy = ["{", "}"]': addresses in braces.
! clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids.
!
! THREADS ARE OPENMP'S ('-fopenmp'): Fortran 2018 has no thread of its own --
! 'do concurrent' promises no concurrency, coarrays are images, not threads.
! _____________________________________________________________________________
module demo_choices
    use, intrinsic :: iso_fortran_env, only: int64, real64, output_unit
    use hwut_text
    use hwut_posix, only: c_usleep
    implicit none
    private
    public :: plain, tolerance, constraints, analogies, race, pool, progress, lisp, clusters

    character(10), parameter :: GREETING(6) = ["hello     ", "bonjour   ", "hallo     ", &
                                               "buongiorno", "hola      ", "ahoj      "]

contains

    ! ------------------------------------------------------------ the draws
    real(real64) function uniform(low, high)
        ! RETURN: a number drawn evenly from [low, high].
        real(real64), intent(in) :: low, high
        real(real64)             :: u
        call random_number(u)
        uniform = low + (high - low) * u
    end function

    integer(int64) function randint(low, high)
        ! RETURN: an integer drawn evenly from low .. high, both included.
        integer(int64), intent(in) :: low, high
        real(real64)               :: u
        call random_number(u)
        randint = low + min(high - low, int(u * real(high - low + 1, real64), int64))
    end function

    real(real64) function gauss(mu, sigma)
        ! RETURN: a number drawn from the normal distribution (mu, sigma),
        !         by Box and Muller.
        real(real64), intent(in) :: mu, sigma
        real(real64)             :: u1, u2
        call random_number(u1)
        call random_number(u2)
        gauss = mu + sigma * sqrt(-2.0_real64 * log(1.0_real64 - u1)) &
                           * cos(2.0_real64 * acos(-1.0_real64) * u2)
    end function

    subroutine sleep_s(seconds)
        ! RETURN: nothing; 'seconds' have passed.
        real(real64), intent(in) :: seconds
        integer                  :: ignored
        ignored = c_usleep(int(seconds * 1.0e6_real64))
    end subroutine

    function fixed(x, digits) result(text)
        ! RETURN: 'x' with 'digits' digits after the point, no blank --
        !         Python's '%.<digits>f' (Fortran's 'F0.d' drops the 0
        !         before the point).
        real(real64), intent(in)  :: x
        integer, intent(in)       :: digits
        character(:), allocatable :: text
        character(48)             :: buffer
        character(16)             :: form
        write(form, '("(F47.", i0, ")")') digits
        write(buffer, form) x
        text = trim(adjustl(buffer))
    end function

    function padded(text, width) result(line)
        ! RETURN: 'text' with blanks before it to 'width' -- Python's '%<w>s'.
        character(*), intent(in)  :: text
        integer, intent(in)       :: width
        character(:), allocatable :: line
        line = repeat(" ", max(0, width - len(text))) // text
    end function

    function hex(i, digits, upper_f) result(text)
        ! RETURN: 'i' in hexadecimal, at least 'digits' digits -- Python's
        !         '%0<d>x', or '%X' where 'upper_f'.
        integer(int64), intent(in) :: i
        integer, intent(in)        :: digits
        logical, intent(in)        :: upper_f
        character(:), allocatable  :: text
        character(32)              :: buffer
        integer                    :: k
        write(buffer, '(Z32)') i
        text = trim(adjustl(buffer))
        text = repeat("0", max(0, digits - len(text))) // text
        if( upper_f ) return
        do k = 1, len(text)
            if( text(k:k) >= "A" .and. text(k:k) <= "F" ) text(k:k) = achar(iachar(text(k:k)) + 32)
        end do
    end function

    ! ------------------------------------------------------------ the choices
    subroutine plain()
        ! RETURN: nothing; prints what never varies.
        call say("the first line")
        call say("the second line: 1 2 3")
    end subroutine

    subroutine tolerance()
        ! RETURN: nothing; prints a greeting and a value, both drawn at random.
        integer(int64) :: k
        k = randint(1_int64, 6_int64)
        call say("greeting: " // trim(GREETING(k)) // ", world")
        call say("value:    " // fixed(uniform(19.91_real64, 20.09_real64), 2))
    end subroutine

    subroutine constraints()
        ! RETURN: nothing; prints bindings, each drawn at random, each lawful.
        integer(int64) :: once
        call say("load  ((load: " // fixed(uniform(0.0_real64, 100.0_real64), 1) // ")) %")
        call say("even  ((even: " // str(2 * randint(0_int64, 500_int64)) // "))")
        once = randint(1_int64, 50_int64)
        call say("once  ((once: " // str(once) // "))")
        call say("twice ((twice: " // str(2 * once) // "))")
    end subroutine

    subroutine analogies()
        ! RETURN: nothing; prints two handles, each drawn at random, each used
        !         consistently from opening to closing.
        integer(int64)            :: first, second
        character(:), allocatable :: a, b
        first = randint(int(z'1000', int64), int(z'FFFF', int64))
        do
            second = randint(int(z'1000', int64), int(z'FFFF', int64))
            if( second /= first ) exit
        end do
        a = hex(first, 4, .false.)
        b = hex(second, 4, .false.)
        call say("open  ((" // a // ")) input.txt")
        call say("open  ((" // b // ")) output.txt")
        call say("read  ((" // a // ")) 17 lines")
        call say("write ((" // b // ")) 17 lines")
        call say("close ((" // a // "))")
        call say("close ((" // b // "))")
    end subroutine

    subroutine race()
        ! RETURN: nothing; three threads print as they finish -- the order is
        !         the scheduler's, the facts are not. The program frames the
        !         unordered block itself: '##! potpourri' ... '####'.
        character(1), parameter :: NAME(3) = ["A", "B", "C"]
        integer, parameter      :: JOBS(3) = [3, 5, 2]
        real(real64)            :: took
        integer                 :: k
        call say("start")
        call say("##! potpourri")
        flush(output_unit)
        !$omp parallel do num_threads(3) private(took) schedule(static, 1)
        do k = 1, 3
            !$omp critical (draw)
            took = uniform(0.0_real64, 0.02_real64)
            !$omp end critical (draw)
            call sleep_s(took)
            !$omp critical (output)
            call say("worker " // NAME(k) // " done: " // str(JOBS(k)) // " jobs")
            !$omp end critical (output)
        end do
        !$omp end parallel do
        call say("####")
        call say("all joined")
    end subroutine

    subroutine pool()
        ! RETURN: nothing; four threads take twelve jobs from one queue; each
        !         reports the job it finished. Who takes how many is the
        !         scheduler's.
        character(1), parameter :: NAME(4) = ["A", "B", "C", "D"]
        type(string)            :: done_list(12)
        integer                 :: queued, done_n, worker, i
        logical                 :: got_f
        real(real64)            :: took
        queued = 12
        done_n = 0
        !$omp parallel do num_threads(4) private(got_f, took) schedule(static, 1)
        do worker = 1, 4
            do
                !$omp critical (queue)
                got_f = queued > 0
                if( got_f ) queued = queued - 1
                took = uniform(0.0_real64, 0.005_real64)
                !$omp end critical (queue)
                if( .not. got_f ) exit
                call sleep_s(took)
                !$omp critical (done)
                done_n = done_n + 1
                done_list(done_n)%s = "job done by worker " // NAME(worker)
                !$omp end critical (done)
            end do
        end do
        !$omp end parallel do
        call say("twelve jobs, four workers:")
        call say("##! potpourri subset duplicates")
        do i = 1, done_n
            call say(done_list(i)%s)
        end do
        call say("####")
        call say("jobs done: " // str(done_n))
    end subroutine

    subroutine progress()
        ! RETURN: nothing; a download that prints dots while it waits; how
        !         many is the network's.
        integer(int64) :: i
        call say("connecting to mirror")
        do i = 1, randint(0_int64, 3_int64)
            call say(repeat(".", int(randint(1_int64, 8_int64))))
        end do
        call say("connected")
        call say("received 1024 bytes")
    end subroutine

    subroutine lisp()
        ! RETURN: nothing; a Lisp session at its prompt: two objects, each
        !         printed with its address '{...}', drawn anew per run, and
        !         each used again.
        integer(int64)            :: table, thread
        character(:), allocatable :: t, w
        table = randint(int(z'1000000000', int64), int(z'10FFFFFFFF', int64))
        do
            thread = randint(int(z'1000000000', int64), int(z'10FFFFFFFF', int64))
            if( thread /= table ) exit
        end do
        t = hex(table, 1, .true.)
        w = hex(thread, 1, .true.)
        call say("* (defvar *cache* (make-hash-table))")
        call say("#<HASH-TABLE :TEST EQL :COUNT 0 {" // t // "}>")
        call say('* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name "worker"))')
        call say('#<THREAD "worker" RUNNING {' // w // '}>')
        call say("* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))")
        call say('#<THREAD "worker" RUNNING {' // w // '}>')
        call say("* *cache*")
        call say("#<HASH-TABLE :TEST EQL :COUNT 1 {" // t // "}>")
    end subroutine

    subroutine clusters()
        ! RETURN: nothing; clusters 90 noisy points around three centres and
        !         prints the centroids in the order the run found them.
        real(real64), parameter :: CENTRE(2, 3) = reshape([1.0_real64, 1.0_real64, &
                                                           5.0_real64, 4.0_real64, &
                                                           9.0_real64, 1.0_real64], [2, 3])
        real(real64) :: point(2, 90), centroid(2, 3), swap(2), nearest_d, d, best
        integer      :: member(90), c, i, j, k, round, far
        do c = 1, 3
            do k = 1, 30
                i = (c - 1) * 30 + k
                point(1, i) = CENTRE(1, c) + gauss(0.0_real64, 0.3_real64)
                point(2, i) = CENTRE(2, c) + gauss(0.0_real64, 0.3_real64)
            end do
        end do
        do i = 90, 2, -1                                   ! shuffled
            j = int(randint(1_int64, int(i, int64)))
            swap = point(:, i); point(:, i) = point(:, j); point(:, j) = swap
        end do
        ! The start: one point at random, then twice the point farthest from
        ! every start chosen so far -- one start per cluster.
        centroid(:, 1) = point(:, randint(1_int64, 90_int64))
        do c = 2, 3
            best = -1.0_real64
            far  = 1
            do i = 1, 90
                nearest_d = huge(1.0_real64)
                do k = 1, c - 1
                    nearest_d = min(nearest_d, sum((point(:, i) - centroid(:, k))**2))
                end do
                if( nearest_d > best ) then
                    best = nearest_d; far = i
                end if
            end do
            centroid(:, c) = point(:, far)
        end do
        do round = 1, 10
            do i = 1, 90
                member(i) = 1
                nearest_d = sum((point(:, i) - centroid(:, 1))**2)
                do c = 2, 3
                    d = sum((point(:, i) - centroid(:, c))**2)
                    if( d < nearest_d ) then
                        nearest_d = d; member(i) = c
                    end if
                end do
            end do
            do c = 1, 3
                centroid(1, c) = sum(point(1, :), mask = member == c) / count(member == c)
                centroid(2, c) = sum(point(2, :), mask = member == c) / count(member == c)
            end do
        end do
        call say("centroids (x y), in the order found:")
        call say("##! point-cloud limit=0.3 pair dist=Linf")
        do c = 1, 3
            call say("    " // padded(fixed(centroid(1, c), 2), 5) // " " // padded(fixed(centroid(2, c), 2), 5))
        end do
        call say("####")
    end subroutine

end module demo_choices

program demo
    use demo_choices
    use hwut_text, only: say
    implicit none
    character(64) :: choice

    call random_init(repeatable = .false., image_distinct = .true.)
    call get_command_argument(1, choice)
    select case( trim(choice) )
    case( "plain" );       call plain()
    case( "tolerance" );   call tolerance()
    case( "constraints" ); call constraints()
    case( "analogies" );   call analogies()
    case( "race" );        call race()
    case( "pool" );        call pool()
    case( "progress" );    call progress()
    case( "lisp" );        call lisp()
    case( "clusters" );    call clusters()
    case default
        call say("choices: plain, tolerance, constraints, analogies, race, pool, progress, lisp, clusters")
        stop 1, quiet = .true.
    end select
    call say("<hwut-end>")
end program demo
