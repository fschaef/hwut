! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
!          'python/deterministic_random.py'. The same seed gives the same
!          numbers as the Python module, draw for draw: Park-Miller MINSTD,
!          'state = 48271 * state mod (2^31 - 1)', in 64-bit integers
!          ('integer(int64)': the product needs 47 bits).
!
!     use deterministic_random
!     type(DeterministicStream) :: s
!     type(SelectionMarker)     :: m
!     s = DeterministicStream(int(z'42', int64))   -- or DeterministicStream()
!     s%next_int(0_int64, 9_int64)                 -- also with default integers
!     s%next_float()        s%coin(0.5_real64)
!     pool(s%select(size(pool)))                   -- a POSITION, 1 .. n
!     s%gauss(0.0_real64, 1.0_real64)              -- 'lower', 'upper' optional
!     s%sample_indices(10, 3)                      -- 3 distinct positions of 1 .. 10
!     s%select_unchosen([1, 2, 3, 4], m)           -- an IDENTITY, see below
!
! POSITIONS ARE FORTRAN'S: 'select', 'choice' and 'sample_indices' answer an
! array position, 1 .. n, where Python answers an index 0 .. n-1 or the
! element itself -- the draw is the same, one apart.
!
! IDENTITY, AS PYTHON MEANS IT: a marker remembers a candidate by 'id()',
! never by value. A Fortran value has no identity -- two arrays holding
! "a" hold two equal texts, nothing more -- so a candidate's identity is an
! INTEGER the caller gives it, and 'select_unchosen' draws among such
! integers. A fresh array of the same identities is, as in Python, the same
! candidates.
!
! 'gauss' is the one path through libm (gfortran's 'log' and 'cos' are
! libm's): a last bit may differ between platforms.
! _____________________________________________________________________________
module deterministic_random
    use, intrinsic :: iso_fortran_env, only: int32, int64, real64
    use, intrinsic :: ieee_arithmetic, only: ieee_value, ieee_positive_inf, ieee_negative_inf, ieee_rint
    implicit none
    private

    public :: DeterministicStream, SelectionMarker

    real(real64), parameter :: PI = 3.141592653589793_real64

    type :: SelectionMarker
        integer, allocatable :: chosen(:)                ! identities
    contains
        procedure :: reset         => marker_reset
        procedure :: seen_f        => marker_seen_f
    end type

    type :: DeterministicStream
        integer(int64) :: state = 66_int64
    contains
        procedure, private :: next_int_64, next_int_default
        generic            :: next_int       => next_int_64, next_int_default
        procedure          :: next_float     => stream_next_float
        procedure          :: coin           => stream_coin
        procedure          :: select         => stream_select
        procedure          :: choice         => stream_select
        procedure          :: select_unchosen => stream_select_unchosen
        procedure          :: gauss          => stream_gauss
        procedure          :: gauss_int      => stream_gauss_int
        procedure          :: sample_indices => stream_sample_indices
    end type

    interface DeterministicStream
        module procedure stream_new_64, stream_new_default
    end interface

contains

    ! ------------------------------------------------------------- the marker
    subroutine marker_reset(self)
        ! RETURN: nothing; every chosen candidate is forgotten, the next cycle
        !         restarts.
        class(SelectionMarker), intent(inout) :: self
        if( allocated(self%chosen) ) deallocate(self%chosen)
        allocate(self%chosen(0))
    end subroutine

    pure logical function marker_seen_f(self, identity)
        ! RETURN: .true. where the candidate 'identity' was chosen since the
        !         last reset; .false. else.
        class(SelectionMarker), intent(in) :: self
        integer, intent(in)                :: identity
        marker_seen_f = .false.
        if( allocated(self%chosen) ) marker_seen_f = any(self%chosen == identity)
    end function

    ! ------------------------------------------------------------- the stream
    function stream_new_64(seed) result(self)
        ! RETURN: a DeterministicStream standing at 'seed' (its low 31 bits).
        integer(int64), intent(in) :: seed
        type(DeterministicStream)  :: self
        self%state = iand(seed, int(z'7FFFFFFF', int64))
    end function

    function stream_new_default(seed) result(self)
        ! RETURN: a DeterministicStream standing at 'seed' -- 0x42 where
        !         absent, as Python's default.
        integer(int32), intent(in), optional :: seed
        type(DeterministicStream)            :: self
        if( present(seed) ) then
            self = stream_new_64(int(seed, int64))
        else
            self = stream_new_64(66_int64)
        end if
    end function

    integer(int64) function next_int_64(self, v_min, v_max) result(value)
        ! RETURN: an integer uniform in [v_min, v_max]; the state steps even
        !         where the range is one value.
        class(DeterministicStream), intent(inout) :: self
        integer(int64), intent(in)                :: v_min, v_max
        self%state = mod(48271_int64 * self%state, 2147483647_int64)
        if( v_min == v_max ) then
            value = v_min
        else
            value = v_min + mod(self%state, v_max - v_min + 1)
        end if
    end function

    integer function next_int_default(self, v_min, v_max) result(value)
        ! RETURN: an integer uniform in [v_min, v_max] -- 'next_int' for
        !         default integers, the same draw.
        class(DeterministicStream), intent(inout) :: self
        integer, intent(in)                       :: v_min, v_max
        value = int(next_int_64(self, int(v_min, int64), int(v_max, int64)))
    end function

    real(real64) function stream_next_float(self) result(value)
        ! RETURN: a number in [0, 1): 'next_int(0, 1000000) / 1000001'.
        class(DeterministicStream), intent(inout) :: self
        value = real(next_int_64(self, 0_int64, 1000000_int64), real64) / 1000001.0_real64
    end function

    logical function stream_coin(self, probability_of_true) result(value)
        ! RETURN: .true. with 'probability_of_true', .false. else -- resolved
        !         in steps of 1/1000001 (TW-1).
        class(DeterministicStream), intent(inout) :: self
        real(real64), intent(in)                  :: probability_of_true
        value = stream_next_float(self) < probability_of_true
    end function

    integer function stream_select(self, candidate_n) result(position)
        ! RETURN: a position 1 .. candidate_n, uniformly drawn -- Python's
        !         'select'/'choice' answer the candidate at index
        !         'position - 1'.
        class(DeterministicStream), intent(inout) :: self
        integer, intent(in)                       :: candidate_n
        position = next_int_default(self, 0, candidate_n - 1) + 1
    end function

    integer function stream_select_unchosen(self, identity, marker) result(choice)
        ! RETURN: one of the 'identity' integers the marker has not seen,
        !         uniformly drawn among those and recorded in the marker;
        !         where every one was seen, the marker is reset and the draw
        !         is over all.
        class(DeterministicStream), intent(inout) :: self
        integer, intent(in)                       :: identity(:)
        type(SelectionMarker), intent(inout)      :: marker
        integer, allocatable                      :: unchosen(:)
        integer                                   :: i
        if( .not. allocated(marker%chosen) ) call marker%reset()
        unchosen = pack(identity, [(.not. marker%seen_f(identity(i)), i = 1, size(identity))])
        if( size(unchosen) == 0 ) then
            call marker%reset()
            unchosen = identity
        end if
        choice        = unchosen(next_int_default(self, 0, size(unchosen) - 1) + 1)
        marker%chosen = [marker%chosen, choice]
    end function

    real(real64) function stream_gauss(self, mu, sigma, lower, upper) result(value)
        ! RETURN: a draw of the normal distribution (mu, sigma) by the
        !         Box-Muller transform, clipped to [lower, upper] -- each
        !         unbounded where absent.
        class(DeterministicStream), intent(inout) :: self
        real(real64), intent(in)                  :: mu, sigma
        real(real64), intent(in), optional        :: lower, upper
        real(real64)                              :: u1, u2, z0, low, high
        low  = ieee_value(low,  ieee_negative_inf)
        high = ieee_value(high, ieee_positive_inf)
        if( present(lower) ) low  = lower
        if( present(upper) ) high = upper
        u1 = stream_next_float(self) + 1e-9_real64             ! avoid log(0)
        u2 = stream_next_float(self)
        z0 = sqrt(-2.0_real64 * log(u1)) * cos(2.0_real64 * PI * u2)
        value = z0 * sigma + mu
        if( value < low ) then
            value = low
        else if( value > high ) then
            value = high
        end if
    end function

    integer(int64) function stream_gauss_int(self, mu, sigma, lower, upper) result(value)
        ! RETURN: 'gauss' rounded to the nearest integer, a half to the even
        !         one -- as Python's 'round'.
        class(DeterministicStream), intent(inout) :: self
        real(real64), intent(in)                  :: mu, sigma
        real(real64), intent(in), optional        :: lower, upper
        value = int(ieee_rint(stream_gauss(self, mu, sigma, lower, upper)), int64)
    end function

    function stream_sample_indices(self, population_size, k) result(position)
        ! RETURN: 'k' distinct positions of 1 .. population_size, drawn by
        !         Fisher-Yates -- Python's 'sample_indices', one apart.
        class(DeterministicStream), intent(inout) :: self
        integer, intent(in)                       :: population_size, k
        integer                                   :: position(k)
        integer                                   :: pool(population_size), i, j, held
        if( population_size < k ) error stop "sample_indices: population_size < k"
        pool = [(i, i = 1, population_size)]
        do i = 1, k
            j       = next_int_default(self, i - 1, population_size - 1) + 1
            held    = pool(i); pool(i) = pool(j); pool(j) = held
            position(i) = pool(i)
        end do
    end function

end module deterministic_random
