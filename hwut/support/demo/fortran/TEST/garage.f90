! @hwut {
!     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
!     build    { framework = "make", target = "%.exe" }
!     interactive = true
!     choices {
!         space       { features = ["demo-fortran+cover-space-from-hocon", "demo-fortran+cover-space-iterator", "demo-fortran+cover-hwut-runner"]
!                       tolerance { constraints = ["mismatches == 0"] } }
!         random      { features = ["demo-fortran+cover-deterministic-stream", "demo-fortran+cover-hwut-runner"]
!                       tolerance { constraints = ["mismatches == 0"] } }
!         race-naive  { features = ["demo-fortran+cover-deterministic-timeline", "demo-fortran+cover-space-iterator", "demo-fortran+cover-hwut-runner"]
!                       tolerance { constraints = ["overbooked > 0"] } }
!         race-atomic { features = ["demo-fortran+cover-deterministic-timeline", "demo-fortran+cover-space-iterator", "demo-fortran+cover-hwut-runner"]
!                       tolerance { constraints = ["overbooked == 0"] } }
!     }
! }
!
! _____________________________________________________________________________
! SUBJECT  the counter of free spaces at a garage's gates: which cars it
!          admits, which it refuses, and how many stand inside.
! REQUIREMENT  The garage admits a car only while a space is free, lets a car
!              out only while one stands inside, and never holds more cars
!              than it has spaces -- also when two gates admit at once.
!
! No choice writes its cases out by hand. Each GENERATES them, with one of
! hwut's modules for writing tests in Fortran (the port named in the
! Makefile):
!
! space        'garage-space.hocon' states the tested space, read by
!              'hwut_hocon'; 'space_iterator' writes down every combination:
!              3 x 5 x 4 = 60 cases, each one cell of a matrix, checked
!              against the model: admitted = min(arriving, capacity), out =
!              min(leaving, admitted).
! random       'DeterministicStream(4711)' draws 1000 cars arriving and
!              leaving at a garage of 5. The draw is the same on every
!              machine and in every language hwut supports, so the GOOD is
!              exact -- the Python demonstration's, by '.link'.
! race-naive   two gates, one free space. A gate CHECKS whether a space is
!              free, and later ADMITS its car. 'deterministic_timeline' runs
!              the two gates as Triggers on timelines drawn as strings; all
!              six interleavings of two two-step gates in four ticks, from
!              'space_iterator'. Where both check before either admits, both
!              admit: overbooked. The law is 'overbooked > 0'.
! race-atomic  the same six interleavings, checking and admitting in ONE
!              step. 'overbooked == 0'.
!
! THE FRONT END is the port's HwutRunner: the choice list below is the whole
! command line, '--hwut-info' included. 'interactive = true': hwut starts the
! application ONCE and asks for the choices one after another.
!
! A GATE IS A TRIGGER: 'type, extends(Trigger) :: Gate' overrides 'fire'. What
! Python's gate shares by reference -- the garage, the log -- a Fortran gate
! holds as a pointer, and the log is a module variable.
! _____________________________________________________________________________
module garage_cases
    use, intrinsic :: iso_fortran_env, only: int64
    use hwut_text
    use hwut_hocon
    use space_iterator
    use deterministic_random
    use deterministic_timeline
    implicit none
    private
    public :: space, random_stream, race_naive, race_atomic

    ! The unit under test: a counter of the spaces a garage has.
    type :: Garage
        integer :: capacity = 0
        integer :: occupied = 0
    contains
        procedure :: free   => garage_free
        procedure :: arrive => garage_arrive
        procedure :: leave  => garage_leave
    end type

    ! A gate on a timeline: its first tick checks, its second admits.
    type, extends(Trigger) :: Gate
        type(Garage), pointer :: garage   => null()
        logical               :: atomic_f = .false.
        integer               :: step     = 0
        logical               :: saw_free = .false.
    contains
        procedure :: fire => gate_fire
    end type

    ! The values of one dimension of the space.
    type :: IntList
        integer, allocatable :: i(:)
    end type

    type(string), allocatable :: event_list(:)          ! what the gates did

contains

    integer function garage_free(self)
        ! RETURN: the number of spaces free now -- negative where the garage
        !         is overbooked.
        class(Garage), intent(in) :: self
        garage_free = self%capacity - self%occupied
    end function

    logical function garage_arrive(self)
        ! RETURN: .true., a car was admitted, if a space was free;
        !         .false., else (the car is refused).
        class(Garage), intent(inout) :: self
        garage_arrive = self%free() > 0
        if( garage_arrive ) self%occupied = self%occupied + 1
    end function

    logical function garage_leave(self)
        ! RETURN: .true., a car drove out, if one stood inside;
        !         .false., else.
        class(Garage), intent(inout) :: self
        garage_leave = self%occupied > 0
        if( garage_leave ) self%occupied = self%occupied - 1
    end function

    function here() result(directory)
        ! RETURN: the directory this program stands in, with a '/' at its
        !         end; '' where it was called without one.
        character(:), allocatable :: directory
        character(4096)           :: path
        call get_command_argument(0, path)
        directory = path(1:index(path, "/", back = .true.))
    end function

    function left(text, width) result(line)
        ! RETURN: 'text' with blanks after it to 'width' -- Python's '%-<w>s'.
        character(*), intent(in)  :: text
        integer, intent(in)       :: width
        character(:), allocatable :: line
        line = text // repeat(" ", max(0, width - len(text)))
    end function

    function right(text, width) result(line)
        ! RETURN: 'text' with blanks before it to 'width' -- Python's '%<w>s'.
        character(*), intent(in)  :: text
        integer, intent(in)       :: width
        character(:), allocatable :: line
        line = repeat(" ", max(0, width - len(text))) // text
    end function

    function list_repr(value) result(text)
        ! RETURN: the integers as Python prints a list of them, '[1, 2]'.
        integer, intent(in)       :: value(:)
        character(:), allocatable :: text
        integer                   :: i
        text = "["
        do i = 1, size(value)
            if( i > 1 ) text = text // ", "
            text = text // str(value(i))
        end do
        text = text // "]"
    end function

    ! _________________________________________________________________________
    ! space -- the tested space from HOCON, written down by space_iterator
    !
    subroutine read_space(path, name, value)
        ! RETURN: nothing; 'name(d)' is the d-th dimension of the space in
        !         'path', in the order written, 'value(d)%i' its values. Every
        !         fault the HOCON reader found is printed with '!!' first.
        character(*), intent(in)                   :: path
        type(string), allocatable, intent(out)     :: name(:)
        type(IntList), allocatable, intent(out)    :: value(:)
        type(SourceLine), allocatable :: line(:)
        type(HoconDocument)           :: document
        type(ParseFault), allocatable :: fault(:)
        character(4096)               :: buffer
        integer                       :: unit, status, n, k, d, i, entry, item
        ! Counted first, then filled component by component: a structure
        ! constructor with a text of its own inside an array constructor is
        ! one of gfortran 13's defects (the port's RATIONALE, F-1).
        open(newunit = unit, file = path, status = "old", action = "read")
        n = 0
        do
            read(unit, '(a)', iostat = status) buffer
            if( status /= 0 ) exit
            n = n + 1
        end do
        allocate(line(n))
        rewind(unit)
        do i = 1, n
            read(unit, '(a)') buffer
            line(i)%text = trim(buffer)
            line(i)%line = i
            line(i)%column_offset = 0
        end do
        close(unit)
        call parse(line, path(index(path, "/", back = .true.) + 1:), document, fault)
        do i = 1, size(fault)
            call say("!! " // fault(i)%str())
        end do
        k = document%get(document%root, "space")
        allocate(name(size(document%node(k)%child)), value(size(document%node(k)%child)))
        do d = 1, size(document%node(k)%child)
            entry = document%node(k)%child(d)
            name(d)%s = document%node(entry)%key
            allocate(value(d)%i(size(document%node(entry)%child)))
            do i = 1, size(document%node(entry)%child)
                item = document%node(entry)%child(i)
                value(d)%i(i) = int(document%node(item)%i)
            end do
        end do
    end subroutine

    subroutine space()
        ! RETURN: nothing; prints every case of the space as a matrix cell.
        type(string), allocatable  :: name(:), cell(:, :)
        type(IntList), allocatable :: value(:)
        integer, allocatable       :: point(:, :)
        type(Garage)               :: g
        character(:), allocatable  :: line, mark
        integer :: p, capacity, arriving, leaving, refused, admitted, i, c, a, mismatch_n
        integer :: expected(2), got(2)
        call read_space(here() // "garage-space.hocon", name, value)
        line = "space: "
        do i = 1, size(name)
            if( i > 1 ) line = line // "  x  "
            line = line // name(i)%s // " " // list_repr(value(i)%i)
        end do
        call say(line)
        call say("cell: cars inside / cars refused at the gate ('!!' differs from the model)")
        mismatch_n = 0
        ! One row per (capacity, arriving), one cell per leaving: the
        ! rightmost dimension changes fastest.
        allocate(cell(size(value(1)%i) * size(value(2)%i), size(value(3)%i)))
        point = product_points([size(value(1)%i), size(value(2)%i), size(value(3)%i)])
        do p = 1, size(point, 2)
            capacity = value(1)%i(point(1, p))
            arriving = value(2)%i(point(2, p))
            leaving  = value(3)%i(point(3, p))
            g = Garage(capacity, 0)
            refused = 0
            do i = 1, arriving
                if( .not. g%arrive() ) refused = refused + 1
            end do
            do i = 1, leaving
                if( g%leave() ) continue
            end do
            admitted = min(arriving, capacity)
            expected = [admitted - min(leaving, admitted), arriving - admitted]
            got      = [g%occupied, refused]
            mark     = merge("  ", "!!", all(got == expected))
            if( any(got /= expected) ) mismatch_n = mismatch_n + 1
            cell((point(1, p) - 1) * size(value(2)%i) + point(2, p), point(3, p))%s &
                = str(got(1)) // "/" // str(got(2)) // mark
        end do
        do c = 1, size(value(1)%i)
            line = "capacity " // str(value(1)%i(c)) // "   "
            do i = 1, size(value(3)%i)
                if( i > 1 ) line = line // "  "
                line = line // "leave " // left(str(value(3)%i(i)), 3)
            end do
            call say(trim(line))
            do a = 1, size(value(2)%i)
                line = "  arrive " // str(value(2)%i(a)) // "   "
                do i = 1, size(value(3)%i)
                    if( i > 1 ) line = line // "  "
                    line = line // left(cell((c - 1) * size(value(2)%i) + a, i)%s, 9)
                end do
                call say(trim(line))
            end do
        end do
        call say("cases " // str(size(point, 2)) // ", differing from the model ((mismatches: " &
                 // str(mismatch_n) // "))")
    end subroutine

    ! _________________________________________________________________________
    ! random -- a deterministic stream of arrivals and departures
    !
    subroutine random_stream()
        ! RETURN: nothing; prints the summary of 1000 drawn cars,
        !         model-checked.
        type(DeterministicStream) :: stream
        type(Garage)              :: g
        integer                   :: model, arrive_n, refused_n, leave_n, empty_n, mismatch_n, i, n
        integer                   :: histogram(0:5)
        character(1000)           :: strip
        stream = DeterministicStream(4711)
        g = Garage(5, 0)
        model = 0; arrive_n = 0; refused_n = 0; leave_n = 0; empty_n = 0; mismatch_n = 0
        histogram = 0
        do i = 1, 1000
            if( stream%coin(0.55d0) ) then
                arrive_n = arrive_n + 1
                if( .not. g%arrive() ) refused_n = refused_n + 1
                model = min(5, model + 1)
                strip(i:i) = "+"
            else
                leave_n = leave_n + 1
                if( .not. g%leave() ) empty_n = empty_n + 1
                model = max(0, model - 1)
                strip(i:i) = "-"
            end if
            if( g%occupied /= model ) mismatch_n = mismatch_n + 1
            histogram(g%occupied) = histogram(g%occupied) + 1
        end do
        call say("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves")
        call say("first 60: " // strip(1:60))
        call say("arrivals " // str(arrive_n) // ", refused " // str(refused_n) // "; departures " &
                 // str(leave_n) // ", from an empty garage " // str(empty_n))
        call say("cars inside after each event:")
        do n = 0, 5
            call say(trim("    " // str(n) // "  " // right(str(histogram(n)), 4) // "  " &
                          // repeat("#", histogram(n) / 10)))
        end do
        call say("steps differing from the model ((mismatches: " // str(mismatch_n) // "))")
    end subroutine

    ! _________________________________________________________________________
    ! race -- two gates on drawn timelines
    !
    subroutine gate_fire(self, pseudo_time, status)
        ! RETURN: nothing; the gate performed its next step at 'pseudo_time'
        !         and said so in 'event_list'; 'status' is left alone.
        class(Gate), intent(inout) :: self
        integer, intent(in)        :: pseudo_time
        integer, intent(inout)     :: status
        if( self%step == 0 .and. self%atomic_f ) then
            self%saw_free = self%garage%arrive()
            call push(event_list, self%name // merge(" checks+admits", " refuses      ", self%saw_free))
            event_list(size(event_list))%s = trim(event_list(size(event_list))%s)
        else if( self%step == 0 ) then
            self%saw_free = self%garage%free() > 0
            call push(event_list, self%name // " sees " // str(self%garage%free()) // " free")
        else if( self%atomic_f ) then
            call push(event_list, self%name // merge(" opens     ", " stays shut", self%saw_free))
            event_list(size(event_list))%s = trim(event_list(size(event_list))%s)
        else if( self%saw_free ) then
            self%garage%occupied = self%garage%occupied + 1          ! the naive admit
            call push(event_list, self%name // " admits")
        else
            call push(event_list, self%name // " refuses")
        end if
        self%step = self%step + 1
    end subroutine

    subroutine interleavings(timeline_a, timeline_b)
        ! RETURN: nothing; 'timeline_a(k)', 'timeline_b(k)' are the k-th pair
        !         of timelines in four ticks in which each of two gates fires
        !         twice, never at the same tick: gate A's and gate B's.
        type(string), allocatable, intent(out) :: timeline_a(:), timeline_b(:)
        integer, allocatable                   :: point(:, :)
        integer                                :: p, t(4)
        allocate(timeline_a(0), timeline_b(0))
        point = product_points([4, 4, 4, 4])
        do p = 1, size(point, 2)
            t = point(:, p) - 1                          ! ticks count from 0
            if( t(1) >= t(2) .or. t(3) >= t(4) ) cycle
            if( t(1) == t(3) .or. t(1) == t(4) .or. t(2) == t(3) .or. t(2) == t(4) ) cycle
            call push(timeline_a, drawn(t(1), t(2)))
            call push(timeline_b, drawn(t(3), t(4)))
        end do
    contains
        function drawn(x, y) result(line)
            ! RETURN: the timeline of four ticks firing at 'x' and 'y'.
            integer, intent(in) :: x, y
            character(4)        :: line
            line = "    "
            line(x + 1:x + 1) = "1"
            line(y + 1:y + 1) = "1"
        end function
    end subroutine

    subroutine race(atomic_f)
        ! RETURN: nothing; plays every interleaving of two gates at one
        !         space.
        logical, intent(in)          :: atomic_f
        type(string), allocatable    :: timeline_a(:), timeline_b(:)
        type(Garage), target         :: g
        type(Gate), target           :: a, b
        type(TriggerDispatcher)      :: dispatcher
        character(:), allocatable    :: mark
        integer                      :: k, overbooked_n
        call say("one free space, two gates, one car at each; timelines: a digit fires")
        call say("    gate A  gate B  what happens                                    inside")
        call interleavings(timeline_a, timeline_b)
        overbooked_n = 0
        do k = 1, size(timeline_a)
            g = Garage(1, 0)
            allocate(event_list(0))
            call a%init(timeline_a(k)%s, "A")
            call b%init(timeline_b(k)%s, "B")
            a%garage => g; a%atomic_f = atomic_f; a%step = 0; a%saw_free = .false.
            b%garage => g; b%atomic_f = atomic_f; b%step = 0; b%saw_free = .false.
            dispatcher = TriggerDispatcher([ref(a), ref(b)])
            call dispatcher%run()
            mark = merge("!!", "  ", g%occupied > g%capacity)
            if( g%occupied > g%capacity ) overbooked_n = overbooked_n + 1
            call say(trim('    "' // timeline_a(k)%s // '"  "' // timeline_b(k)%s // '"  ' &
                          // left(join(event_list, ", "), 46) // "  " // str(g%occupied) // " " // mark))
            deallocate(event_list)
        end do
        call say("interleavings overbooking the garage ((overbooked: " // str(overbooked_n) &
                 // ")) of " // str(size(timeline_a)))
    end subroutine

    subroutine race_naive()
        ! RETURN: nothing; the gates check, then admit, in two steps.
        call race(.false.)
    end subroutine

    subroutine race_atomic()
        ! RETURN: nothing; the gates check and admit in one step.
        call race(.true.)
    end subroutine

end module garage_cases

program garage_app      ! not 'garage': Fortran is blind to case, and 'Garage' is the type
    use hwut_runner
    use garage_cases
    implicit none
    type(HwutRunner) :: runner

    runner = HwutRunner("Demo: a garage's space counter -- a space, a stream and races, generated;", &
                        [HwutChoice("space",       space),         &
                         HwutChoice("random",      random_stream), &
                         HwutChoice("race-naive",  race_naive),    &
                         HwutChoice("race-atomic", race_atomic)])
    call runner%run()
end program garage_app
