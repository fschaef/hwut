! @hwut {
!     title      = "DeterministicStream RNG and SelectionMarker spread"
!     build      { framework = "make", executable = "%.exe" }
!     choices {
!         gauss      { features = ["fortran-random"] }
!         primitives { features = ["fortran-random"] }
!         ranges     { features = ["fortran-random"] }
!         sample     { features = ["fortran-random"] }
!         seed_sweep { features = ["fortran-random"] }
!         select     { features = ["fortran-random"] }
!         unchosen   { features = ["fortran-random"] }
!     }
!     interactive = true
! }
!
! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: The Fortran port of 'python/TEST/test-deterministic-random.py',
!          choice for choice, held against its GOOD files by '.link'. Where
!          Python prints an index, the Fortran position less one is printed;
!          a candidate's identity is an integer (see deterministic_random).
! _____________________________________________________________________________
module test_deterministic_random_choices
    use, intrinsic :: iso_fortran_env, only: int64, real64
    use hwut_text
    use hwut_pytext
    use hwut_runner
    use deterministic_random
    implicit none

    integer(int64), parameter :: SEED = int(z'42', int64)
    character(*),   parameter :: TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}"
    character(*),   parameter :: REGION_END             = "####"

contains

    subroutine banner(label)
        character(*), intent(in) :: label
        call say("")
        call say("--- " // label // " ---")
    end subroutine

    function numbered(i, text) result(line)
        ! RETURN: '[0i] text' -- Python's '[%02d] %s'.
        integer, intent(in)       :: i
        character(*), intent(in)  :: text
        character(:), allocatable :: line
        character(8)              :: number
        write(number, '(i2.2)') i
        line = "[" // trim(number) // "] " // text
    end function

    function list_text(index) result(text)
        ! RETURN: the integers as Python prints a list of int: '[3, 0, 7]'.
        integer, intent(in)       :: index(:)
        character(:), allocatable :: text
        integer                   :: i
        text = "["
        do i = 1, size(index)
            if( i > 1 ) text = text // ", "
            text = text // str(index(i))
        end do
        text = text // "]"
    end function

    subroutine run_primitives()
        type(DeterministicStream) :: s
        character(:), allocatable :: line
        integer                   :: i
        call banner("next_int(0, 1000000) -- first 20")
        s = DeterministicStream(SEED)
        do i = 0, 19
            call say(numbered(i, str(s%next_int(0, 1000000))))
        end do
        call banner("next_float -- first 10 (full precision)")
        s = DeterministicStream(SEED)
        do i = 0, 9
            call say(numbered(i, repr(s%next_float())))
        end do
        call banner("coin(0.5) -- 40 draws")
        s = DeterministicStream(SEED)
        line = ""
        do i = 1, 40
            line = line // merge("T", "F", s%coin(0.5_real64))
            if( i < 40 ) line = line // " "
        end do
        call say(line)
    end subroutine

    subroutine run_ranges()
        type(DeterministicStream) :: s
        type(string)              :: draw(30)
        character(8)              :: signed
        integer                   :: i
        call banner("next_int(0, 9) -- 30 draws")
        s = DeterministicStream(SEED)
        do i = 1, 30
            draw(i)%s = str(s%next_int(0, 9))
        end do
        call say(join(draw, " "))
        call banner("next_int(5, 5) -- degenerate range returns the bound")
        s = DeterministicStream(SEED)
        do i = 1, 5
            draw(i)%s = str(s%next_int(5, 5))
        end do
        call say(join(draw(:5), " "))
        call banner("next_int(-3, 3) -- spanning zero")
        s = DeterministicStream(SEED)
        do i = 1, 20
            write(signed, '(sp, i0)') s%next_int(-3, 3)
            draw(i)%s = trim(signed)
        end do
        call say(join(draw(:20), " "))
    end subroutine

    subroutine run_gauss()
        type(DeterministicStream) :: s
        type(string)              :: draw(20)
        integer                   :: i
        call banner("gauss(0, 1) -- 10 draws (full precision)")
        s = DeterministicStream(SEED)
        call say(TOLERANCE_REGION_BEGIN)
        do i = 0, 9
            call say(numbered(i, repr(s%gauss(0.0_real64, 1.0_real64))))
        end do
        call say(REGION_END)
        call banner("gauss(0, 1) clamped to [-1, 1]")
        s = DeterministicStream(SEED)
        call say(TOLERANCE_REGION_BEGIN)
        do i = 0, 9
            call say(numbered(i, repr(s%gauss(0.0_real64, 1.0_real64, -1.0_real64, 1.0_real64))))
        end do
        call say(REGION_END)
        call banner("gauss_int(100, 15) -- 20 draws")
        s = DeterministicStream(SEED)
        do i = 1, 20
            draw(i)%s = str(s%gauss_int(100.0_real64, 15.0_real64))
        end do
        call say(join(draw, " "))
    end subroutine

    subroutine run_sample()
        type(DeterministicStream) :: s
        type(string)              :: pool(5), draw(20), letter(4)
        character(*), parameter   :: LETTERS = "ABCDEFGH"
        integer                   :: i, k(4)
        pool = [string("alpha"), string("beta"), string("gamma"), string("delta"), string("epsilon")]
        call banner("sample_indices(10, 10) -- full permutation")
        s = DeterministicStream(SEED)
        call say(list_text(s%sample_indices(10, 10) - 1))
        call banner("sample_indices(20, 5) -- partial draw")
        s = DeterministicStream(SEED)
        call say(list_text(s%sample_indices(20, 5) - 1))
        call banner("choice from a list -- 20 draws")
        s = DeterministicStream(SEED)
        do i = 1, 20
            k(1) = s%choice(size(pool))      ! drawn ONCE: see RATIONALE F-1
            draw(i) = pool(k(1))
        end do
        call say(join(draw, " "))
        call banner("sample(list, 4) -- unique elements")
        s = DeterministicStream(SEED)
        k = s%sample_indices(len(LETTERS), 4)
        do i = 1, 4
            letter(i)%s = repr(LETTERS(k(i):k(i)))
        end do
        call say("[" // join(letter, ", ") // "]")
    end subroutine

    subroutine run_select()
        type(DeterministicStream) :: s
        type(string)              :: draw(20)
        character(*), parameter   :: POOL = "abcd", BRANCH = "pqr"
        integer                   :: i, k
        call banner("select over a list -- 20 draws")
        s = DeterministicStream(SEED)
        do i = 1, 20
            k = s%select(len(POOL)); draw(i)%s = POOL(k:k)
        end do
        call say(join(draw, " "))
        call banner("select over a tuple -- 12 draws")
        s = DeterministicStream(SEED)
        do i = 1, 12
            k = s%select(len(BRANCH)); draw(i)%s = BRANCH(k:k)
        end do
        call say(join(draw(:12), " "))
    end subroutine

    ! THE CANDIDATES BY IDENTITY: 1 is "a", 2 is "b", ... -- see the head.
    function named(identity) result(name)
        integer, intent(in)       :: identity(:)
        character(:), allocatable :: name
        character(*), parameter   :: TEXT = "abcd"
        integer                   :: i
        name = ""
        do i = 1, size(identity)
            if( i > 1 ) name = name // " "
            name = name // TEXT(identity(i):identity(i))
        end do
    end function

    subroutine run_unchosen()
        type(DeterministicStream) :: s
        type(SelectionMarker)     :: m
        integer                   :: i, drawn(12), first, before(4), after(4)
        integer, parameter        :: A = 1, B = 2, C = 3, D = 4
        integer, parameter        :: POOL(4) = [A, B, C, D]

        call banner("stable pool -- three full cycles of 4 elements")
        s = DeterministicStream(SEED); m = SelectionMarker()
        do i = 1, 12
            drawn(i) = s%select_unchosen(POOL, m)
        end do
        call say(named(drawn))

        call banner("FRESH container each call -- identical to the stable pool above")
        s = DeterministicStream(SEED); m = SelectionMarker()
        do i = 1, 12
            drawn(i) = s%select_unchosen([A, B, C, D], m)        ! a new array every call
        end do
        call say(named(drawn))

        call banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]")
        s = DeterministicStream(SEED); m = SelectionMarker()
        first = s%select_unchosen([A, B], m)
        do i = 1, 3
            drawn(i) = s%select_unchosen(POOL, m)
        end do
        call say("first(from sub): " // named([first]) // "  then(from full): " // named(drawn(:3)))

        call banner("reset() restarts the cycle")
        s = DeterministicStream(SEED); m = SelectionMarker()
        do i = 1, 4
            before(i) = s%select_unchosen(POOL, m)
        end do
        call m%reset()
        do i = 1, 4
            after(i) = s%select_unchosen(POOL, m)
        end do
        call say("before reset: " // named(before))
        call say("after  reset: " // named(after))
    end subroutine

    subroutine run_seed_sweep()
        type(DeterministicStream) :: s
        character(64)             :: line
        integer                   :: seed
        call banner("first next_int(0, 1000000) per seed 0..15")
        do seed = 0, 15
            s = DeterministicStream(seed)
            write(line, '("seed=", i2, " -> ", i0)') seed, s%next_int(0, 1000000)
            call say(trim(line))
        end do
    end subroutine

end module test_deterministic_random_choices

program test_deterministic_random
    ! THE CHOICES ARE MODULE PROCEDURES: a procedure pointer to an internal
    ! one would need a trampoline, and with it an executable stack.
    use hwut_runner
    use test_deterministic_random_choices
    implicit none
    type(HwutRunner) :: runner
    runner = HwutRunner("DeterministicStream RNG and SelectionMarker spread", [ &
                 HwutChoice("primitives", run_primitives), HwutChoice("ranges",   run_ranges), &
                 HwutChoice("gauss",      run_gauss),      HwutChoice("sample",   run_sample), &
                 HwutChoice("select",     run_select),     HwutChoice("unchosen", run_unchosen), &
                 HwutChoice("seed_sweep", run_seed_sweep)])
    call runner%run()
end program test_deterministic_random
