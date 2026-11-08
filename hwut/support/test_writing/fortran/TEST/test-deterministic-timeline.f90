! @hwut {
!     title      = "TriggerDispatcher: schedule, priority, and the end of time"
!     build      { framework = "make", target = "%.exe" }
!     choices {
!         abstract    { features = ["fortran-timeline"] }
!         cancel      { features = ["fortran-timeline"] }
!         edges       { features = ["fortran-timeline"] }
!         priority    { features = ["fortran-timeline"] }
!         schedule    { features = ["fortran-timeline"] }
!         stable      { features = ["fortran-timeline"] }
!         stop        { features = ["fortran-timeline"] }
!         termination { features = ["fortran-timeline"] }
!         yielding    { features = ["fortran-timeline"] }
!     }
!     interactive = true
! }
!
! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: The Fortran port of 'python/TEST/test-deterministic-timeline.py',
!          choice for choice, held against its GOOD files by '.link'. Where
!          Python awaits, Fortran steps a task.
! _____________________________________________________________________________
module timeline_triggers
    ! THE TEST'S OWN TRIGGERS AND TASKS -- classes extending the module's.
    use hwut_text
    use deterministic_timeline
    implicit none

    type, extends(Trigger) :: SpeakingTrigger
        logical                          :: silent_termination_f = .false.
        type(TriggerDispatcher), pointer :: dispatcher => null()
    contains
        procedure :: fire           => speaking_fire
        procedure :: on_termination => speaking_on_termination
    end type

    type, extends(Trigger) :: MuteTrigger                ! no 'on_termination'
    contains
        procedure :: fire => mute_fire
    end type

    type, extends(SpeakingTrigger) :: StoppingTrigger
    contains
        procedure :: fire => stopping_fire
    end type

    type, extends(Trigger) :: ProducingTrigger
        character(:), allocatable :: item                ! unallocated: None
        logical                   :: finished = .false.
    contains
        procedure :: fire           => producing_fire
        procedure :: on_termination => producing_on_termination
    end type

    type, extends(Task) :: Consumer
        type(ProducingTrigger), pointer :: producer => null()
        integer                         :: taken    = 0
    contains
        procedure :: advance => consume_advance
    end type

contains

    function setup_line(name, timeline) result(line)
        ! RETURN: 'SETUP: <name, left in 7> |<timeline>|'.
        character(*), intent(in)  :: name, timeline
        character(:), allocatable :: line
        character(7)              :: padded
        padded = name
        line   = "SETUP: " // padded // name(min(len(name), 7) + 1:) // " |" // timeline // "|"
    end function

    subroutine speaking(self, name, timeline)
        ! RETURN: nothing; 'self' is ready and said so -- Python's
        !         SpeakingTrigger(name, timeline).
        class(SpeakingTrigger), intent(inout) :: self
        character(*), intent(in)              :: name, timeline
        call self%init(timeline, name)
        call say(setup_line(name, timeline))
    end subroutine

    subroutine mute(self, name, timeline)
        ! RETURN: nothing; 'self' is ready and said so.
        type(MuteTrigger), intent(inout) :: self
        character(*), intent(in)         :: name, timeline
        call self%init(timeline, name)
        call say(setup_line(name, timeline) // "  (no on_termination override)")
    end subroutine

    subroutine speaking_fire(self, pseudo_time, status)
        class(SpeakingTrigger), intent(inout) :: self
        integer, intent(in)                   :: pseudo_time
        integer, intent(inout)                :: status
        call say("  [t:" // str(pseudo_time) // "] " // self%name // " fires")
    end subroutine

    subroutine speaking_on_termination(self, end_tick)
        class(SpeakingTrigger), intent(inout) :: self
        integer, intent(in)                   :: end_tick
        if( self%silent_termination_f ) return
        call say("  [end:" // str(end_tick) // "] " // self%name // " notified")
    end subroutine

    subroutine mute_fire(self, pseudo_time, status)
        class(MuteTrigger), intent(inout) :: self
        integer, intent(in)               :: pseudo_time
        integer, intent(inout)            :: status
        call say("  [t:" // str(pseudo_time) // "] " // self%name // " fires")
    end subroutine

    subroutine stopping_fire(self, pseudo_time, status)
        ! RETURN: nothing; fired once as its base does, then asked the run to
        !         leave.
        class(StoppingTrigger), intent(inout) :: self
        integer, intent(in)                   :: pseudo_time
        integer, intent(inout)                :: status
        call speaking_fire(self, pseudo_time, status)
        call say("  ... asks the dispatcher to stop")
        call self%dispatcher%stop()
    end subroutine

    subroutine producing_fire(self, pseudo_time, status)
        ! RETURN: nothing; one item prepared, stamped with its tick.
        class(ProducingTrigger), intent(inout) :: self
        integer, intent(in)                    :: pseudo_time
        integer, intent(inout)                 :: status
        self%item = "item@" // str(pseudo_time)
        call say("  [t:" // str(pseudo_time) // "] " // self%name // " prepared " // self%item)
    end subroutine

    subroutine producing_on_termination(self, end_tick)
        ! RETURN: nothing; end-of-stream announced to the consumer.
        class(ProducingTrigger), intent(inout) :: self
        integer, intent(in)                    :: end_tick
        self%finished = .true.
        call say("  [end:" // str(end_tick) // "] " // self%name // " announced end-of-stream")
    end subroutine

    logical function consume_advance(self) result(more_f)
        ! RETURN: .true. to wait for the next item (the yield); .false. once
        !         the end-of-stream was seen.
        class(Consumer), intent(inout) :: self
        do
            if( .not. allocated(self%producer%item) ) then
                if( self%producer%finished ) then
                    call say("  consumer saw end-of-stream after " // str(self%taken) // " item(s)")
                    more_f = .false.
                    return
                end if
                more_f = .true.
                return
            end if
            self%taken = self%taken + 1
            call say("        consumer took " // self%producer%item)
            deallocate(self%producer%item)
        end do
    end function

end module timeline_triggers

module test_deterministic_timeline_choices
    use hwut_text
    use hwut_runner
    use deterministic_timeline
    use timeline_triggers
    implicit none

contains

    subroutine banner(label)
        character(*), intent(in) :: label
        call say("")
        call say("--- " // label // " ---")
    end subroutine

    subroutine dispatch(trigger_list, stat)
        ! RETURN: nothing; a dispatcher over 'trigger_list' ran to its end --
        !         'stat' as 'run' reports it.
        type(TriggerRef), intent(in)   :: trigger_list(:)
        integer, intent(out), optional :: stat
        type(TriggerDispatcher)        :: d
        d = TriggerDispatcher(trigger_list)
        call d%run(stat)
    end subroutine

    subroutine run_schedule()
        type(SpeakingTrigger), target :: a, b, c
        type(TriggerDispatcher)       :: d
        call banner("staggered: A at 0, B at 2, C at 4")
        call speaking(a, "A", "1    "); call speaking(b, "B", "  1  "); call speaking(c, "C", "    1")
        call dispatch([ref(a), ref(b), ref(c)])
        call banner("a SHORT timeline stops contributing; the long one goes on")
        call speaking(a, "SHORT", "11"); call speaking(b, "LONG", "111111")
        call dispatch([ref(a), ref(b)])
        call banner("the SCHEDULE as built -- '[tick] (priority)name'")
        call speaking(a, "A", "12"); call speaking(b, "B", "21")
        d = TriggerDispatcher([ref(a), ref(b)])
        call say(d%repr())
    end subroutine

    subroutine run_priority()
        type(SpeakingTrigger), target :: a, b
        call banner("digits swap between ticks: B leads at 0, A leads at 1")
        call speaking(a, "A", "21"); call speaking(b, "B", "12")
        call dispatch([ref(a), ref(b)])
        call banner("0 is the strongest digit, 9 the weakest")
        call speaking(a, "WEAK", "9"); call speaking(b, "STRONG", "0")
        call dispatch([ref(a), ref(b)])
    end subroutine

    subroutine run_stable()
        type(SpeakingTrigger), target :: a, b, c
        call banner("three triggers, all digit 1 at tick 0")
        call speaking(a, "first", "1"); call speaking(b, "second", "1"); call speaking(c, "third", "1")
        call dispatch([ref(a), ref(b), ref(c)])
        call banner("registered BACKWARDS -- the order follows registration, not the name")
        call speaking(a, "third", "1"); call speaking(b, "second", "1"); call speaking(c, "first", "1")
        call dispatch([ref(a), ref(b), ref(c)])
    end subroutine

    subroutine run_termination()
        type(SpeakingTrigger), target :: a, b
        type(MuteTrigger), target     :: m
        call banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0")
        call speaking(a, "EARLY", "1    ")
        call dispatch([ref(a)])
        call banner("a trigger that NEVER fires is notified all the same")
        call speaking(a, "FIRES", "1  "); call speaking(b, "SILENT", "   ")
        call dispatch([ref(a), ref(b)])
        call banner("the LONGEST timeline sets end_tick for everybody")
        call speaking(a, "SHORT", "1"); call speaking(b, "LONG", "1      ")
        call dispatch([ref(a), ref(b)])
        call banner("a trigger that does not override is simply silent at the end")
        call speaking(a, "SPEAKS", "1 "); call mute(m, "MUTE", "1 ")
        call dispatch([ref(a), ref(m)])
    end subroutine

    subroutine run_yielding()
        type(ProducingTrigger), target  :: producer
        type(Consumer), target          :: take
        type(TriggerDispatcher), target :: d
        call banner("producer fires at every tick; consumer waits between them")
        call producer%init("111", "PROD")
        call say(setup_line("PROD", "111"))
        d = TriggerDispatcher([ref(producer)])
        take%producer => producer
        call gather([ref(d), ref(take)])
        call say("")
        call say("Each item was taken BEFORE the next tick prepared one: the run yields.")
    end subroutine

    subroutine run_stop()
        type(StoppingTrigger), target   :: stopper
        type(SpeakingTrigger), target   :: bystander
        type(TriggerDispatcher), target :: d
        call banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes")
        call speaking(stopper, "STOPPER", "1111")
        call speaking(bystander, "OTHER", "1111")
        d = TriggerDispatcher([ref(stopper), ref(bystander)])
        stopper%dispatcher => d
        call d%run()
        call say("")
        call say("end_tick is still the timeline's length, not the tick the run stopped at.")
    end subroutine

    subroutine run_cancel()
        type(SpeakingTrigger), target :: a
        type(TriggerDispatcher)       :: d
        logical                       :: ignored
        call banner("cancel() the task carrying run() -- no announcement follows")
        call speaking(a, "A", "1111111111")
        d = TriggerDispatcher([ref(a)])
        ignored = d%step()                                   ! one tick passes
        call d%cancel()
        if( d%await() == TIMELINE_CANCELLED ) call say("  run() was cancelled")
        call say("")
        call say("No '[end:..]' line above: the triggers were abandoned, not ended.")
    end subroutine

    subroutine run_edges()
        type(SpeakingTrigger), target :: a, b
        type(TriggerRef)              :: none(0)
        call banner("an EMPTY timeline -- end_tick 0")
        call speaking(a, "EMPTY", "")
        call dispatch([ref(a)])
        call banner("a timeline of BLANKS -- no digit, so nothing fires")
        call speaking(a, "BLANK", "    ")
        call dispatch([ref(a)])
        call banner("NO TRIGGERS at all -- nothing to announce, and no failure")
        call dispatch(none)
        call say("  (dispatcher ran; nothing was scheduled)")
        call banner("a timeline of blanks beside one that fires")
        call speaking(a, "BLANK", "   "); call speaking(b, "FIRES", " 1 ")
        call dispatch([ref(a), ref(b)])
    end subroutine

    subroutine run_abstract()
        type(Trigger), target :: bare
        integer               :: stat
        call banner("the BASE 'fire' is abstract -- it refuses")
        bare = Trigger("1", "BARE")
        call dispatch([ref(bare)], stat)
        if( stat == TIMELINE_NOT_IMPLEMENTED ) &
            call say("  NotImplementedError -- as owed: a trigger must say what it does")
        call banner("the BASE 'on_termination' is optional -- it is silent")
        bare = Trigger("", "BARE")
        call bare%on_termination(0)
        call say("  returned quietly; nothing raised, nothing printed")
        call banner("a NAME given is the name kept")
        bare = Trigger("1", "GIVEN")
        call say("  name: " // bare%name)
    end subroutine

end module test_deterministic_timeline_choices

program test_deterministic_timeline
    ! THE CHOICES ARE MODULE PROCEDURES: a procedure pointer to an internal
    ! one would need a trampoline, and with it an executable stack.
    use hwut_runner
    use test_deterministic_timeline_choices
    implicit none
    type(HwutRunner) :: runner
    runner = HwutRunner("TriggerDispatcher: schedule, priority, and the end of time", [ &
                 HwutChoice("schedule", run_schedule), HwutChoice("priority", run_priority), &
                 HwutChoice("stable", run_stable), HwutChoice("termination", run_termination), &
                 HwutChoice("yielding", run_yielding), HwutChoice("stop", run_stop), &
                 HwutChoice("cancel", run_cancel), HwutChoice("edges", run_edges), &
                 HwutChoice("abstract", run_abstract)])
    call runner%run()
end program test_deterministic_timeline
