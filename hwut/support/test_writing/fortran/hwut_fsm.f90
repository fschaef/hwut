! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
!          port of 'python/hwut_fsm.py' (README-hwut_fsm.txt). The states it
!          may be in, the events that move it, the states it must never
!          reach. A test FIRES the events it observes; every event the model
!          does not allow, and every forbidden state entered, is WRITTEN as a
!          line -- so it lands in the GOOD file and the comparison judges it.
!
!     use hwut_fsm
!     type(Machine) :: m
!     m = Machine_from_string("initial: idle"                                  // NL // &
!                             "forbidden: crashed"                             // NL // &
!                             "idle ---( request )---> waiting ---( grant )---> busy" // NL // &
!                             "busy ---( release )---> idle"                   // NL // &
!                             ":    ---( fault )--->   crashed")
!     moved = m%fire("request", where = 1)      -- .true.
!     moved = m%fire("release", where = 2)      -- BREACH line 2: 'release' in ...
!     n     = m%report()
!
! The same model text, the same words, the same sorted reports as Python.
!
! THE MODEL IS A TABLE: states and events are POSITIONS in their sorted name
! lists, a transition three integers, a set of states a logical array over
! the states ('current', 'forbid'), a mask a logical matrix over (state,
! event) whose row 0 stands for every state. Python's sets and dicts become
! Fortran's arrays, and its questions 'any', 'count', 'pack' over them.
!
! WHAT PYTHON RAISES (FsmError) is, in Fortran's own manner, a STAT and an
! ERRMSG: where the caller passes 'stat', it is set (0, or 1 with 'errmsg'
! holding Python's text); where it passes none, the program stops with
! 'FsmError: <text>' -- as 'allocate' stops without 'stat='.
!
! 'where' (a breach's place) is 'class(*)': an integer names a line ('line
! 3'), a text stands as written, absent names no place -- Python's int, str
! and None. 'dfa' .true. (the default): one state; .false.: the machine holds
! a SET. Every line goes through the procedure pointer 'write' -- stdout by
! default.
! _____________________________________________________________________________
module hwut_fsm
    use hwut_text
    implicit none
    private

    public :: Machine, Machine_from_string, Transition, TraceEntry, EventPath, Place, line_writer, fsm_block

    abstract interface
        subroutine line_writer(line)
            ! RETURN: nothing; 'line' was written where the machine reports.
            character(*), intent(in) :: line
        end subroutine
    end interface

    type :: Place                                   ! a 'where'
        logical                   :: given_f = .false.
        logical                   :: line_f  = .false.
        character(:), allocatable :: text
    contains
        procedure :: str => place_str
    end type

    type :: Transition
        character(:), allocatable :: source, event, target
    end type

    type :: TraceEntry
        type(Place)               :: where
        character(:), allocatable :: state, event, target
    end type

    type :: EventPath                               ! a tuple of events, or None
        logical                   :: found_f = .false.
        type(string), allocatable :: event(:)
    contains
        procedure :: repr => path_repr
    end type

    type :: Machine
        character(:), allocatable                  :: name
        logical                                    :: dfa_f = .true.
        procedure(line_writer), pointer, nopass    :: write => null()
        type(string), allocatable                  :: state_list(:), event_list(:)  ! sorted
        integer, allocatable                       :: edge_source(:), edge_event(:), edge_target(:)
        integer                                    :: initial = 0
        logical, allocatable                       :: model_forbidden(:), final(:)
        ! the run, and the law as it stands now
        logical, allocatable                       :: current_f(:), forbid_f(:), permit_f(:)  ! per state
        type(Place), allocatable                   :: forbid_since(:), permit_since(:)
        logical, allocatable                       :: mask(:, :)        ! (0:state, event)
        type(Place), allocatable                   :: mask_since(:, :)
        integer, allocatable                       :: visit_n(:), taken_n(:)
        type(TraceEntry), allocatable              :: trace_list(:)
        integer                                    :: breach_n = 0
    contains
        procedure :: to_string           => machine_to_string
        procedure :: reset               => machine_reset
        procedure :: fire                => machine_fire
        procedure :: disallow            => machine_disallow
        procedure :: allow               => machine_allow
        procedure :: forbid              => machine_forbid
        procedure :: permit              => machine_permit
        procedure :: disallowed          => machine_disallowed
        procedure :: forbidding          => machine_forbidding
        procedure :: forbidden           => machine_forbidden
        procedure :: state               => machine_state
        procedure :: current             => machine_current
        procedure :: in_state            => machine_in_state
        procedure :: can                 => machine_can
        procedure :: allowed             => machine_allowed
        procedure :: trace               => machine_trace
        procedure :: path_to             => machine_path_to
        procedure :: state_reachable     => machine_state_reachable
        procedure :: unreachable         => machine_unreachable
        procedure :: dead_ends           => machine_dead_ends
        procedure :: forbidden_reachable => machine_forbidden_reachable
        procedure :: check               => machine_check
        procedure :: report              => machine_report
    end type

    interface Machine
        module procedure machine_new
    end interface

    abstract interface
        subroutine fsm_block(m)
            ! RETURN: nothing; the block of a phase ran on the machine 'm'.
            import :: Machine
            class(Machine), intent(inout) :: m
        end subroutine
    end interface

    type(Place), parameter :: NOWHERE = Place(.false., .false., null())

contains

    ! =============================================================== the small
    subroutine say_line(line)
        ! RETURN: nothing; 'line' was printed on stdout -- the default 'write'.
        character(*), intent(in) :: line
        call say(line)
    end subroutine

    subroutine raise(message, stat, errmsg)
        ! RETURN: nothing, where the caller asked for 'stat': it is 1 and
        !         'errmsg' holds 'message'. Never, else: the program stops
        !         with 'FsmError: <message>' -- Python's uncaught FsmError.
        character(*), intent(in)                         :: message
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        if( present(errmsg) ) errmsg = message
        if( .not. present(stat) ) error stop "FsmError: " // message
        stat = 1
    end subroutine

    function place_of(where) result(p)
        ! RETURN: the Place 'where' names -- an integer a line, a text as
        !         written, absent (or another type) none.
        class(*), intent(in), optional :: where
        type(Place)                    :: p
        if( .not. present(where) ) return
        select type( where )
        type is( integer )
            p%given_f = .true.; p%line_f = .true.; p%text = str(where)
        type is( character(*) )
            p%given_f = .true.; p%text = where
        end select
    end function

    function place_str(self) result(text)
        ! RETURN: the place as Python's 'str(where)': '3', the text, 'None'.
        class(Place), intent(in)  :: self
        character(:), allocatable :: text
        if( self%given_f ) then
            text = self%text
        else
            text = "None"
        end if
    end function

    function where_text(p) result(text)
        ! RETURN: ' line 3' for a line, ' <text>' for a text, '' for none --
        !         the place a breach line names.
        type(Place), intent(in)   :: p
        character(:), allocatable :: text
        if( .not. p%given_f ) then
            text = ""
        else if( p%line_f ) then
            text = " line " // p%text
        else
            text = " " // p%text
        end if
    end function

    function since_text(p) result(text)
        ! RETURN: ' since line 9', ' since <text>', or '' for none -- when a
        !         mask or a forbidden state began.
        type(Place), intent(in)   :: p
        character(:), allocatable :: text
        text = ""
        if( p%given_f ) text = " since" // where_text(p)
    end function

    pure function unique_sorted(list) result(unique)
        ! RETURN: the texts of 'list', sorted by code point, each once.
        type(string), intent(in)  :: list(:)
        type(string), allocatable :: unique(:), sorted(:)
        integer                   :: i
        sorted = list
        call sort_strings(sorted)
        allocate(unique(0))
        do i = 1, size(sorted)
            if( i > 1 ) then
                if( sorted(i)%s == sorted(i - 1)%s .and. len(sorted(i)%s) == len(sorted(i - 1)%s) ) cycle
            end if
            unique = [unique, sorted(i)]
        end do
    end function

    function quoted_list(list) result(text)
        ! RETURN: the texts each in single quotes, joined by ', '.
        type(string), intent(in)  :: list(:)
        character(:), allocatable :: text
        integer                   :: i
        text = ""
        do i = 1, size(list)
            if( i > 1 ) text = text // ", "
            text = text // "'" // list(i)%s // "'"
        end do
    end function

    function names(self, flag) result(list)
        ! RETURN: the names of the states whose 'flag' is set, sorted.
        class(Machine), intent(in) :: self
        logical, intent(in)        :: flag(:)
        type(string), allocatable  :: list(:)
        list = pack(self%state_list, flag)
    end function

    integer function state_i(self, name)
        ! RETURN: the position of the state 'name'; 0 where the model names
        !         none.
        class(Machine), intent(in) :: self
        character(*), intent(in)   :: name
        state_i = text_index(self%state_list, name)
    end function

    integer function event_i(self, name)
        ! RETURN: the position of the event 'name'; 0 where the model names
        !         none.
        class(Machine), intent(in) :: self
        character(*), intent(in)   :: name
        event_i = text_index(self%event_list, name)
    end function

    subroutine emit(self, line)
        ! RETURN: nothing; 'line' went through 'self%write'.
        class(Machine), intent(in) :: self
        character(*), intent(in)   :: line
        if( associated(self%write) ) then
            call self%write(line)
        else
            call say(line)
        end if
    end subroutine

    ! ============================================================ construction
    function machine_new(transition_list, initial, forbidden, final, dfa, name, states, &
                         stat, errmsg) result(self)
        ! RETURN: a Machine standing in 'initial'; where the model cannot be
        !         meant -- a DFA with two transitions for one (state, event),
        !         a forbidden or final state named nowhere else -- FsmError
        !         ('stat'/'errmsg', see the head). 'states' names states no
        !         transition touches (yet).
        type(Transition), intent(in)                     :: transition_list(:)
        character(*), intent(in)                         :: initial
        type(string), intent(in), optional               :: forbidden(:), final(:), states(:)
        logical, intent(in), optional                    :: dfa
        character(*), intent(in), optional               :: name
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        type(Machine)                                    :: self
        type(string), allocatable                        :: all(:), chosen(:), unknown(:), target_set(:)
        integer                                          :: i, j, k, c, n, ns
        integer, allocatable                             :: s(:), e(:), t(:)
        character(9)                                     :: label

        if( present(stat) ) stat = 0
        self%dfa_f = .true.
        if( present(dfa) ) self%dfa_f = dfa
        self%name = "fsm"
        if( present(name) ) self%name = name
        self%write => say_line

        allocate(all(0))
        call push(all, initial)
        if( present(states) ) all = [all, states]
        do i = 1, size(transition_list)
            ! A DFA MOVES ONE WAY PER EVENT: the targets seen so far.
            allocate(target_set(0))
            do j = 1, i - 1
                if( transition_list(j)%source /= transition_list(i)%source ) cycle
                if( transition_list(j)%event  /= transition_list(i)%event )  cycle
                call push(target_set, transition_list(j)%target)
            end do
            if( self%dfa_f .and. size(target_set) > 0 ) then
                if( text_index(target_set, transition_list(i)%target) == 0 ) then
                    target_set = unique_sorted(target_set)
                    call raise("'" // transition_list(i)%source // "' --(" // transition_list(i)%event &
                               // ")--> '" // target_set(1)%s // "' and '" // transition_list(i)%target &
                               // "': a DFA moves one way per event -- or 'DFA=False'", stat, errmsg)
                    return
                end if
            end if
            deallocate(target_set)
            call push(all, transition_list(i)%source)
            call push(all, transition_list(i)%target)
        end do
        self%state_list = unique_sorted(all)

        do c = 1, 2
            if( c == 1 ) then
                label = "forbidden"
                if( .not. present(forbidden) ) cycle
                chosen = forbidden
            else
                label = "final"
                if( .not. present(final) ) cycle
                chosen = final
            end if
            allocate(unknown(0))
            do i = 1, size(chosen)
                if( state_i(self, chosen(i)%s) == 0 ) call push(unknown, chosen(i)%s)
            end do
            if( size(unknown) > 0 ) then
                call raise(trim(label) // " state(s) " // quoted_list(unique_sorted(unknown)) &
                           // ": named nowhere else in the model", stat, errmsg)
                return
            end if
            deallocate(unknown)
        end do

        ns = size(self%state_list)
        deallocate(all)
        allocate(all(0))
        do i = 1, size(transition_list)
            call push(all, transition_list(i)%event)
        end do
        self%event_list = unique_sorted(all)

        ! THE EDGES, as positions, sorted by (source, event, target), each once.
        n = size(transition_list)
        allocate(s(n), e(n), t(n))
        do i = 1, n
            s(i) = state_i(self, transition_list(i)%source)
            e(i) = event_i(self, transition_list(i)%event)
            t(i) = state_i(self, transition_list(i)%target)
        end do
        allocate(self%edge_source(0), self%edge_event(0), self%edge_target(0))
        do i = 1, ns
            do j = 1, size(self%event_list)
                do k = 1, ns
                    if( .not. any(s == i .and. e == j .and. t == k) ) cycle
                    self%edge_source = [self%edge_source, i]
                    self%edge_event  = [self%edge_event, j]
                    self%edge_target = [self%edge_target, k]
                end do
            end do
        end do

        self%initial = state_i(self, initial)
        allocate(self%model_forbidden(ns), self%final(ns))
        self%model_forbidden = .false.
        self%final           = .false.
        if( present(forbidden) ) then
            do i = 1, size(forbidden)
                self%model_forbidden(state_i(self, forbidden(i)%s)) = .true.
            end do
        end if
        if( present(final) ) then
            do i = 1, size(final)
                self%final(state_i(self, final(i)%s)) = .true.
            end do
        end if
        call self%reset()
    end function

    subroutine machine_reset(self)
        ! RETURN: nothing; the machine stands in its initial state again,
        !         under the model as written: what was seen, every mask and
        !         every state forbidden or permitted since are forgotten.
        class(Machine), intent(inout) :: self
        integer                       :: ns, ne
        ns = size(self%state_list)
        ne = size(self%event_list)
        if( allocated(self%current_f) ) then
            deallocate(self%current_f, self%forbid_f, self%permit_f, self%forbid_since, self%permit_since, &
                       self%mask, self%mask_since, self%visit_n, self%taken_n, self%trace_list)
        end if
        allocate(self%current_f(ns), self%forbid_f(ns), self%permit_f(ns), self%forbid_since(ns), &
                 self%permit_since(ns), self%mask(0:ns, ne), self%mask_since(0:ns, ne), &
                 self%visit_n(ns), self%taken_n(size(self%edge_source)), self%trace_list(0))
        self%current_f = .false.
        self%forbid_f  = self%model_forbidden
        self%permit_f  = .false.
        self%mask    = .false.
        self%visit_n = 0
        self%taken_n = 0
        self%current_f(self%initial) = .true.
        self%visit_n(self%initial) = 1
        self%breach_n = 0
    end subroutine

    ! ================================================================ reading
    logical function name_of(text, number, name, errmsg) result(ok_f)
        ! RETURN: .true., 'name' holds the state 'text' names -- 'A' or
        !         'state A'; .false., it names none and 'errmsg' says so with
        !         line 'number'.
        character(*), intent(in)               :: text
        integer, intent(in)                    :: number
        character(:), allocatable, intent(out) :: name
        character(:), allocatable, intent(out) :: errmsg
        character(:), allocatable              :: t, rest
        character(*), parameter :: FIRST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"
        character(*), parameter :: OTHER = FIRST // "0123456789.-"
        t    = strip(text)
        rest = t
        if( len(t) > 5 ) then
            if( t(1:5) == "state" .and. strip(t(6:6)) == "" ) rest = strip(t(6:))
        end if
        ok_f = .false.
        if( len(rest) > 0 ) then
            if( verify(rest(1:1), FIRST) == 0 .and. verify(rest, OTHER) == 0 ) ok_f = .true.
        end if
        if( ok_f ) then
            name = rest
        else
            errmsg = "line " // str(number) // ": '" // t // "' names no state -- a state is a word ('A', 'state A')"
        end if
    end function

    logical function arrow_at(line, p, end_at, event) result(found_f)
        ! RETURN: .true. where an arrow '-+ \s* ( \s* event \s* ) \s* -* >'
        !         begins at 'p' -- 'end_at' the position after it, 'event'
        !         its stripped text; .false. else.
        character(*), intent(in)               :: line
        integer, intent(in)                    :: p
        integer, intent(out)                   :: end_at
        character(:), allocatable, intent(out) :: event
        integer                                :: q, open, close
        found_f = .false.
        q = p
        if( at(q) /= "-" ) return
        do while( at(q) == "-" )
            q = q + 1
        end do
        do while( space_f(at(q)) )
            q = q + 1
        end do
        if( at(q) /= "(" ) return
        open  = q + 1
        close = open
        do while( close <= len(line) )
            if( line(close:close) == ")" ) exit
            if( line(close:close) == "(" ) return
            close = close + 1
        end do
        if( at(close) /= ")" ) return
        q = close + 1
        do while( space_f(at(q)) )
            q = q + 1
        end do
        do while( at(q) == "-" )
            q = q + 1
        end do
        if( at(q) /= ">" ) return
        end_at  = q + 1
        event   = strip(line(open:close - 1))
        found_f = .true.
    contains
        character function at(i)
            ! RETURN: the character at 'i'; NUL beyond the line.
            integer, intent(in) :: i
            at = achar(0)
            if( i <= len(line) ) at = line(i:i)
        end function
        logical function space_f(c)
            ! RETURN: .true. for a white space character.
            character, intent(in) :: c
            space_f = c == " " .or. (iachar(c) >= 9 .and. iachar(c) <= 13)
        end function
    end function

    function Machine_from_string(text, dfa, name, stat, errmsg) result(self)
        ! RETURN: the Machine the model 'text' states; FsmError naming the
        !         line where it cannot be meant ('stat'/'errmsg', see the
        !         head). One statement per line, '#' a comment:
        !             initial: A        forbidden: X, Y        final: A, B
        !             state A
        !             A ---( ev )---> B ---( ev2 )---> C
        !             :  ---( ev )---> D     -- ':' the state that began the
        !                                       line above
        character(*), intent(in)                         :: text
        logical, intent(in), optional                    :: dfa
        character(*), intent(in), optional               :: name
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        type(Machine)                                    :: self
        type(string), allocatable                        :: line_list(:), part(:), declared_initial(:)
        type(string), allocatable                        :: declared_forbidden(:), declared_final(:), alone(:)
        type(Transition), allocatable                    :: triple(:)
        type(Transition)                                 :: one
        integer, allocatable                             :: line_of(:)
        character(:), allocatable                        :: line, first, previous_head, head, source
        character(:), allocatable                        :: target, event, message, word, rest, piece
        integer                                          :: number, k, at, start, end_at, i, comma
        logical                                          :: dfa_f, found_f
        character(*), parameter :: KEY(3) = ["initial  ", "forbidden", "final    "]

        if( present(stat) ) stat = 0
        dfa_f = .true.
        if( present(dfa) ) dfa_f = dfa
        allocate(declared_initial(0), declared_forbidden(0), declared_final(0), alone(0), triple(0), line_of(0))
        first         = ""
        previous_head = ""
        line_list     = split_lines(text)
        if( len(text) > 0 ) then                   ! 'splitlines' gives no line after a last newline
            if( text(len(text):len(text)) == NL ) line_list = line_list(:size(line_list) - 1)
        else
            line_list = line_list(:0)
        end if

        do number = 1, size(line_list)
            line = line_list(number)%s
            k    = index(line, "#")
            if( k > 0 ) line = line(:k - 1)
            line = strip(line)
            if( len(line) == 0 ) cycle

            ! KEY: 'initial:', 'forbidden:', 'final:'
            found_f = .false.
            do i = 1, 3
                word = trim(KEY(i))
                if( .not. starts_with(line, word) ) cycle
                rest = strip(line(len(word) + 1:))
                if( .not. starts_with(rest, ":") ) cycle
                found_f = .true.
                exit
            end do
            if( found_f ) then
                rest = rest(2:)
                k    = 0
                do
                    comma = index(rest, ",")
                    if( comma == 0 ) then
                        piece = rest
                    else
                        piece = rest(:comma - 1)
                    end if
                    if( len(strip(piece)) > 0 ) then
                        if( .not. name_of(piece, number, head, message) ) then
                            call raise(message, stat, errmsg); return
                        end if
                        k = k + 1
                        select case( i )
                        case( 1 ); call push(declared_initial, head)
                        case( 2 ); call push(declared_forbidden, head)
                        case( 3 ); call push(declared_final, head)
                        end select
                    end if
                    if( comma == 0 ) exit
                    rest = rest(comma + 1:)
                end do
                if( i == 1 .and. k /= 1 ) then
                    call raise("line " // str(number) // ": 'initial:' names one state", stat, errmsg)
                    return
                end if
                cycle
            end if

            ! THE PARTS: head, then (event, state) per arrow
            allocate(part(0))
            at    = 1
            start = 1
            do while( at <= len(line) )
                if( arrow_at(line, at, end_at, event) ) then
                    call push(part, line(start:at - 1))
                    call push(part, event)
                    at    = end_at
                    start = end_at
                else
                    at = at + 1
                end if
            end do
            call push(part, line(start:))
            if( size(part) == 1 ) then
                if( .not. name_of(line, number, head, message) ) then
                    call raise(message, stat, errmsg); return
                end if
                if( len(first) == 0 ) first = head
                call push(alone, head)
                previous_head = head
                deallocate(part)
                cycle
            end if
            do i = 2, size(part), 2
                if( len(part(i)%s) == 0 ) then
                    call raise("line " // str(number) // ": an arrow names no event -- '---( event )--->'", &
                               stat, errmsg)
                    return
                end if
            end do
            if( strip(part(1)%s) == ":" .and. len(strip(part(1)%s)) == 1 ) then
                if( len(previous_head) == 0 ) then
                    call raise("line " // str(number) // ": ':' stands for the state of the line above, " &
                               // "and none stands there", stat, errmsg)
                    return
                end if
                head = previous_head
            else
                if( .not. name_of(part(1)%s, number, head, message) ) then
                    call raise(message, stat, errmsg); return
                end if
            end if
            if( len(first) == 0 ) first = head
            previous_head = head
            source        = head
            do i = 2, size(part), 2
                if( .not. name_of(part(i + 1)%s, number, target, message) ) then
                    call raise(message, stat, errmsg); return
                end if
                event = part(i)%s
                if( dfa_f ) then              ! THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines
                    do k = 1, size(triple)
                        if( triple(k)%source /= source .or. triple(k)%event /= event ) cycle
                        if( len(triple(k)%source) /= len(source) .or. len(triple(k)%event) /= len(event) ) cycle
                        if( triple(k)%target /= target .or. len(triple(k)%target) /= len(target) ) then
                            call raise("line " // str(number) // ": '" // source // "' --(" // event // ")--> '" &
                                       // target // "', and line " // str(line_of(k)) // ": --> '" &
                                       // triple(k)%target // "' -- a DFA moves one way per event, or 'DFA=False'", &
                                       stat, errmsg)
                            return
                        end if
                        exit
                    end do
                end if
                one%source = source                 ! not 'Transition(...)': see 'fire'
                one%event  = event
                one%target = target
                triple  = [triple, one]
                line_of = [line_of, number]
                source  = target
            end do
            deallocate(part)
        end do

        if( len(first) == 0 .and. size(declared_initial) == 0 ) then
            call raise("the model names no state", stat, errmsg)
            return
        end if
        if( size(declared_initial) > 0 ) first = declared_initial(1)%s
        self = machine_new(triple, first, declared_forbidden, declared_final, dfa_f, name, alone, stat, errmsg)
    end function

    function machine_to_string(self) result(text)
        ! RETURN: the model in the text 'Machine_from_string' reads, one
        !         transition per line, sorted -- what a book page or a GOOD
        !         file can show of it.
        class(Machine), intent(in) :: self
        character(:), allocatable  :: text
        logical, allocatable       :: named(:)
        integer                    :: i
        text = "initial: " // self%state_list(self%initial)%s
        if( any(self%model_forbidden) ) text = text // NL // "forbidden: " // join(names(self, self%model_forbidden), ", ")
        if( any(self%final) )           text = text // NL // "final: " // join(names(self, self%final), ", ")
        allocate(named(size(self%state_list)))
        named = .false.
        named(self%initial) = .true.
        do i = 1, size(self%edge_source)
            text = text // NL // self%state_list(self%edge_source(i))%s // " ---( " &
                   // self%event_list(self%edge_event(i))%s // " )---> " // self%state_list(self%edge_target(i))%s
            named(self%edge_source(i)) = .true.
            named(self%edge_target(i)) = .true.
        end do
        do i = 1, size(self%state_list)
            if( .not. named(i) .and. .not. self%model_forbidden(i) ) text = text // NL // "state " // self%state_list(i)%s
        end do
    end function

    ! ================================================================ running
    logical function masked_f(self, s, e)
        ! RETURN: .true. where the event 'e' is disallowed in the state 's'
        !         now -- in every state, or in that one; .false. else.
        class(Machine), intent(in) :: self
        integer, intent(in)        :: s, e
        masked_f = self%mask(0, e) .or. self%mask(s, e)
    end function

    function here(self) result(text)
        ! RETURN: where the machine stands: "'idle'", or "{'a', 'b'}" for a
        !         set.
        class(Machine), intent(in) :: self
        character(:), allocatable  :: text
        if( count(self%current_f) == 1 ) then
            text = quoted_list(names(self, self%current_f))
        else
            text = "{" // quoted_list(names(self, self%current_f)) // "}"
        end if
    end function

    logical function machine_fire(self, event, where) result(moved_f)
        ! RETURN: .true., 'event' moved the machine and entered no forbidden
        !         state; .false., it was not allowed where the machine stands
        !         -- a BREACH line is written and the machine stays -- or it
        !         entered a forbidden state, which is written too.
        class(Machine), intent(inout)  :: self
        character(*), intent(in)       :: event
        class(*), intent(in), optional :: where
        type(Place)                    :: p
        type(TraceEntry)               :: entry
        logical, allocatable           :: moved(:)
        type(string), allocatable      :: allowed(:)
        character(:), allocatable      :: hint
        integer                        :: s, i, e, masked
        logical                        :: entered_f

        p = place_of(where)
        e = event_i(self, event)
        allocate(moved(size(self%state_list)))
        moved  = .false.
        masked = 0
        if( e > 0 ) then
            do s = 1, size(self%state_list)
                if( .not. self%current_f(s) ) cycle
                if( masked_f(self, s, e) ) then
                    if( masked == 0 .and. any(self%edge_source == s .and. self%edge_event == e) ) masked = s
                    cycle
                end if
                do i = 1, size(self%edge_source)
                    if( self%edge_source(i) /= s .or. self%edge_event(i) /= e ) cycle
                    moved(self%edge_target(i)) = .true.
                    self%taken_n(i) = self%taken_n(i) + 1
                    ! COMPONENT BY COMPONENT, not 'TraceEntry(p, ...)': gfortran 13
                    ! copies a deferred-length text wrongly in such a constructor.
                    entry%where  = p
                    entry%state  = self%state_list(s)%s
                    entry%event  = event
                    entry%target = self%state_list(self%edge_target(i))%s
                    self%trace_list = [self%trace_list, entry]
                end do
            end do
        end if
        if( .not. any(moved) ) then
            self%breach_n = self%breach_n + 1
            allowed = self%allowed()
            if( size(allowed) > 0 ) then
                hint = "allowed: " // join(allowed, ", ")
            else
                hint = "no event leaves it"
            end if
            if( e == 0 ) then
                hint = "an event the model never names"
            else if( masked > 0 ) then
                if( self%mask(masked, e) ) then
                    hint = "disallowed" // since_text(self%mask_since(masked, e))
                else
                    hint = "disallowed" // since_text(self%mask_since(0, e))
                end if
            end if
            call emit(self, "BREACH" // where_text(p) // ": '" // event // "' in " // here(self) // " -- " // hint)
            moved_f = .false.
            return
        end if
        self%current_f = moved
        self%visit_n = self%visit_n + merge(1, 0, moved)
        entered_f = .false.
        do s = 1, size(self%state_list)
            if( .not. (moved(s) .and. self%forbid_f(s)) ) cycle
            self%breach_n = self%breach_n + 1
            entered_f     = .true.
            if( self%model_forbidden(s) .and. .not. self%forbid_since(s)%given_f ) then
                call emit(self, "BREACH" // where_text(p) // ": '" // self%state_list(s)%s // "' entered by '" &
                                // event // "' -- a forbidden state")
            else
                call emit(self, "BREACH" // where_text(p) // ": '" // self%state_list(s)%s // "' entered by '" &
                                // event // "' -- forbidden" // since_text(self%forbid_since(s)))
            end if
        end do
        moved_f = .not. entered_f
    end function

    ! ======================================================= the law, changing
    logical function known(self, event, state, stat, errmsg) result(ok_f)
        ! RETURN: .true. where 'event' and 'state' (each where given) are
        !         named by the model; .false. else, FsmError raised naming
        !         what is not -- a mask over a word the model never names
        !         would guard nothing.
        class(Machine), intent(in)                       :: self
        character(*), intent(in), optional               :: event, state
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        ok_f = .false.
        if( present(event) ) then
            if( event_i(self, event) == 0 ) then
                call raise("'" // event // "': an event the model never names -- events: " &
                           // join(self%event_list, ", "), stat, errmsg)
                return
            end if
        end if
        if( present(state) ) then
            if( state_i(self, state) == 0 ) then
                call raise("'" // state // "': a state the model never names -- states: " &
                           // join(self%state_list, ", "), stat, errmsg)
                return
            end if
        end if
        if( present(stat) ) stat = 0
        ok_f = .true.
    end function

    subroutine machine_disallow(self, event, state, where, stat, errmsg)
        ! RETURN: nothing; from now on 'event' is a breach -- in 'state'
        !         alone, or in every state where absent -- until 'allow'
        !         lifts it; the breach line says 'disallowed since <where>'.
        !         FsmError where the model names no such event or state.
        class(Machine), intent(inout)                    :: self
        character(*), intent(in)                         :: event
        character(*), intent(in), optional               :: state
        class(*), intent(in), optional                   :: where
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        integer                                          :: s, e
        if( .not. known(self, event, state, stat, errmsg) ) return
        s = 0
        if( present(state) ) s = state_i(self, state)
        e = event_i(self, event)
        if( self%mask(s, e) ) return                      ! the first 'since' stands
        self%mask(s, e)       = .true.
        self%mask_since(s, e) = place_of(where)
    end subroutine

    subroutine machine_allow(self, event, state, where, stat, errmsg)
        ! RETURN: nothing; the mask 'disallow(event, state)' set is lifted --
        !         a mask set for another scope ('state' absent or a state)
        !         stays. FsmError where the model names no such word.
        class(Machine), intent(inout)                    :: self
        character(*), intent(in)                         :: event
        character(*), intent(in), optional               :: state
        class(*), intent(in), optional                   :: where
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        integer                                          :: s, e
        if( .not. known(self, event, state, stat, errmsg) ) return
        s = 0
        if( present(state) ) s = state_i(self, state)
        e = event_i(self, event)
        self%mask(s, e)       = .false.
        self%mask_since(s, e) = NOWHERE
    end subroutine

    subroutine machine_forbid(self, state, where, stat, errmsg)
        ! RETURN: nothing; from now on entering 'state' is a breach, until
        !         'permit'. Where the machine STANDS in it, one BREACH
        !         line is written at once: the test forbade the present.
        !         FsmError where the model names no such state.
        class(Machine), intent(inout)                    :: self
        character(*), intent(in)                         :: state
        class(*), intent(in), optional                   :: where
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        integer                                          :: s
        type(Place)                                      :: p
        if( .not. known(self, state = state, stat = stat, errmsg = errmsg) ) return
        s = state_i(self, state)
        if( self%forbid_f(s) ) return
        p = place_of(where)
        self%forbid_f(s)       = .true.
        self%forbid_since(s) = p
        self%permit_f(s)       = .false.
        self%permit_since(s) = NOWHERE
        if( self%current_f(s) ) then
            self%breach_n = self%breach_n + 1
            call emit(self, "BREACH" // where_text(p) // ": stands in '" // state // "' -- forbidden" // since_text(p))
        end if
    end subroutine

    subroutine machine_permit(self, state, where, stat, errmsg)
        ! RETURN: nothing; 'state' is no longer forbidden -- a state of the
        !         model's own 'forbidden:' too, until 'forbid' again.
        !         FsmError where the model names no such state.
        class(Machine), intent(inout)                    :: self
        character(*), intent(in)                         :: state
        class(*), intent(in), optional                   :: where
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        integer                                          :: s
        if( .not. known(self, state = state, stat = stat, errmsg = errmsg) ) return
        s = state_i(self, state)
        if( .not. self%forbid_f(s) ) return
        self%forbid_f(s)       = .false.
        self%forbid_since(s) = NOWHERE
        if( self%model_forbidden(s) ) then
            self%permit_f(s)       = .true.
            self%permit_since(s) = place_of(where)
        end if
    end subroutine

    subroutine machine_disallowed(self, event, block, state, where, stat, errmsg)
        ! RETURN: nothing, once 'block(self)' ran with 'event' disallowed (see
        !         'disallow') and it is allowed again -- Python's 'with
        !         m.disallowed(...)'. FsmError where the model names no such
        !         word; the block does not run then.
        class(Machine), intent(inout)                    :: self
        character(*), intent(in)                         :: event
        procedure(fsm_block)                             :: block
        character(*), intent(in), optional               :: state
        class(*), intent(in), optional                   :: where
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        if( .not. known(self, event, state, stat, errmsg) ) return
        call self%disallow(event, state, where)
        call block(self)
        call self%allow(event, state)
    end subroutine

    subroutine machine_forbidding(self, state, block, where, stat, errmsg)
        ! RETURN: nothing, once 'block(self)' ran with 'state' forbidden (see
        !         'forbid') and it is permitted again -- Python's 'with
        !         m.forbidding(...)'. FsmError where the model names no such
        !         state; the block does not run then.
        class(Machine), intent(inout)                    :: self
        character(*), intent(in)                         :: state
        procedure(fsm_block)                             :: block
        class(*), intent(in), optional                   :: where
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        if( .not. known(self, state = state, stat = stat, errmsg = errmsg) ) return
        call self%forbid(state, where)
        call block(self)
        call self%permit(state)
    end subroutine

    function machine_forbidden(self) result(list)
        ! RETURN: the states forbidden NOW, sorted -- the model's, less those
        !         permitted, with those forbidden since.
        class(Machine), intent(in) :: self
        type(string), allocatable  :: list(:)
        list = names(self, self%forbid_f)
    end function

    ! ============================================================== questions
    function machine_state(self, stat, errmsg) result(name)
        ! RETURN: the one state the machine stands in; FsmError where a set
        !         of states stands (dfa .false.): ask 'current()'.
        class(Machine), intent(in)                       :: self
        integer, intent(out), optional                   :: stat
        character(:), allocatable, intent(out), optional :: errmsg
        character(:), allocatable                        :: name
        type(string), allocatable                        :: list(:)
        if( present(stat) ) stat = 0
        name = ""
        if( count(self%current_f) /= 1 ) then
            call raise("the machine stands in " // here(self) // ": ask 'current()'", stat, errmsg)
            return
        end if
        list = names(self, self%current_f)
        name = list(1)%s
    end function

    function machine_current(self) result(list)
        ! RETURN: every state the machine stands in, sorted -- Python's
        !         'current()'.
        class(Machine), intent(in) :: self
        type(string), allocatable  :: list(:)
        list = names(self, self%current_f)
    end function

    logical function machine_in_state(self, state)
        ! RETURN: .true. where the machine stands in 'state'; .false. else.
        class(Machine), intent(in) :: self
        character(*), intent(in)   :: state
        integer                    :: s
        s = state_i(self, state)
        machine_in_state = .false.
        if( s > 0 ) machine_in_state = self%current_f(s)
    end function

    logical function machine_can(self, event)
        ! RETURN: .true. where 'event' would move the machine now; .false.
        !         else.
        class(Machine), intent(in) :: self
        character(*), intent(in)   :: event
        integer                    :: i, e
        e = event_i(self, event)
        machine_can = .false.
        do i = 1, size(self%edge_source)
            if( self%edge_event(i) /= e ) cycle
            if( .not. self%current_f(self%edge_source(i)) ) cycle
            if( masked_f(self, self%edge_source(i), e) ) cycle
            machine_can = .true.
            return
        end do
    end function

    function machine_allowed(self) result(list)
        ! RETURN: the events that would move the machine now, sorted.
        class(Machine), intent(in) :: self
        type(string), allocatable  :: list(:)
        integer                    :: e
        allocate(list(0))
        do e = 1, size(self%event_list)
            if( self%can(self%event_list(e)%s) ) list = [list, self%event_list(e)]
        end do
    end function

    function machine_trace(self) result(list)
        ! RETURN: every transition fired, in order: (where, state, event,
        !         state).
        class(Machine), intent(in)    :: self
        type(TraceEntry), allocatable :: list(:)
        list = self%trace_list
    end function

    ! ========================================================= the model alone
    function machine_path_to(self, state, start, masked) result(path)
        ! RETURN: the shortest sequence of events from 'start' -- the initial
        !         state where absent, 'now' for where the machine stands --
        !         into 'state' ('found_f', no event where 'start' is
        !         'state'); 'found_f' .false. where none leads there. Among
        !         equally short paths the first in event order; under the
        !         masks standing now unless 'masked' is .false.
        class(Machine), intent(in)         :: self
        character(*), intent(in)           :: state
        character(*), intent(in), optional :: start
        logical, intent(in), optional      :: masked
        type(EventPath)                    :: path
        logical, allocatable               :: seen(:)
        integer, allocatable               :: queue(:), parent(:), via(:)
        integer                            :: goal, head, tail, here_s, i, t, at, k
        logical                            :: masked_on

        masked_on = .true.
        if( present(masked) ) masked_on = masked
        goal = state_i(self, state)
        allocate(seen(size(self%state_list)), queue(size(self%state_list)), &
                 parent(size(self%state_list)), via(size(self%state_list)))
        seen = .false.
        if( .not. present(start) ) then
            seen(self%initial) = .true.
        else if( start == "now" ) then
            seen = self%current_f
        else
            seen(state_i(self, start)) = .true.
        end if
        allocate(path%event(0))
        if( goal > 0 ) then
            if( seen(goal) ) then
                path%found_f = .true.; return
            end if
        end if
        tail = 0
        do i = 1, size(seen)
            if( .not. seen(i) ) cycle
            tail = tail + 1; queue(tail) = i; parent(i) = 0
        end do
        head = 0
        do while( head < tail )
            head   = head + 1
            here_s = queue(head)
            ! successors of 'here_s', sorted by (event, target): the edge order
            do i = 1, size(self%edge_source)
                if( self%edge_source(i) /= here_s ) cycle
                if( masked_on ) then
                    if( masked_f(self, here_s, self%edge_event(i)) ) cycle
                end if
                t = self%edge_target(i)
                if( seen(t) ) cycle
                seen(t) = .true.; parent(t) = here_s; via(t) = i
                if( t == goal ) then
                    k  = 0
                    at = t
                    do while( parent(at) > 0 )
                        k = k + 1; at = parent(at)
                    end do
                    deallocate(path%event)
                    allocate(path%event(k))
                    at = t
                    do while( parent(at) > 0 )
                        path%event(k)%s = self%event_list(self%edge_event(via(at)))%s
                        k = k - 1; at = parent(at)
                    end do
                    path%found_f = .true.
                    return
                end if
                tail = tail + 1; queue(tail) = t
            end do
        end do
    end function

    function path_repr(self) result(text)
        ! RETURN: the path as Python prints what 'path_to' returns: the tuple
        !         "('request', 'grant')", "('grant',)", "()" -- or 'None'.
        class(EventPath), intent(in) :: self
        character(:), allocatable    :: text
        if( .not. self%found_f ) then
            text = "None"
        else if( size(self%event) == 1 ) then
            text = "(" // quoted_list(self%event) // ",)"
        else
            text = "(" // quoted_list(self%event) // ")"
        end if
    end function

    logical function machine_state_reachable(self, state, start, masked)
        ! RETURN: .true. where 'state' can be reached from 'start' (see
        !         'path_to'); .false. else.
        class(Machine), intent(in)         :: self
        character(*), intent(in)           :: state
        character(*), intent(in), optional :: start
        logical, intent(in), optional      :: masked
        type(EventPath)                    :: path
        path = self%path_to(state, start, masked)
        machine_state_reachable = path%found_f
    end function

    function forbidden_of(self, masked) result(flag)
        ! RETURN: per state, .true. where it is forbidden now ('masked'), or
        !         in the model as written (not 'masked').
        class(Machine), intent(in) :: self
        logical, intent(in)        :: masked
        logical, allocatable       :: flag(:)
        if( masked ) then
            flag = self%forbid_f
        else
            flag = self%model_forbidden
        end if
    end function

    logical function masked_arg(masked)
        ! RETURN: 'masked' where given; .true. else.
        logical, intent(in), optional :: masked
        masked_arg = .true.
        if( present(masked) ) masked_arg = masked
    end function

    function machine_unreachable(self, masked) result(list)
        ! RETURN: the states no path from the initial state reaches,
        !         forbidden ones left out, sorted; under the masks unless
        !         'masked' is .false.
        class(Machine), intent(in)    :: self
        logical, intent(in), optional :: masked
        type(string), allocatable     :: list(:)
        logical, allocatable          :: forbidden(:)
        integer                       :: s
        forbidden = forbidden_of(self, masked_arg(masked))
        allocate(list(0))
        do s = 1, size(self%state_list)
            if( forbidden(s) ) cycle
            if( self%state_reachable(self%state_list(s)%s, masked = masked_arg(masked)) ) cycle
            list = [list, self%state_list(s)]
        end do
    end function

    function machine_dead_ends(self, masked) result(list)
        ! RETURN: the states no event leaves that are neither final nor
        !         forbidden -- where a system would hang -- sorted; under the
        !         masks unless 'masked' is .false. (a mask can make one).
        class(Machine), intent(in)    :: self
        logical, intent(in), optional :: masked
        type(string), allocatable     :: list(:)
        logical, allocatable          :: forbidden(:)
        logical                       :: leaves_f
        integer                       :: s, i
        forbidden = forbidden_of(self, masked_arg(masked))
        allocate(list(0))
        do s = 1, size(self%state_list)
            leaves_f = .false.
            do i = 1, size(self%edge_source)
                if( self%edge_source(i) /= s ) cycle
                if( masked_arg(masked) ) then
                    if( masked_f(self, s, self%edge_event(i)) ) cycle
                end if
                leaves_f = .true.
                exit
            end do
            if( leaves_f .or. self%final(s) .or. forbidden(s) ) cycle
            list = [list, self%state_list(s)]
        end do
    end function

    function machine_forbidden_reachable(self, masked) result(list)
        ! RETURN: the forbidden states the model lets the system reach from
        !         the initial state, sorted; under the masks and the states
        !         forbidden now unless 'masked' is .false.
        class(Machine), intent(in)    :: self
        logical, intent(in), optional :: masked
        type(string), allocatable     :: list(:)
        logical, allocatable          :: forbidden(:)
        integer                       :: s
        forbidden = forbidden_of(self, masked_arg(masked))
        allocate(list(0))
        do s = 1, size(self%state_list)
            if( .not. forbidden(s) ) cycle
            if( .not. self%state_reachable(self%state_list(s)%s, masked = masked_arg(masked)) ) cycle
            list = [list, self%state_list(s)]
        end do
    end function

    integer function machine_check(self, masked) result(finding_n)
        ! RETURN: how many findings the MODEL has, each written as one line
        !         'MODEL: ...'; 0 where it has none. Asked of the model alone:
        !         states no path reaches, dead ends, forbidden states the
        !         model allows to be reached (each with the shortest way
        !         there) -- under the masks unless 'masked' is .false.
        class(Machine), intent(inout) :: self
        logical, intent(in), optional :: masked
        type(string), allocatable     :: list(:)
        type(EventPath)               :: path
        integer                       :: i
        finding_n = 0
        list = self%unreachable(masked)
        do i = 1, size(list)
            call emit(self, "MODEL: '" // list(i)%s // "' cannot be reached")
        end do
        finding_n = finding_n + size(list)
        list = self%dead_ends(masked)
        do i = 1, size(list)
            call emit(self, "MODEL: '" // list(i)%s // "' is a dead end -- no event leaves it")
        end do
        finding_n = finding_n + size(list)
        list = self%forbidden_reachable(masked)
        do i = 1, size(list)
            path = self%path_to(list(i)%s, masked = masked_arg(masked))
            call emit(self, "MODEL: forbidden '" // list(i)%s // "' is reachable: " // join(path%event, " "))
        end do
        finding_n = finding_n + size(list)
    end function

    ! ================================================================ the end
    integer function machine_report(self) result(breach_n)
        ! RETURN: the breaches seen, counting a non-final end; written before
        !         it, sorted, what the events covered of the model -- states
        !         counted without the model's forbidden ones:
        !             fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
        !               taken      idle ---( request )---> waiting   x2
        !               not taken  busy ---( fault )---> crashed
        !               never in   ...
        !               ended in   'idle'
        !         A machine with final states that ends elsewhere adds a
        !         BREACH line.
        class(Machine), intent(inout) :: self
        logical                       :: end_f
        logical, allocatable          :: goal(:)
        character(:), allocatable     :: label, suffix, scope
        integer                       :: i, s, e, n

        breach_n = self%breach_n
        end_f    = .not. any(self%final) .or. any(self%current_f .and. self%final)
        if( .not. end_f ) breach_n = breach_n + 1
        ! A FORBIDDEN STATE IS NO GOAL OF COVERAGE: counted out.
        goal = .not. self%model_forbidden
        call emit(self, self%name // ": " // str(count(goal .and. self%visit_n > 0)) // " of " // str(count(goal)) &
                        // " states visited, " // str(count(self%taken_n > 0)) // " of " &
                        // str(size(self%edge_source)) // " transitions taken, " // str(breach_n) &
                        // " breach" // trim(merge("  ", "es", breach_n == 1)))
        do i = 1, size(self%edge_source)
            n = self%taken_n(i)
            label  = merge("taken    ", "not taken", n > 0)
            suffix = ""
            if( n > 1 ) suffix = "   x" // str(n)
            call emit(self, "  " // label // "  " // self%state_list(self%edge_source(i))%s // " ---( " &
                            // self%event_list(self%edge_event(i))%s // " )---> " &
                            // self%state_list(self%edge_target(i))%s // suffix)
        end do
        do s = 1, size(self%state_list)
            if( self%visit_n(s) == 0 .and. .not. self%model_forbidden(s) ) &
                call emit(self, "  never in   '" // self%state_list(s)%s // "'")
        end do
        call emit(self, "  ended in   " // here(self))
        ! A PHASE NEVER LIFTED IS SAID: what still stands at the end, by
        ! (event, state) -- 'every state' (row 0) first.
        do e = 1, size(self%event_list)
            do s = 0, size(self%state_list)
                if( .not. self%mask(s, e) ) cycle
                if( s == 0 ) then
                    scope = "in every state"
                else
                    scope = "in '" // self%state_list(s)%s // "'"
                end if
                call emit(self, "  disallowed '" // self%event_list(e)%s // "' " // scope &
                                // since_text(self%mask_since(s, e)))
            end do
        end do
        do s = 1, size(self%state_list)
            if( self%forbid_f(s) .and. .not. self%model_forbidden(s) ) &
                call emit(self, "  forbidden  '" // self%state_list(s)%s // "'" // since_text(self%forbid_since(s)))
        end do
        do s = 1, size(self%state_list)
            if( self%permit_f(s) ) &
                call emit(self, "  permitted  '" // self%state_list(s)%s // "'" // since_text(self%permit_since(s)))
        end do
        if( .not. end_f ) &
            call emit(self, "BREACH: ended in " // here(self) // " -- final: " // join(names(self, self%final), ", "))
    end function

end module hwut_fsm
