! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
!          'python/hwut_vterm.py'. libvterm, a pseudo-terminal and a process
!          on it are C's world: this module BINDS the C port
!          ('../c/hwut_vterm.c', which finds libvterm by 'dlopen') through
!          ISO_C_BINDING and gives it Fortran's classes, texts and errors.
!
!     use hwut_vterm
!     type(Screen)     :: s
!     type(Cell)       :: c
!     type(VtermError) :: error
!     integer          :: stat
!     s = Screen(24, 80, stat, error)
!     if( stat /= 0 ) print '(a)', "NOT PROBED: " // error%message
!     n = s%feed(ESC // "[1mbold" // ESC // "[0m plain")
!     print '(a)', s%line(0)                     -- 'bold plain'
!     c = s%cell(0, 0)                           -- c%bold_f .true.
!     call s%close()
!
! ROWS AND COLUMNS COUNT FROM 0, as the terminal's own sequences are written
! about and as Python counts them: they are places on a screen, not array
! positions.
!
! TWO CLASSES:
!     Screen      the grid alone: bytes in, cells out. No process.
!     Terminal    a screen an APPLICATION RUNS IN, on a pseudo-terminal
!                 ('extends(Screen)': every Screen procedure applies).
! A Screen is OPENED by its constructor and CLOSED by 'close', as a Fortran
! unit is: the C object it stands for lives in between. No finalizer frees
! it -- a copy of a Screen is the same screen, as a copy of a unit number
! is the same unit.
!
! A CALLBACK ('on_change', 'on_event') is a Fortran procedure; the C module
! calls a 'bind(c)' trampoline here, which finds the procedure in a table
! of this module ('slot') and calls it with Fortran texts.
!
! ERRORS: what Python raises -- 'LibraryMissing', 'IndexError', 'KeyError',
! 'TimeoutError', 'RuntimeError' -- is a 'stat' and a 'VtermError' (kind:
! the exception's name, message: its text) where the caller passes them;
! where it does not, the program stops with '<kind>: <message>'.
!
! WANTS libvterm AT RUN TIME ('libvterm.so.0', or the file HWUT_LIBVTERM
! names); no header of it is needed to build. Link: '-ldl -lutil'.
! _____________________________________________________________________________
module hwut_vterm
    use, intrinsic :: iso_c_binding
    use hwut_text
    use hwut_posix, only: c_text, c_string, c_free
    implicit none
    private

    public :: Screen, Terminal, Cell, VtermError, VtermEvent, change_callback, event_callback
    public :: detection_text, reset_library, LIBRARY_VARIABLE, ATTRIBUTE_NAME, ATTRIBUTE_SGR

    character(*), parameter :: LIBRARY_VARIABLE = "HWUT_LIBVTERM"
    character(9), parameter :: ATTRIBUTE_NAME(7) = ["bold     ", "italic   ", "underline", "blink    ", &
                                                    "reverse  ", "conceal  ", "strike   "]
    character(1), parameter :: ATTRIBUTE_SGR(7)  = ["1", "3", "4", "5", "7", "8", "9"]

    ! ------------------------------------------- the C structures, as declared
    type, bind(c) :: c_error_t
        character(kind=c_char) :: kind(32), message(2048)
    end type

    type, bind(c) :: c_cell_t
        character(kind=c_char) :: text(32)
        integer(c_int)         :: width, bold_f, italic_f, underline_f, blink_f, reverse_f, conceal_f, strike_f
        integer(c_int)         :: foreground_f
        integer(c_signed_char) :: foreground(3)
        integer(c_int)         :: background_f
        integer(c_signed_char) :: background(3)
    end type

    type, bind(c) :: c_screen_t
        integer(c_int)  :: row_n, column_n
        type(c_ptr)     :: terminal, screen, state
        type(c_error_t) :: error
    end type

    type, bind(c) :: c_event_t
        type(c_ptr)    :: kind
        integer(c_int) :: row, column, row_end, column_end
        type(c_ptr)    :: name
        integer(c_int) :: value_f, value
    end type

    ! ------------------------------------------------------ the Fortran faces
    type :: VtermError
        character(:), allocatable :: kind, message
    end type

    type :: Cell
        character(:), allocatable :: text          ! '' unwritten, and right of a wide one
        integer                   :: width = 1
        logical                   :: bold_f = .false., italic_f = .false., underline_f = .false., &
                                     blink_f = .false., reverse_f = .false., conceal_f = .false., &
                                     strike_f = .false.
        logical                   :: foreground_f = .false., background_f = .false.  ! .false.: the default
        integer                   :: foreground(3) = 0, background(3) = 0
    contains
        procedure :: attribute_text => cell_attribute_text
    end type

    type :: VtermEvent                             ! one thing the terminal did
        character(:), allocatable :: kind          ! damage, cursor, property, bell
        integer                   :: row = 0, column = 0, row_end = 0, column_end = 0
        character(:), allocatable :: name          ! a property's
        logical                   :: value_f = .false.
        integer                   :: value = 0
    contains
        procedure :: str => event_str
    end type

    abstract interface
        subroutine change_callback(name, line_list)
            ! RETURN: nothing; told that the region 'name' now reads 'line_list'.
            import :: string
            character(*), intent(in) :: name
            type(string), intent(in) :: line_list(:)
        end subroutine
        subroutine event_callback(event)
            ! RETURN: nothing; told one raw event.
            import :: VtermEvent
            type(VtermEvent), intent(in) :: event
        end subroutine
    end interface

    type :: Screen
        type(c_ptr) :: handle   = c_null_ptr
        integer     :: row_n    = 0
        integer     :: column_n = 0
    contains
        procedure :: close     => screen_close
        procedure :: feed      => screen_feed
        procedure :: cursor    => screen_cursor
        procedure :: cell      => screen_cell
        procedure :: line      => screen_line
        procedure :: line_list => screen_line_list
    end type

    type, extends(Screen) :: Terminal
    contains
        procedure :: close       => terminal_close
        procedure :: feed        => terminal_feed
        procedure :: on_event    => terminal_on_event
        procedure :: on_change   => terminal_on_change
        procedure :: region      => terminal_region
        procedure :: region_text => terminal_region_text
        procedure :: report      => terminal_report
        procedure :: answer      => terminal_answer
        procedure :: send        => terminal_send
        procedure :: press       => terminal_press
        procedure :: run         => terminal_run
        procedure :: pump        => terminal_pump
        procedure :: expect      => terminal_expect
        procedure :: wait        => terminal_wait
    end type

    interface Screen
        module procedure screen_new
    end interface

    interface Terminal
        module procedure terminal_new
    end interface

    ! THE TABLE OF CALLBACKS: the C module is handed 'c_loc(slot(k))'.
    type :: slot_t
        procedure(change_callback), pointer, nopass :: change_f => null()
        procedure(event_callback),  pointer, nopass :: event_f  => null()
    end type
    integer, parameter          :: SLOT_MAX = 64
    type(slot_t), target, save  :: slot(SLOT_MAX)
    integer, save               :: slot_n = 0

    ! ------------------------------------------------------ the C functions
    interface
        type(c_ptr) function VtermScreen_new(row_n, column_n, error) bind(c, name="VtermScreen_new")
            import :: c_ptr, c_int, c_error_t
            integer(c_int), value :: row_n, column_n
            type(c_error_t)       :: error
        end function
        subroutine VtermScreen_free(self) bind(c, name="VtermScreen_free")
            import :: c_ptr
            type(c_ptr), value :: self
        end subroutine
        integer(c_size_t) function VtermScreen_feed(self, data, length) bind(c, name="VtermScreen_feed")
            import :: c_ptr, c_char, c_size_t
            type(c_ptr), value                 :: self
            character(kind=c_char), intent(in) :: data(*)
            integer(c_size_t), value           :: length
        end function
        subroutine VtermScreen_cursor(self, row, column) bind(c, name="VtermScreen_cursor")
            import :: c_ptr, c_int
            type(c_ptr), value :: self
            integer(c_int)     :: row, column
        end subroutine
        integer(c_int) function VtermScreen_cell(self, row, column, cell) bind(c, name="VtermScreen_cell")
            import :: c_ptr, c_int, c_cell_t
            type(c_ptr), value    :: self
            integer(c_int), value :: row, column
            type(c_cell_t)        :: cell
        end function
        type(c_ptr) function VtermScreen_line(self, row, buffer, size) bind(c, name="VtermScreen_line")
            import :: c_ptr, c_int, c_char, c_size_t
            type(c_ptr), value       :: self
            integer(c_int), value    :: row
            character(kind=c_char)   :: buffer(*)
            integer(c_size_t), value :: size
        end function
        type(c_ptr) function Vterm_detection_text(buffer, size) bind(c, name="Vterm_detection_text")
            import :: c_ptr, c_char, c_size_t
            character(kind=c_char)   :: buffer(*)
            integer(c_size_t), value :: size
        end function
        subroutine Vterm_reset_library() bind(c, name="Vterm_reset_library")
        end subroutine
        type(c_ptr) function VtermTerminal_new(row_n, column_n, settle_s, error) bind(c, name="VtermTerminal_new")
            import :: c_ptr, c_int, c_double, c_error_t
            integer(c_int), value :: row_n, column_n
            real(c_double), value :: settle_s
            type(c_error_t)       :: error
        end function
        subroutine VtermTerminal_free(self) bind(c, name="VtermTerminal_free")
            import :: c_ptr
            type(c_ptr), value :: self
        end subroutine
        subroutine VtermTerminal_on_event(self, f, context) bind(c, name="VtermTerminal_on_event")
            import :: c_ptr, c_funptr
            type(c_ptr), value    :: self, context
            type(c_funptr), value :: f
        end subroutine
        subroutine VtermTerminal_on_change(self, f, context) bind(c, name="VtermTerminal_on_change")
            import :: c_ptr, c_funptr
            type(c_ptr), value    :: self, context
            type(c_funptr), value :: f
        end subroutine
        subroutine VtermTerminal_region(self, name, row, row_n, column, column_n) bind(c, name="VtermTerminal_region")
            import :: c_ptr, c_int, c_char
            type(c_ptr), value                 :: self
            character(kind=c_char), intent(in) :: name(*)
            integer(c_int), value              :: row, row_n, column, column_n
        end subroutine
        type(c_ptr) function VtermTerminal_region_text(self, name, line_n) bind(c, name="VtermTerminal_region_text")
            import :: c_ptr, c_char, c_size_t
            type(c_ptr), value                 :: self
            character(kind=c_char), intent(in) :: name(*)
            integer(c_size_t)                  :: line_n
        end function
        subroutine VtermTerminal_lines_free(line_list, line_n) bind(c, name="VtermTerminal_lines_free")
            import :: c_ptr, c_size_t
            type(c_ptr), value       :: line_list
            integer(c_size_t), value :: line_n
        end subroutine
        integer(c_size_t) function VtermTerminal_report(self) bind(c, name="VtermTerminal_report")
            import :: c_ptr, c_size_t
            type(c_ptr), value :: self
        end function
        integer(c_size_t) function VtermTerminal_feed(self, data, length) bind(c, name="VtermTerminal_feed")
            import :: c_ptr, c_char, c_size_t
            type(c_ptr), value                 :: self
            character(kind=c_char), intent(in) :: data(*)
            integer(c_size_t), value           :: length
        end function
        type(c_ptr) function VtermTerminal_answer(self, length) bind(c, name="VtermTerminal_answer")
            import :: c_ptr, c_size_t
            type(c_ptr), value :: self
            integer(c_size_t)  :: length
        end function
        integer(c_int) function VtermTerminal_send(self, text, react_s) bind(c, name="VtermTerminal_send")
            import :: c_ptr, c_int, c_char, c_double
            type(c_ptr), value                 :: self
            character(kind=c_char), intent(in) :: text(*)
            real(c_double), value              :: react_s
        end function
        integer(c_int) function VtermTerminal_press(self, key, modifier, react_s) bind(c, name="VtermTerminal_press")
            import :: c_ptr, c_int, c_char, c_double
            type(c_ptr), value                 :: self, modifier
            character(kind=c_char), intent(in) :: key(*)
            real(c_double), value              :: react_s
        end function
        integer(c_int) function VtermTerminal_run(self, argv, cwd, start_s) bind(c, name="VtermTerminal_run")
            import :: c_ptr, c_int, c_double
            type(c_ptr), value :: self, cwd
            type(c_ptr)        :: argv(*)
            real(c_double), value :: start_s
        end function
        integer(c_int) function VtermTerminal_pump(self, first_s) bind(c, name="VtermTerminal_pump")
            import :: c_ptr, c_int, c_double
            type(c_ptr), value    :: self
            real(c_double), value :: first_s
        end function
        integer(c_int) function VtermTerminal_expect(self, text, timeout_s, row, column) &
                                bind(c, name="VtermTerminal_expect")
            import :: c_ptr, c_int, c_char, c_double
            type(c_ptr), value                 :: self
            character(kind=c_char), intent(in) :: text(*)
            real(c_double), value              :: timeout_s
            integer(c_int)                     :: row, column
        end function
        integer(c_int) function VtermTerminal_wait(self, timeout_s, status) bind(c, name="VtermTerminal_wait")
            import :: c_ptr, c_int, c_double
            type(c_ptr), value    :: self
            real(c_double), value :: timeout_s
            integer(c_int)        :: status
        end function
    end interface

contains

    ! ============================================================ the small
    function from_c(chars) result(text)
        ! RETURN: the NUL-ended C text in the array 'chars' as a Fortran text.
        character(kind=c_char), intent(in) :: chars(:)
        character(:), allocatable          :: text
        integer                            :: i, n
        n = size(chars)
        do i = 1, size(chars)
            if( chars(i) == c_null_char ) then
                n = i - 1; exit
            end if
        end do
        allocate(character(n) :: text)
        do i = 1, n
            text(i:i) = chars(i)
        end do
    end function

    subroutine fail(e, stat, error)
        ! RETURN: nothing, where the caller asked for 'stat': it is 1 and
        !         'error' holds what C said; never, else -- the program stops
        !         with '<kind>: <message>', as an uncaught exception.
        type(c_error_t), intent(in)               :: e
        integer, intent(out), optional            :: stat
        type(VtermError), intent(out), optional   :: error
        if( present(error) ) then
            error%kind    = from_c(e%kind)
            error%message = from_c(e%message)
        end if
        if( .not. present(stat) ) error stop from_c(e%kind) // ": " // from_c(e%message)
        stat = 1
    end subroutine

    subroutine fail_here(self, stat, error)
        ! RETURN: nothing; the error the screen 'self' holds was raised (see
        !         'fail').
        class(Screen), intent(in)               :: self
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        type(c_screen_t), pointer               :: s
        call c_f_pointer(self%handle, s)
        call fail(s%error, stat, error)
    end subroutine

    function detection_text() result(text)
        ! RETURN: 'libvterm found: <name>' where the library loads; else the
        !         text of 'LibraryMissing' -- what is wrong and how to
        !         install it.
        character(:), allocatable              :: text
        character(kind=c_char), allocatable    :: buffer(:)
        type(c_ptr)                            :: ignored
        allocate(buffer(4096))
        ignored = Vterm_detection_text(buffer, size(buffer, kind = c_size_t))
        text = from_c(buffer)
    end function

    subroutine reset_library()
        ! RETURN: nothing; the library is looked for again at the next
        !         screen, and its layout measured again -- as
        !         'hwut_vterm._library = None'.
        call Vterm_reset_library()
    end subroutine

    ! ============================================================== the cell
    function cell_attribute_text(self) result(text)
        ! RETURN: the attributes that are set, by name, in one fixed order,
        !         separated by blanks -- 'bold reverse'; '' where none.
        class(Cell), intent(in)   :: self
        character(:), allocatable :: text
        logical                   :: flag(7)
        integer                   :: i
        flag = [self%bold_f, self%italic_f, self%underline_f, self%blink_f, self%reverse_f, self%conceal_f, &
                self%strike_f]
        text = ""
        do i = 1, 7
            if( .not. flag(i) ) cycle
            if( len(text) > 0 ) text = text // " "
            text = text // trim(ATTRIBUTE_NAME(i))
        end do
    end function

    function event_str(self) result(text)
        ! RETURN: the event on one line, as a test prints it.
        class(VtermEvent), intent(in) :: self
        character(:), allocatable     :: text
        select case( self%kind )
        case( "damage" )
            text = "damage    rows " // str(self%row) // ".." // str(self%row_end) // "  columns " &
                   // str(self%column) // ".." // str(self%column_end)
        case( "cursor" )
            text = "cursor    (" // str(self%row) // ", " // str(self%column) // ")"
            if( self%value == 0 ) text = text // "  hidden"
        case( "property" )
            if( self%value_f ) then
                text = "property  " // self%name // " = " // str(self%value)
            else
                text = "property  " // self%name // " = None"
            end if
        case default
            text = self%kind
        end select
    end function

    ! ============================================================ the screen
    function screen_new(row_n, column_n, stat, error) result(self)
        ! RETURN: an open Screen of 'row_n' rows and 'column_n' columns (24,
        !         80 where absent), blank; LibraryMissing where the library is
        !         not found (see the head).
        integer, intent(in), optional           :: row_n, column_n
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        type(Screen)                            :: self
        type(c_error_t)                         :: e
        if( present(stat) ) stat = 0
        self%row_n    = 24
        self%column_n = 80
        if( present(row_n) )    self%row_n    = row_n
        if( present(column_n) ) self%column_n = column_n
        self%handle = VtermScreen_new(int(self%row_n, c_int), int(self%column_n, c_int), e)
        if( .not. c_associated(self%handle) ) call fail(e, stat, error)
    end function

    subroutine screen_close(self)
        ! RETURN: nothing; the screen is closed and its C object given back --
        !         a second call does nothing.
        class(Screen), intent(inout) :: self
        if( c_associated(self%handle) ) call VtermScreen_free(self%handle)
        self%handle = c_null_ptr
    end subroutine

    integer function screen_feed(self, data) result(taken_n)
        ! RETURN: the number of bytes the terminal took -- all of them, where
        !         it works as documented. 'data' is what a program wrote, its
        !         bytes as they stand (UTF-8 for a text).
        class(Screen), intent(inout) :: self
        character(*), intent(in)     :: data
        taken_n = int(VtermScreen_feed(self%handle, data, len(data, kind = c_size_t)))
    end function

    function screen_cursor(self) result(at)
        ! RETURN: the cursor's place (row, column), counted from 0 --
        !         Python's tuple.
        class(Screen), intent(in) :: self
        integer                   :: at(2)
        integer(c_int)            :: row, column
        call VtermScreen_cursor(self%handle, row, column)
        at = [int(row), int(column)]
    end function

    function screen_cell(self, row, column, stat, error) result(c)
        ! RETURN: what stands at (row, column) -- its text, width,
        !         attributes and colours; IndexError where the place is not
        !         on the screen (see the head).
        class(Screen), intent(inout)            :: self
        integer, intent(in)                     :: row, column
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        type(Cell)                              :: c
        type(c_cell_t)                          :: raw
        if( present(stat) ) stat = 0
        c%text = ""
        if( VtermScreen_cell(self%handle, int(row, c_int), int(column, c_int), raw) /= 0 ) then
            call fail_here(self, stat, error)
            return
        end if
        c%text         = from_c(raw%text)
        c%width        = raw%width
        c%bold_f       = raw%bold_f /= 0;      c%italic_f  = raw%italic_f /= 0
        c%underline_f  = raw%underline_f /= 0; c%blink_f   = raw%blink_f /= 0
        c%reverse_f    = raw%reverse_f /= 0;   c%conceal_f = raw%conceal_f /= 0
        c%strike_f     = raw%strike_f /= 0
        c%foreground_f = raw%foreground_f /= 0
        c%background_f = raw%background_f /= 0
        c%foreground   = iand(int(raw%foreground), 255)          ! unsigned char
        c%background   = iand(int(raw%background), 255)
    end function

    function screen_line(self, row) result(text)
        ! RETURN: the characters of row 'row', blanks at its end dropped; an
        !         unwritten cell reads a blank.
        class(Screen), intent(in)           :: self
        integer, intent(in)                 :: row
        character(:), allocatable           :: text
        character(kind=c_char), allocatable :: buffer(:)
        type(c_ptr)                         :: ignored
        allocate(buffer(4096))
        ignored = VtermScreen_line(self%handle, int(row, c_int), buffer, size(buffer, kind = c_size_t))
        text = from_c(buffer)
    end function

    function screen_line_list(self) result(list)
        ! RETURN: every row's 'line', from the top.
        class(Screen), intent(in) :: self
        type(string), allocatable :: list(:)
        integer                   :: row
        allocate(list(self%row_n))
        do row = 0, self%row_n - 1
            list(row + 1)%s = self%line(row)
        end do
    end function

    ! ========================================================== the terminal
    function terminal_new(row_n, column_n, settle_s, stat, error) result(self)
        ! RETURN: an open Terminal of 'row_n' rows and 'column_n' columns (24,
        !         80 where absent), nothing running in it yet; 'settle_s' the
        !         pause after which a screen counts as quiet (0.1 where
        !         absent); LibraryMissing where the library is not found.
        integer, intent(in), optional           :: row_n, column_n
        real(c_double), intent(in), optional    :: settle_s
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        type(Terminal)                          :: self
        type(c_error_t)                         :: e
        real(c_double)                          :: settle
        if( present(stat) ) stat = 0
        self%row_n    = 24
        self%column_n = 80
        settle        = 0.1_c_double
        if( present(row_n) )    self%row_n    = row_n
        if( present(column_n) ) self%column_n = column_n
        if( present(settle_s) ) settle        = settle_s
        self%handle = VtermTerminal_new(int(self%row_n, c_int), int(self%column_n, c_int), settle, e)
        if( .not. c_associated(self%handle) ) call fail(e, stat, error)
    end function

    subroutine terminal_close(self)
        ! RETURN: nothing; an application still running was ended, the
        !         terminal closed and given back -- a second call does
        !         nothing.
        class(Terminal), intent(inout) :: self
        if( c_associated(self%handle) ) call VtermTerminal_free(self%handle)
        self%handle = c_null_ptr
    end subroutine

    integer function terminal_feed(self, data) result(taken_n)
        ! RETURN: the number of bytes the terminal took; the raw events of
        !         what was fed fired before this returns, what the terminal
        !         answered went to the application, where one runs.
        class(Terminal), intent(inout) :: self
        character(*), intent(in)     :: data
        taken_n = int(VtermTerminal_feed(self%handle, data, len(data, kind = c_size_t)))
    end function

    integer function new_slot()
        ! RETURN: the position of an unused slot of the callback table.
        if( slot_n == SLOT_MAX ) error stop "hwut_vterm: more than 64 callbacks"
        slot_n   = slot_n + 1
        new_slot = slot_n
    end function

    subroutine terminal_on_event(self, callback)
        ! RETURN: nothing; 'callback(event)' is called with every raw event
        !         from now on -- the RAW layer.
        class(Terminal), intent(inout) :: self
        procedure(event_callback)      :: callback
        integer                        :: k
        k = new_slot()
        slot(k)%event_f => callback
        call VtermTerminal_on_event(self%handle, c_funloc(event_trampoline), c_loc(slot(k)))
    end subroutine

    subroutine terminal_on_change(self, callback)
        ! RETURN: nothing; 'callback(name, line_list)' is called for every
        !         region whose text changed, once the screen is quiet.
        class(Terminal), intent(inout) :: self
        procedure(change_callback)     :: callback
        integer                        :: k
        k = new_slot()
        slot(k)%change_f => callback
        call VtermTerminal_on_change(self%handle, c_funloc(change_trampoline), c_loc(slot(k)))
    end subroutine

    subroutine event_trampoline(context, event) bind(c)
        ! RETURN: nothing; the Fortran callback of the slot 'context' was
        !         told the C event 'event'.
        type(c_ptr), value          :: context
        type(c_event_t), intent(in) :: event
        type(slot_t), pointer       :: s
        type(VtermEvent)            :: e
        call c_f_pointer(context, s)
        e%kind       = c_string(event%kind)
        e%name       = c_string(event%name)
        e%row        = event%row
        e%column     = event%column
        e%row_end    = event%row_end
        e%column_end = event%column_end
        e%value_f    = event%value_f /= 0
        e%value      = event%value
        call s%event_f(e)
    end subroutine

    subroutine change_trampoline(context, name, line_list, line_n) bind(c)
        ! RETURN: nothing; the Fortran callback of the slot 'context' was
        !         told that region 'name' now reads the 'line_n' lines.
        type(c_ptr), value       :: context, name, line_list
        integer(c_size_t), value :: line_n
        type(slot_t), pointer    :: s
        type(c_ptr), pointer     :: line(:)
        type(string)             :: list(line_n)
        integer                  :: i
        call c_f_pointer(context, s)
        call c_f_pointer(line_list, line, [line_n])
        do i = 1, int(line_n)
            list(i)%s = c_string(line(i))
        end do
        call s%change_f(c_string(name), list)
    end subroutine

    subroutine terminal_region(self, name, row, row_n, column, column_n)
        ! RETURN: nothing; the rectangle 'name' is observed from now on:
        !         'row_n' rows (1 where absent) from 'row' -- a NEGATIVE row
        !         counts from the bottom, -1 the last -- 'column_n' columns
        !         from 'column' (0), to the right edge where absent. What
        !         stands there now is known, not news.
        class(Terminal), intent(inout) :: self
        character(*), intent(in)       :: name
        integer, intent(in)            :: row
        integer, intent(in), optional  :: row_n, column, column_n
        integer(c_int)                 :: n, c, cn
        n = 1; c = 0; cn = -1
        if( present(row_n) )    n  = row_n
        if( present(column) )   c  = column
        if( present(column_n) ) cn = column_n
        call VtermTerminal_region(self%handle, c_text(name), int(row, c_int), n, c, cn)
    end subroutine

    function terminal_region_text(self, name, stat, error) result(list)
        ! RETURN: the region's rows as they stand now, blanks at each row's
        !         end dropped; KeyError where no such region was declared.
        class(Terminal), intent(inout)          :: self
        character(*), intent(in)                :: name
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        type(string), allocatable               :: list(:)
        type(c_ptr)                             :: raw
        type(c_ptr), pointer                    :: line(:)
        integer(c_size_t)                       :: line_n
        integer                                 :: i
        if( present(stat) ) stat = 0
        allocate(list(0))
        raw = VtermTerminal_region_text(self%handle, c_text(name), line_n)
        if( .not. c_associated(raw) ) then
            call fail_here(self, stat, error)
            return
        end if
        call c_f_pointer(raw, line, [line_n])
        deallocate(list)
        allocate(list(line_n))
        do i = 1, int(line_n)
            list(i)%s = c_string(line(i))
        end do
        call VtermTerminal_lines_free(raw, line_n)
    end function

    integer function terminal_report(self) result(changed_n)
        ! RETURN: the number of regions whose text differs from what was last
        !         told -- each told to every 'on_change' callback, in the
        !         order of declaration.
        class(Terminal), intent(inout) :: self
        changed_n = int(VtermTerminal_report(self%handle))
    end function

    function terminal_answer(self) result(data)
        ! RETURN: the bytes the terminal said since the last call that no
        !         application took.
        class(Terminal), intent(inout) :: self
        character(:), allocatable      :: data
        type(c_ptr)                    :: raw
        integer(c_size_t)              :: length
        raw  = VtermTerminal_answer(self%handle, length)
        data = c_string(raw, length)
        call c_free(raw)
    end function

    logical function terminal_send(self, text, react_s) result(running_f)
        ! RETURN: .true., the application still runs after 'text' (UTF-8)
        !         was typed character by character, as a keyboard sends it,
        !         and the screen read until quiet ('react_s', 1.0 where
        !         absent, to begin answering); .false., it does not.
        class(Terminal), intent(inout)       :: self
        character(*), intent(in)             :: text
        real(c_double), intent(in), optional :: react_s
        real(c_double)                       :: react
        react = 1.0_c_double
        if( present(react_s) ) react = react_s
        running_f = VtermTerminal_send(self%handle, c_text(text), react) == 1
    end function

    logical function terminal_press(self, key, modifier, react_s, stat, error) result(running_f)
        ! RETURN: .true., the application still runs after 'key' was pressed
        !         -- 'enter', 'up', 'f5', ... or one character -- with the
        !         'modifier's ('shift', 'alt', 'ctrl', blank separated) held;
        !         .false., it does not; KeyError where a name is unknown.
        class(Terminal), intent(inout)          :: self
        character(*), intent(in)                :: key
        character(*), intent(in), optional      :: modifier
        real(c_double), intent(in), optional    :: react_s
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        character(kind=c_char), allocatable, target :: held(:)
        type(c_ptr)                             :: modifier_c
        real(c_double)                          :: react
        integer(c_int)                          :: result
        integer                                 :: i
        if( present(stat) ) stat = 0
        react = 1.0_c_double
        if( present(react_s) ) react = react_s
        modifier_c = c_null_ptr
        if( present(modifier) ) then
            allocate(held(len(modifier) + 1))
            do i = 1, len(modifier)
                held(i) = modifier(i:i)
            end do
            held(len(modifier) + 1) = c_null_char
            modifier_c = c_loc(held)
        end if
        result    = VtermTerminal_press(self%handle, c_text(key), modifier_c, react)
        running_f = result == 1
        if( result < 0 ) call fail_here(self, stat, error)
    end function

    logical function terminal_run(self, argv, start_s, stat, error) result(running_f)
        ! RETURN: .true., the application 'argv' still runs once its first
        !         screen stands ('start_s', 10.0 where absent, at most);
        !         .false., it does not; RuntimeError where one was already
        !         run here. It runs on a pseudo-terminal of this terminal's
        !         size: its three streams are that terminal, which is its
        !         controlling one, and TERM says what it is.
        class(Terminal), intent(inout)          :: self
        type(string), intent(in)                :: argv(:)
        real(c_double), intent(in), optional    :: start_s
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        character(kind=c_char), allocatable, target :: buffer(:)
        type(c_ptr), allocatable                :: pointer_list(:)
        real(c_double)                          :: start
        integer(c_int)                          :: result
        integer                                 :: i, k, n
        if( present(stat) ) stat = 0
        start = 10.0_c_double
        if( present(start_s) ) start = start_s
        n = 0
        do i = 1, size(argv)
            n = n + len(argv(i)%s) + 1
        end do
        allocate(buffer(max(n, 1)), pointer_list(size(argv) + 1))
        k = 1
        do i = 1, size(argv)
            pointer_list(i) = c_loc(buffer(k))
            buffer(k:k + len(argv(i)%s) - 1) = transfer(argv(i)%s, buffer(1:0), len(argv(i)%s))
            buffer(k + len(argv(i)%s)) = c_null_char
            k = k + len(argv(i)%s) + 1
        end do
        pointer_list(size(argv) + 1) = c_null_ptr
        result    = VtermTerminal_run(self%handle, pointer_list, c_null_ptr, start)
        running_f = result == 1
        if( result < 0 ) call fail_here(self, stat, error)
    end function

    logical function terminal_pump(self, first_s) result(running_f)
        ! RETURN: .true., the application still runs after the screen was
        !         read until quiet ('first_s', 1.0 where absent, for the
        !         first bytes); .false., it ended.
        class(Terminal), intent(inout)       :: self
        real(c_double), intent(in), optional :: first_s
        real(c_double)                       :: first
        first = 1.0_c_double
        if( present(first_s) ) first = first_s
        running_f = VtermTerminal_pump(self%handle, first) == 1
    end function

    function terminal_expect(self, text, timeout_s, stat, error) result(at)
        ! RETURN: the place (row, column) where 'text' stands on the screen,
        !         once it does -- the column counted in characters;
        !         TimeoutError, carrying the screen, where it did not appear
        !         within 'timeout_s' (10.0 where absent).
        class(Terminal), intent(inout)          :: self
        character(*), intent(in)                :: text
        real(c_double), intent(in), optional    :: timeout_s
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        integer                                 :: at(2)
        real(c_double)                          :: timeout
        integer(c_int)                          :: row, column
        if( present(stat) ) stat = 0
        timeout = 10.0_c_double
        if( present(timeout_s) ) timeout = timeout_s
        row = -1; column = -1
        if( VtermTerminal_expect(self%handle, c_text(text), timeout, row, column) /= 0 ) &
            call fail_here(self, stat, error)
        at = [int(row), int(column)]
    end function

    integer function terminal_wait(self, timeout_s, stat, error) result(status)
        ! RETURN: the application's exit status (negative: the signal that
        !         ended it), once it ended and its last words are on the
        !         screen; 0 where none was run; TimeoutError where it still
        !         ran after 'timeout_s' (10.0 where absent) and was killed.
        class(Terminal), intent(inout)          :: self
        real(c_double), intent(in), optional    :: timeout_s
        integer, intent(out), optional          :: stat
        type(VtermError), intent(out), optional :: error
        real(c_double)                          :: timeout
        integer(c_int)                          :: result, code
        if( present(stat) ) stat = 0
        timeout = 10.0_c_double
        if( present(timeout_s) ) timeout = timeout_s
        code   = 0
        result = VtermTerminal_wait(self%handle, timeout, code)
        status = int(code)
        if( result < 0 ) call fail_here(self, stat, error)
    end function

end module hwut_vterm
