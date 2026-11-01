! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
!          'python/deterministic_timeline.py'. Triggers fire at the ticks
!          their timeline strings mark with a digit; within one tick the
!          LOWER digit fires first, equal digits in registration order:
!
!              Trigger A: "1  12 1"
!              Trigger B: " 1  1 2"
!
!          When the last tick has passed, every trigger is told
!          'on_termination(end_tick)', 'end_tick' being the LONGEST
!          timeline's length. 'stop' leaves early and still announces; a
!          CANCELLED task announces nothing.
!
! A TRIGGER OF ONE'S OWN EXTENDS 'Trigger' and overrides its type-bound
! procedures -- Fortran's classes:
!
!     type, extends(Trigger) :: MyTrigger
!     contains
!         procedure :: fire => my_fire
!     end type
!     subroutine my_fire(self, pseudo_time, status)
!         class(MyTrigger), intent(inout) :: self
!         integer, intent(in)             :: pseudo_time
!         integer, intent(inout)          :: status        -- left alone: done
!         ...
!     end subroutine
!
!     type(MyTrigger), target :: a
!     type(TriggerDispatcher) :: d
!     call a%init("1 1 3", "SUB")
!     d = TriggerDispatcher([ref(a)])
!     call d%run()
!
! The dispatcher holds REFERENCES ('ref(a)': a polymorphic pointer), as
! Python's list holds the objects: what a trigger does to itself is seen by
! whoever else holds it. A trigger handed to it is declared 'target'.
!
! 'fire' of the base is ABSTRACT: it sets 'status' to TIMELINE_NOT_IMPLEMENTED
! and the run ends there -- Python's NotImplementedError. A run given no
! 'stat' to report it in stops the program with that name ('error stop'),
! as allocate does without 'stat='. 'on_termination' of the base says
! nothing.
!
! THE YIELD WITHOUT COROUTINES: Fortran has none, and its parallel constructs
! ('do concurrent', coarrays) promise NO order -- the one thing a timeline is
! for. So a 'Task' is an object with a STEP FUNCTION ('advance', deferred):
! one 'step' runs up to the next yield. 'gather' steps tasks in turn, in the
! order given -- the order 'asyncio.gather' gives them -- until each is done.
! A TriggerDispatcher IS the task of its run: one firing per step.
! _____________________________________________________________________________
module deterministic_timeline
    use hwut_text, only: str, NL
    implicit none
    private

    public :: Trigger, TriggerRef, Task, TaskRef, TriggerDispatcher, gather, ref
    public :: TIMELINE_OK, TIMELINE_NOT_IMPLEMENTED, TIMELINE_CANCELLED

    integer, parameter :: TIMELINE_OK = 0, TIMELINE_NOT_IMPLEMENTED = 1, TIMELINE_CANCELLED = 2

    type :: Trigger
        character(:), allocatable :: timeline
        character(:), allocatable :: name
    contains
        procedure :: init           => trigger_init
        procedure :: fire           => trigger_fire
        procedure :: on_termination => trigger_on_termination
    end type

    interface Trigger
        module procedure trigger_new
    end interface

    type :: TriggerRef
        class(Trigger), pointer :: p => null()
    end type

    type, abstract :: Task
        logical :: done_f      = .false.
        logical :: cancelled_f = .false.
        integer :: error       = TIMELINE_OK
    contains
        procedure(task_advance), deferred :: advance
        procedure                         :: step   => task_step
        procedure                         :: cancel => task_cancel
        procedure                         :: await  => task_await
    end type

    abstract interface
        logical function task_advance(self)
            ! RETURN: .true., the task yielded and has more to do; .false.,
            !         it is done ('self%error' says how it ended).
            import :: Task
            class(Task), intent(inout) :: self
        end function
    end interface

    type :: TaskRef
        class(Task), pointer :: p => null()
    end type

    type, extends(Task) :: TriggerDispatcher
        type(TriggerRef), allocatable :: trigger_list(:)
        integer, allocatable          :: firing_tick(:), firing_priority(:), firing_trigger(:)
        integer                       :: end_tick  = 0
        integer                       :: next      = 0      ! the firings done
        logical                       :: running_f = .true.
    contains
        procedure :: advance => dispatcher_advance
        procedure :: stop    => dispatcher_stop
        procedure :: run     => dispatcher_run
        procedure :: repr    => dispatcher_repr
    end type

    interface TriggerDispatcher
        module procedure dispatcher_new
    end interface

    ! 'ref(x)': THE REFERENCE TO A TRIGGER OR A TASK, for the lists the
    ! dispatcher and 'gather' take. (The structure constructor
    ! 'TriggerRef(x)' means the same; gfortran 13 fails to compile it for
    ! some extended types -- an internal compiler error -- so 'ref' it is.)
    interface ref
        module procedure trigger_ref, task_ref
    end interface

    integer, save :: anonymous_n = 0

contains

    ! ------------------------------------------------------------ the trigger
    subroutine trigger_init(self, timeline, name)
        ! RETURN: nothing; the trigger carries its timeline and its name -- a
        !         name chosen by the machine ('trigger-<n>') where none or ''
        !         is given.
        class(Trigger), intent(inout)      :: self
        character(*), intent(in)           :: timeline
        character(*), intent(in), optional :: name
        self%timeline = timeline
        if( present(name) ) then
            if( len(name) > 0 ) then
                self%name = name
                return
            end if
        end if
        anonymous_n = anonymous_n + 1
        self%name   = "trigger-" // str(anonymous_n)
    end subroutine

    function trigger_new(timeline, name) result(self)
        ! RETURN: a plain Trigger -- see 'init'.
        character(*), intent(in)           :: timeline
        character(*), intent(in), optional :: name
        type(Trigger)                      :: self
        call self%init(timeline, name)
    end function

    subroutine trigger_fire(self, pseudo_time, status)
        ! RETURN: nothing; 'status' is TIMELINE_NOT_IMPLEMENTED -- the base
        !         'fire' is abstract: a trigger that does nothing when its
        !         tick comes has no reason to stand in the timeline. An
        !         override does what the trigger does at 'pseudo_time' and
        !         leaves 'status' (TIMELINE_OK) alone.
        class(Trigger), intent(inout) :: self
        integer, intent(in)           :: pseudo_time
        integer, intent(inout)        :: status
        status = TIMELINE_NOT_IMPLEMENTED
    end subroutine

    subroutine trigger_on_termination(self, end_tick)
        ! RETURN: nothing; the base says nothing at the end of the timeline
        !         -- overriding is optional, unlike 'fire'.
        class(Trigger), intent(inout) :: self
        integer, intent(in)           :: end_tick
    end subroutine

    function trigger_ref(object) result(reference)
        ! RETURN: a TriggerRef pointing at 'object' -- which must be a
        !         'target' that outlives the reference.
        class(Trigger), target, intent(inout) :: object
        type(TriggerRef)                      :: reference
        reference%p => object
    end function

    function task_ref(object) result(reference)
        ! RETURN: a TaskRef pointing at 'object' -- which must be a 'target'
        !         that outlives the reference.
        class(Task), target, intent(inout) :: object
        type(TaskRef)                      :: reference
        reference%p => object
    end function

    ! ---------------------------------------------------------------- the task
    logical function task_step(self) result(more_f)
        ! RETURN: .true., the task yielded and goes on; .false., it is done
        !         or cancelled -- then it is not stepped again.
        class(Task), intent(inout) :: self
        more_f = .false.
        if( self%done_f ) return
        if( .not. self%advance() ) self%done_f = .true.
        more_f = .not. self%done_f
    end function

    subroutine task_cancel(self)
        ! RETURN: nothing; the task is abandoned: never stepped again, and
        !         what it would have done at its end is not done.
        class(Task), intent(inout) :: self
        self%done_f      = .true.
        self%cancelled_f = .true.
    end subroutine

    integer function task_await(self) result(status)
        ! RETURN: the task's end, once it is done: TIMELINE_OK,
        !         TIMELINE_CANCELLED where it was cancelled (Python's
        !         CancelledError), or the error it ended with.
        class(Task), intent(inout) :: self
        do while( self%step() )
        end do
        status = merge(TIMELINE_CANCELLED, self%error, self%cancelled_f)
    end function

    subroutine gather(task_list)
        ! RETURN: nothing, once every task is done -- stepped in turn, in the
        !         order given, each up to its next yield.
        type(TaskRef), intent(in) :: task_list(:)
        logical                   :: live_f, ignored
        integer                   :: i
        live_f = .true.
        do while( live_f )
            live_f = .false.
            do i = 1, size(task_list)
                if( task_list(i)%p%done_f ) cycle
                ignored = task_list(i)%p%step()
                live_f  = .true.
            end do
        end do
    end subroutine

    ! ---------------------------------------------------------- the dispatcher
    function dispatcher_new(trigger_list) result(self)
        ! RETURN: a TriggerDispatcher over 'trigger_list', its schedule built:
        !         the firings ordered by tick, within a tick by digit, between
        !         equal digits by registration -- read off the timelines in
        !         exactly that order, so no sort is needed.
        type(TriggerRef), intent(in) :: trigger_list(:)
        type(TriggerDispatcher)      :: self
        integer                      :: t, digit, k, n
        character                    :: c
        allocate(self%trigger_list, source = trigger_list)
        self%end_tick     = 0
        do k = 1, size(trigger_list)
            self%end_tick = max(self%end_tick, len(trigger_list(k)%p%timeline))
        end do
        allocate(self%firing_tick(0), self%firing_priority(0), self%firing_trigger(0))
        do t = 1, self%end_tick
            do digit = 0, 9
                c = achar(iachar("0") + digit)
                do k = 1, size(trigger_list)
                    n = len(trigger_list(k)%p%timeline)
                    if( t > n ) cycle
                    if( trigger_list(k)%p%timeline(t:t) /= c ) cycle
                    self%firing_tick     = [self%firing_tick, t - 1]
                    self%firing_priority = [self%firing_priority, digit]
                    self%firing_trigger  = [self%firing_trigger, k]
                end do
            end do
        end do
    end function

    subroutine dispatcher_stop(self)
        ! RETURN: nothing; the run leaves the timeline before its next firing
        !         -- and still announces termination.
        class(TriggerDispatcher), intent(inout) :: self
        self%running_f = .false.
    end subroutine

    logical function dispatcher_advance(self) result(more_f)
        ! RETURN: .true. after one firing (the yield: a consumer of what the
        !         trigger produced may progress); .false. once the timeline
        !         passed, or 'stop' cut it short, and every trigger was told
        !         'on_termination(end_tick)' -- or a trigger's 'fire' refused
        !         ('self%error'), when nobody is told anything.
        class(TriggerDispatcher), intent(inout) :: self
        integer                                 :: k, status
        more_f = .false.
        if( self%running_f .and. self%next < size(self%firing_tick) ) then
            self%next = self%next + 1
            k         = self%firing_trigger(self%next)
            status    = TIMELINE_OK
            call self%trigger_list(k)%p%fire(self%firing_tick(self%next), status)
            if( status /= TIMELINE_OK ) then
                self%error = status
                return
            end if
            more_f = .true.
            return
        end if
        do k = 1, size(self%trigger_list)
            call self%trigger_list(k)%p%on_termination(self%end_tick)
        end do
    end function

    subroutine dispatcher_run(self, stat)
        ! RETURN: nothing, once the timeline passed and the triggers were
        !         told; 'stat' TIMELINE_OK, or TIMELINE_NOT_IMPLEMENTED where
        !         a trigger's 'fire' refused. Where 'stat' is absent, such a
        !         refusal stops the program ('error stop'), naming it.
        class(TriggerDispatcher), intent(inout) :: self
        integer, intent(out), optional          :: stat
        integer                                 :: status
        status = self%await()
        if( present(stat) ) then
            stat = status
        else if( status == TIMELINE_NOT_IMPLEMENTED ) then
            error stop "NotImplementedError: a trigger's 'fire' says nothing it does"
        end if
    end subroutine

    function dispatcher_repr(self) result(text)
        ! RETURN: the built timeline: 'TriggerDispatcher', then one line per
        !         scheduled firing, '[tick] (priority)name', in the order of
        !         the run.
        class(TriggerDispatcher), intent(in) :: self
        character(:), allocatable            :: text
        integer                              :: i
        text = "TriggerDispatcher"
        do i = 1, size(self%firing_tick)
            text = text // NL // "[" // str(self%firing_tick(i)) // "] (" // str(self%firing_priority(i)) &
                   // ")" // self%trigger_list(self%firing_trigger(i))%p%name
        end do
    end function

end module deterministic_timeline
