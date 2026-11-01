! @hwut {
!     title      = "hwut_fsm: a state machine as the test's model of the system"
!     build      { framework = "make", executable = "%.exe" }
!     choices {
!         syntax    { features = ["fortran-fsm"] }
!         refused   { features = ["fortran-fsm"] }
!         dfa       { features = ["fortran-fsm"] }
!         nfa       { features = ["fortran-fsm"] }
!         forbidden { features = ["fortran-fsm"] }
!         model     { features = ["fortran-fsm"] }
!         report    { features = ["fortran-fsm"] }
!         masks     { features = ["fortran-fsm"] }
!     }
!     interactive = true
! }
!
! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: The Fortran port of 'python/TEST/test-hwut_fsm.py', choice for
!          choice, held against its GOOD files by '.link'. What Python prints
!          of its own values -- True, None, a tuple -- is printed so here,
!          since the GOOD file is one. Where Python raises FsmError, the
!          Fortran call is given 'stat' and 'errmsg', and the text is printed
!          the same way.
! _____________________________________________________________________________
module test_hwut_fsm_choices
    use hwut_text
    use hwut_pytext
    use hwut_runner
    use hwut_fsm
    implicit none

    ! THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
    ! a fault while busy crashes it -- which must never happen.
    character(*), parameter :: PROTOCOL = NL &
        // "    initial:   idle" // NL &
        // "    forbidden: crashed" // NL &
        // "    final:     idle" // NL &
        // "    idle    ---( request )---> waiting ---( grant )---> busy" // NL &
        // "    busy    ---( release )---> idle" // NL &
        // "    :       ---( fault )--->   crashed       # the state that began line 6" // NL &
        // "    waiting ---( cancel )---> idle" // NL

contains

    subroutine banner(label)
        character(*), intent(in) :: label
        call say("")
        call say("--- " // label // " ---")
    end subroutine

    function left(text, width) result(padded)
        ! RETURN: 'text' filled with blanks to 'width' -- Python's '%-8s'.
        character(*), intent(in)  :: text
        integer, intent(in)       :: width
        character(:), allocatable :: padded
        padded = text // repeat(" ", max(0, width - len(text)))
    end function

    subroutine run_syntax()
        type(Machine) :: m
        call banner("the protocol, written back")
        m = Machine_from_string(PROTOCOL)
        call say(m%to_string())
        call banner("the author's form: 'state', a chain, ':', blanks around '-->'")
        m = Machine_from_string(NL &
            // "        state A ---( event )---> state B" // NL &
            // "        :                ---(event2)---> state C ---(event) --> state D" // NL &
            // "        state E          # no transition yet" // NL &
            // "    ")
        call say(m%to_string())
    end subroutine

    subroutine run_refused()
        type(Machine)             :: m
        type(string)              :: text_list(7)
        character(:), allocatable :: message
        integer                   :: i, stat
        text_list = [string("A ---( x )---> B" // NL // ": ---( x )---> C"), &
                     string("A ---(  )---> B"), &
                     string(": ---( x )---> B"), &
                     string("A B ---( x )---> C"), &
                     string("initial: A, B" // NL // "A ---( x )---> B"), &
                     string("forbidden: Q" // NL // "A ---( x )---> B"), &
                     string("# nothing but a comment")]
        do i = 1, size(text_list)
            call banner(replace_all(text_list(i)%s, NL, " | "))
            m = Machine_from_string(text_list(i)%s, stat = stat, errmsg = message)
            if( stat == 0 ) then
                call say("accepted")
            else
                call say("FsmError: " // message)
            end if
        end do
    end subroutine

    subroutine run_dfa()
        type(Machine)                 :: m
        type(TraceEntry), allocatable :: trace(:)
        character(:), allocatable     :: line
        type(string)                  :: event(6)
        integer                       :: number
        logical                       :: moved
        event = [string("request"), string("release"), string("grant"), &
                 string("release"), string("jump"), string("request")]
        m = Machine_from_string(PROTOCOL)
        do number = 1, size(event)
            moved = m%fire(event(number)%s, where = number)
            call say("    " // left(event(number)%s, 8) // " -> " // left(repr(moved), 5) // " now " &
                     // left(m%state(), 8) // " allowed: " // join(m%allowed(), ", "))
        end do
        call banner("questions where it stands")
        call say("can('grant')   " // repr(m%can("grant")))
        call say("can('release') " // repr(m%can("release")))
        call say("in_state('waiting') " // repr(m%in_state("waiting")))
        trace = m%trace()
        line  = "trace:"
        do number = 1, size(trace)
            line = line // " " // trace(number)%where%str() // ":" // trace(number)%event // ">" // trace(number)%target
        end do
        call say(line)
    end subroutine

    subroutine run_nfa()
        type(Machine)             :: m
        character(:), allocatable :: message, state
        character                 :: event(3) = ["x", "z", "y"]
        integer                   :: i, stat
        logical                   :: ignored
        m = Machine_from_string(NL &
            // "        A ---( x )---> B ---( y )---> D" // NL &
            // "        : ---( x )---> C ---( y )---> E" // NL &
            // "        C ---( z )---> F" // NL &
            // "    ", dfa = .false.)
        do i = 1, 3
            ignored = m%fire(event(i), where = "t=" // event(i))
            call say("    after " // event(i) // ": " // join(m%current(), ", "))
        end do
        call banner("'state' asked of a set")
        call m%reset()
        ignored = m%fire("x")
        state = m%state(stat, message)
        if( stat == 0 ) then
            call say(state)
        else
            call say("FsmError: " // message)
        end if
    end subroutine

    subroutine run_forbidden()
        type(Machine) :: m
        type(string)  :: event(3)
        integer       :: number
        logical       :: moved
        event = [string("request"), string("grant"), string("fault")]
        m = Machine_from_string(PROTOCOL)
        do number = 1, 3
            moved = m%fire(event(number)%s, where = number)
            call say("    " // left(event(number)%s, 8) // " -> " // repr(moved))
        end do
        call say("now in " // m%state() // " -- breaches: " // str(m%breach_n))
    end subroutine

    subroutine run_model()
        type(Machine)   :: m
        type(EventPath) :: path
        type(string)    :: goal(4)
        integer         :: i, n
        logical         :: ignored
        goal = [string("busy"), string("crashed"), string("limbo"), string("idle")]
        m = Machine_from_string(PROTOCOL // NL // "    state limbo" // NL // "    limbo ---( kick )---> idle" // NL)
        n = m%check()
        call say("check: " // str(n))
        call banner("path_to")
        do i = 1, 4
            path = m%path_to(goal(i)%s)
            call say("    " // left(goal(i)%s, 8) // " " // path%repr())
        end do
        ignored = m%fire("request")
        path = m%path_to("busy", start = "now")
        call say("    busy from now: " // path%repr())
        call say("    state_reachable('idle', start='now'): " // repr(m%state_reachable("idle", start = "now")))
    end subroutine

    subroutine run_report()
        type(Machine) :: m
        type(string)  :: event(5)
        integer       :: i, n
        logical       :: ignored
        event = [string("request"), string("grant"), string("release"), string("request"), string("grant")]
        m = Machine_from_string(PROTOCOL, name = "protocol")
        do i = 1, 5
            ignored = m%fire(event(i)%s)
        end do
        n = m%report()
        call say("report returns " // str(n))
    end subroutine

    subroutine release_in_phase(m)
        ! RETURN: nothing; 'release' was fired, line 20 -- the block of the
        !         phase.
        class(Machine), intent(inout) :: m
        logical                       :: ignored
        ignored = m%fire("release", where = 20)
    end subroutine

    subroutine run_masks()
        type(Machine)             :: m
        type(EventPath)           :: path
        character(:), allocatable :: message
        integer                   :: n, stat
        logical                   :: moved

        m = Machine_from_string(PROTOCOL)
        call banner("'grant' disallowed in every state, since line 2")
        call m%disallow("grant", where = 2)
        moved = m%fire("request", where = 3)
        call say("    allowed now: " // join(m%allowed(), ", ") // " -- can('grant'): " // repr(m%can("grant")))
        moved = m%fire("grant", where = 4)
        path = m%path_to("busy")
        call say("    path_to('busy'):               " // path%repr())
        path = m%path_to("busy", masked = .false.)
        call say("    path_to('busy', masked=False): " // path%repr())
        n = m%check()
        call say("    check(): " // str(n))
        n = m%check(masked = .false.)
        call say("    check(masked=False): " // str(n))

        call banner("allowed again; 'busy' forbidden while standing in it")
        call m%allow("grant", where = 5)
        moved = m%fire("grant", where = 6)
        call m%forbid("busy", where = 7)
        moved = m%fire("release", where = 8)
        moved = m%fire("request", where = 9)
        moved = m%fire("grant", where = 10)

        call banner("permitted: 'busy', and the model's own 'crashed'")
        call m%permit("busy", where = 11)
        call m%permit("crashed", where = 12)
        moved = m%fire("fault", where = 13)
        call say("    fault -> " // repr(moved) // " -- now in " // m%state())

        call banner("a phase: 'release' disallowed in 'busy' for a block")
        call m%reset()
        moved = m%fire("request"); moved = m%fire("grant")
        call m%disallowed("release", release_in_phase, state = "busy", where = "phase")
        moved = m%fire("release", where = 21)
        call m%disallow("cancel", where = 22)
        n = m%report()

        call banner("refused: a word the model never names")
        call m%disallow("jump", stat = stat, errmsg = message)
        if( stat /= 0 ) call say("FsmError: " // message)
        call m%forbid("limbo", stat = stat, errmsg = message)
        if( stat /= 0 ) call say("FsmError: " // message)
        call m%allow("grant", state = "nowhere", stat = stat, errmsg = message)
        if( stat /= 0 ) call say("FsmError: " // message)
    end subroutine

end module test_hwut_fsm_choices

program test_hwut_fsm
    ! THE CHOICES ARE MODULE PROCEDURES: a procedure pointer to an internal
    ! one would need a trampoline, and with it an executable stack.
    use hwut_runner
    use test_hwut_fsm_choices
    implicit none
    type(HwutRunner) :: runner
    runner = HwutRunner("hwut_fsm: a state machine as the test's model of the system", [ &
                 HwutChoice("syntax", run_syntax), HwutChoice("refused", run_refused), &
                 HwutChoice("dfa", run_dfa), HwutChoice("nfa", run_nfa), &
                 HwutChoice("forbidden", run_forbidden), HwutChoice("model", run_model), &
                 HwutChoice("report", run_report), HwutChoice("masks", run_masks)])
    call runner%run()
end program test_hwut_fsm
