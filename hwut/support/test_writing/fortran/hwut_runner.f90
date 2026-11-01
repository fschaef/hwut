! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN FORTRAN -- the port of
!          'python/hwut_runner.py': the same modes, the same words.
!
!     app --hwut-info      the info block; exit 0.
!     app <choice>         one choice; test output on stdout and stderr,
!                          '<hwut-end>' after it. '-' runs a choice-less test.
!     app --interactive    choices started over stdin, output into two named
!                          sink files per choice, 'done' on the original stdout.
!     app                  the choice-less test; where the application has
!                          choices, refused, naming them.
!
! USAGE:
!
!     program test_x
!         use hwut_runner
!         type(HwutRunner) :: runner
!         runner = HwutRunner("What this tests", [ &
!                      HwutChoice("plain",  run_plain), &
!                      HwutChoice("tricky", run_tricky)])
!         call runner%run()
!     contains
!         subroutine run_plain()
!             ...
!         end subroutine
!         ...
!     end program
!
! A choice is a NAME and a PROCEDURE POINTER to a subroutine without
! arguments. A choice-less test names its one choice "-". Before 'run' a test
! may set 'happy' (a list of patterns), 'same_f' and 'parallel_f'
! (interactive: choices run concurrently).
!
! THE INTERACTIVE PROTOCOL is Python's, line for line:
!     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
!     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
! EVERY CHOICE RUNS IN A CHILD PROCESS of its own ('fork' of libc, through
! 'hwut_posix'): a choice that says 'stop 3' or crashes ends that choice, not
! the session -- what Python gets by catching SystemExit. Fortran's units
! write through to descriptors 1 and 2, so a child that points those at its
! sinks has its 'write' land there; every unit is flushed before a fork.
! _____________________________________________________________________________
module hwut_runner
    use, intrinsic :: iso_fortran_env, only: output_unit, error_unit, input_unit
    use, intrinsic :: iso_c_binding,   only: c_int, c_null_char
    use hwut_text
    use hwut_posix
    implicit none
    private

    public :: HwutRunner, HwutChoice, choice_procedure, levenshtein_distance, levenshtein_best_match

    abstract interface
        subroutine choice_procedure()
        end subroutine
    end interface

    type :: HwutChoice
        character(:), allocatable                         :: name
        procedure(choice_procedure), pointer, nopass      :: run => null()
    end type

    type :: HwutRunner
        character(:), allocatable     :: title
        type(HwutChoice), allocatable :: choice_list(:)
        type(string), allocatable     :: sorted(:)
        type(string), allocatable     :: happy(:)
        logical                       :: same_f     = .false.
        logical                       :: parallel_f = .false.
        ! interactive mode
        integer(c_int)                :: control_fd = -1
        integer(c_int), allocatable   :: pending_pid(:)
        type(string), allocatable     :: pending_token(:)
    contains
        procedure :: run => runner_run
    end type

    interface HwutRunner
        module procedure runner_new
    end interface

    integer, parameter :: STATUS_PENDING = -1000

contains

    function runner_new(title, choice_list) result(self)
        ! RETURN: a HwutRunner over 'choice_list' (sorted by name for the info
        !         block and the indices), titled 'title', ready for 'run'.
        character(*), intent(in)     :: title
        type(HwutChoice), intent(in) :: choice_list(:)
        type(HwutRunner)             :: self
        integer                      :: i
        self%title       = title
        self%choice_list = choice_list
        allocate(self%sorted(size(choice_list)))
        do i = 1, size(choice_list)
            self%sorted(i)%s = choice_list(i)%name
        end do
        call sort_strings(self%sorted)
        allocate(self%happy(0), self%pending_pid(0), self%pending_token(0))
    end function

    logical function none_f(self)
        ! RETURN: .true. where the application is choice-less ('-' its one
        !         choice); .false. else.
        class(HwutRunner), intent(in) :: self
        none_f = size(self%choice_list) == 1
        if( none_f ) none_f = self%choice_list(1)%name == "-"
    end function

    integer function choice_index(self, name)
        ! RETURN: the position in 'choice_list' of the choice 'name'; 0 where
        !         none is.
        class(HwutRunner), intent(in) :: self
        character(*), intent(in)      :: name
        integer                       :: i
        do i = 1, size(self%choice_list)
            if( len(self%choice_list(i)%name) /= len(name) ) cycle
            if( self%choice_list(i)%name == name ) then
                choice_index = i; return
            end if
        end do
        choice_index = 0
    end function

    function info_lines(self) result(line_list)
        ! RETURN: the lines of the info block: the title (';' ended), the
        !         CHOICES, the HAPPY patterns, SAME, INTERACTIVE.
        class(HwutRunner), intent(in) :: self
        type(string), allocatable     :: line_list(:)
        integer                       :: i, n
        n = len(self%title)
        allocate(line_list(0))
        if( n > 0 ) then
            if( self%title(n:n) == ";" ) then
                call push(line_list, self%title)
            else
                call push(line_list, self%title // ";")
            end if
        else
            call push(line_list, ";")
        end if
        if( .not. none_f(self) ) call push(line_list, "CHOICES: " // join(self%sorted, ", ") // ";")
        do i = 1, size(self%happy)
            call push(line_list, "HAPPY: " // self%happy(i)%s // ";")
        end do
        if( self%same_f ) call push(line_list, "SAME;")
        call push(line_list, "INTERACTIVE;")
    end function

    subroutine run_one(self, i)
        ! RETURN: nothing; the choice at position 'i' ran, then '<hwut-end>'
        !         (R-70).
        class(HwutRunner), intent(in) :: self
        integer, intent(in)           :: i
        call self%choice_list(i)%run()
        call say("<hwut-end>")
        flush(output_unit)
    end subroutine

    subroutine finish(code)
        ! RETURN: never; the process ends with 'code', every unit flushed,
        !         nothing more said ('stop' would print the code).
        integer, intent(in) :: code
        flush(output_unit)
        flush(error_unit)
        stop code, quiet = .true.
    end subroutine

    ! ---------------------------------------------------------- the dispatch
    subroutine runner_run(self)
        ! RETURN: never; the mode the command line selects (see the head)
        !         ran, and the process ends with its status -- a refusal
        !         with 1.
        class(HwutRunner), intent(inout) :: self
        character(:), allocatable        :: word, best
        type(string), allocatable        :: line_list(:)
        integer                          :: i, n

        if( command_argument_count() < 1 ) then
            if( none_f(self) ) then
                call run_one(self, 1)
                call finish(0)
            end if
            call say("error: a choice is required: " // join(self%sorted, ", ") &
                     // " -- name one, or let 'hwut.play' ask.")
            call finish(1)
        end if
        call get_command_argument(1, length = n)
        allocate(character(n) :: word)
        call get_command_argument(1, word)

        select case( word )
        case( "-h", "--hi", "--hwut-info", "--sos", "--wtf" )
            line_list = info_lines(self)
            do i = 1, size(line_list)
                call say(line_list(i)%s)
            end do
            call finish(0)
        case( "--interactive" )
            call mode_interactive(self)
            call finish(0)
        end select

        i = choice_index(self, word)
        if( i > 0 ) then
            call run_one(self, i)
            call finish(0)
        end if
        if( none_f(self) ) then
            call say("error: '" // word // "': this application has no choices -- call it without one.")
            call finish(1)
        end if
        call say("error: choice '" // word // "' not available.")
        call say("error: available: " // join(self%sorted, ", ") // ".")
        best = levenshtein_best_match(word, self%sorted)
        if( len(best) > 0 ) call say("error: did you mean '" // best // "'?")
        call finish(1)
    end subroutine

    ! ------------------------------------------------------ interactive mode
    subroutine up(self, message)
        ! RETURN: nothing; 'message' and a newline were written on the UP
        !         channel.
        class(HwutRunner), intent(in) :: self
        character(*), intent(in)      :: message
        call write_line(self%control_fd, message)
    end subroutine

    subroutine reap(self, block_f)
        ! RETURN: nothing; every child that has ended was reported 'done';
        !         with 'block_f' it waited until none was left.
        class(HwutRunner), intent(inout) :: self
        logical, intent(in)              :: block_f
        integer(c_int)                   :: status, pid
        integer                          :: i
        integer(c_int), parameter        :: WNOHANG = 1
        do while( size(self%pending_pid) > 0 )
            pid = c_waitpid(-1_c_int, status, merge(0_c_int, WNOHANG, block_f))
            if( pid <= 0 ) return
            i = findloc(self%pending_pid, pid, dim = 1)
            if( i == 0 ) cycle
            call up(self, "done " // self%pending_token(i)%s // " " // str(exit_code_of(status)))
            self%pending_pid   = [self%pending_pid(:i - 1),   self%pending_pid(i + 1:)]
            self%pending_token = [self%pending_token(:i - 1), self%pending_token(i + 1:)]
        end do
    end subroutine

    integer function run_into_sinks(self, i, sink_out, sink_err, token) result(code)
        ! RETURN: the child's exit status, where the choice at position 'i'
        !         ran to its end in this call (sequential); STATUS_PENDING
        !         where it runs on (parallel, reported when reaped); 1 where
        !         no child could be made.
        class(HwutRunner), intent(inout) :: self
        integer, intent(in)              :: i
        character(*), intent(in)         :: sink_out, sink_err, token
        integer(c_int)                   :: pid, status, out, err, ignored
        character(:), allocatable        :: value
        integer                          :: n

        flush(output_unit)
        flush(error_unit)
        pid = c_fork()
        if( pid < 0 ) then
            code = 1; return
        end if
        if( pid == 0 ) then
            out = c_creat(c_text(sink_out), int(o'644', c_int))
            err = c_creat(c_text(sink_err), int(o'644', c_int))
            if( out < 0 .or. err < 0 ) call c_exit_now(1_c_int)
            ignored = c_dup2(out, 1_c_int); ignored = c_dup2(err, 2_c_int)
            ignored = c_close(out);         ignored = c_close(err)
            ignored = c_close(self%control_fd)
            call self%choice_list(i)%run()
            call get_environment_variable("HWUT_NO_TERMINAL", length = n)
            allocate(character(n) :: value)
            if( n > 0 ) call get_environment_variable("HWUT_NO_TERMINAL", value)
            if( len(value) == 0 ) call say("<hwut-end>")
            flush(output_unit)
            flush(error_unit)
            call c_exit_now(0_c_int)
        end if
        if( self%parallel_f ) then
            self%pending_pid   = [self%pending_pid, pid]
            call push(self%pending_token, token)
            code = STATUS_PENDING
            return
        end if
        do while( c_waitpid(pid, status, 0_c_int) < 0 )
        end do
        code = exit_code_of(status)
    end function

    integer function find_choice(self, token)
        ! RETURN: the position in 'choice_list' of the choice 'token' names --
        !         by name, by its index into the sorted list, or '-' for the
        !         choice-less test; 0 where it names none.
        class(HwutRunner), intent(in) :: self
        character(*), intent(in)      :: token
        integer                       :: k, ios
        find_choice = choice_index(self, token)
        if( find_choice > 0 .or. len(token) == 0 ) return
        if( verify(token, "0123456789") /= 0 ) return
        read(token, *, iostat = ios) k
        if( ios /= 0 ) return
        if( k < size(self%sorted) ) find_choice = choice_index(self, self%sorted(k + 1)%s)
    end function

    logical function interprete(self, line) result(go_on)
        ! RETURN: .true., the session goes on; .false., it ends ('quit').
        class(HwutRunner), intent(inout) :: self
        character(*), intent(in)         :: line
        type(string), allocatable        :: field(:)
        type(string), allocatable        :: line_list(:)
        integer                          :: i, status

        field = words(line)
        go_on = .true.
        if( size(field) == 1 ) then
            select case( field(1)%s )
            case( "quit", "q", "exit" )
                go_on = .false.
                return
            case( "info" )
                line_list = info_lines(self)
                do i = 1, size(line_list)
                    call up(self, "info: " // line_list(i)%s)
                end do
                call up(self, "done - 0")
                return
            end select
        else if( size(field) == 4 ) then
            if( field(1)%s == "run" ) then
                i = find_choice(self, field(2)%s)
                if( i == 0 ) then
                    call up(self, "fail " // field(2)%s // " unknown-choice")
                else
                    status = run_into_sinks(self, i, field(3)%s, field(4)%s, field(2)%s)
                    if( status /= STATUS_PENDING ) call up(self, "done " // field(2)%s // " " // str(status))
                end if
                return
            end if
        end if
        call up(self, "fail - bad-command")
    end function

    pure function words(line) result(field)
        ! RETURN: the words of 'line', split at blanks and tabs -- Python's
        !         'str.split()' on one line.
        character(*), intent(in)  :: line
        type(string), allocatable :: field(:)
        integer                   :: i, begin
        allocate(field(0))
        begin = 0
        do i = 1, len(line) + 1
            if( i <= len(line) ) then
                if( line(i:i) /= " " .and. line(i:i) /= TAB ) then
                    if( begin == 0 ) begin = i
                    cycle
                end if
            end if
            if( begin > 0 ) then
                call push(field, line(begin:i - 1))
                begin = 0
            end if
        end do
    end function

    subroutine read_line(line, end_f)
        ! RETURN: nothing; 'line' holds the next line of stdin, whatever its
        !         length; 'end_f' is .true. where stdin has ended instead.
        character(:), allocatable, intent(out) :: line
        logical, intent(out)                   :: end_f
        character(256)                         :: piece
        integer                                :: ios, n
        line  = ""
        end_f = .false.
        do
            read(input_unit, '(a)', advance = 'no', size = n, iostat = ios) piece
            if( is_iostat_end(ios) ) then
                end_f = len(line) == 0
                return
            end if
            line = line // piece(1:n)
            if( is_iostat_eor(ios) .or. ios /= 0 ) return
        end do
    end subroutine

    subroutine mode_interactive(self)
        ! RETURN: nothing, once the session ended ('quit' or end of input).
        !         The original stdout is the UP channel; descriptors 1 and 2
        !         point at a stray sink for what is said outside a choice.
        class(HwutRunner), intent(inout) :: self
        character(:), allocatable        :: line
        character(len=23, kind=kind('a')) :: path
        integer(c_int)                   :: stray, ignored
        logical                          :: end_f

        flush(output_unit)
        flush(error_unit)
        self%control_fd = c_dup(1_c_int)
        path  = "/tmp/hwut_stray_XXXXXX" // c_null_char
        stray = c_mkstemp(path)
        if( stray >= 0 ) then
            ignored = c_dup2(stray, 1_c_int); ignored = c_dup2(stray, 2_c_int)
            ignored = c_close(stray)
        end if
        do
            call reap(self, .false.)
            call read_line(line, end_f)
            if( end_f ) exit
            line = strip(line)
            if( len(line) == 0 ) cycle
            if( .not. interprete(self, line) ) exit
        end do
        call reap(self, .true.)
        call up(self, "bye")
    end subroutine

    ! ------------------------------------------------------- the suggestion
    pure integer function levenshtein_distance(a, b) result(distance)
        ! RETURN: the Levenshtein distance between 'a' and 'b', >= 0.
        character(*), intent(in) :: a, b
        integer                  :: previous(0:len(b)), current(0:len(b)), i, j
        if( a == b .and. len(a) == len(b) ) then
            distance = 0; return
        end if
        previous = [(j, j = 0, len(b))]
        do i = 1, len(a)
            current(0) = i
            do j = 1, len(b)
                current(j) = min(current(j - 1) + 1, previous(j) + 1, &
                                 previous(j - 1) + merge(0, 1, a(i:i) == b(j:j)))
            end do
            previous = current
        end do
        distance = previous(len(b))
    end function

    function levenshtein_best_match(needle, haystack) result(best)
        ! RETURN: the element of 'haystack' least distant from 'needle', the
        !         first of equals; '' where 'haystack' is empty.
        character(*), intent(in)  :: needle
        type(string), intent(in)  :: haystack(:)
        character(:), allocatable :: best
        integer                   :: i, d, best_d
        best   = ""
        best_d = -1
        if( text_index(haystack, needle) > 0 ) then
            best = needle; return
        end if
        do i = 1, size(haystack)
            d = levenshtein_distance(needle, haystack(i)%s)
            if( best_d < 0 .or. d < best_d ) then
                best_d = d
                best   = haystack(i)%s
            end if
        end do
    end function

end module hwut_runner
