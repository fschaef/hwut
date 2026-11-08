! @hwut {
!     title     = "Demo: a terminal program's screen, as a person sees it"
!     build     { framework = "make", target = "%.exe" }
!     tolerance { regions    = false
!                 comment    = false
!                 whitespace = false }
!     choices {
!         open   { features = ["terminal-screen", "screen-as-seen"] }
!         scroll { features = ["terminal-screen", "screen-as-seen"] }
!     }
! }
!
! _____________________________________________________________________________
! SUBJECT  the screen of 'viewer.exe' ('viewer.f90'), a full-screen file
!          viewer, run in a terminal of 9 rows and 40 columns and driven by
!          its keys.
! REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
!              as they fit, and a status line -- the keys flush left, the
!              lines shown flush right; 'j' and the down key go one line
!              further, 'k' one back.
!
! The port's 'hwut_vterm' 'Terminal' runs the viewer on a pseudo-terminal:
! the viewer cannot tell it from a real one. The test PRESSES KEYS and is told
! what CHANGED: three regions are declared -- title, body, status -- and after
! every key, once the viewer has gone quiet, each region whose text changed is
! printed (the callback 'show', a module procedure). A redraw that changes
! nothing is not told: the title is told once.
!
! THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched off,
! in the header:
!
!     regions = false     the file shown is a GOOD file of hwut, with a
!                         '##! potpourri' ... '####' block: characters here.
!     comment = false     '## ...' lines are characters too, not notes.
!     whitespace = false  the status line's two halves stand flush left and
!                         flush right: every blank between them counts.
!
! libvterm must be installed ('apt install libvterm0'); where it is not, the
! test prints why and probes nothing -- its output differs from GOOD and the
! reason stands in the difference.
!
! CHOICES  open    the viewer opened, then quit.
!          scroll  down, down, 'j', then 'k': three lines on, one back.
! _____________________________________________________________________________
module screen_said
    use, intrinsic :: iso_c_binding, only: c_int, c_char
    use hwut_text
    use hwut_posix, only: c_text
    use hwut_vterm
    implicit none
    private
    public :: view

    interface
        integer(c_int) function c_mkdir(path, mode) bind(c, name="mkdir")
            import :: c_int, c_char
            character(kind=c_char), intent(in) :: path(*)
            integer(c_int), value              :: mode
        end function
    end interface

contains

    subroutine show(name, line_list)
        ! RETURN: nothing; one region that changed was printed, its rows as
        !         they stand on the screen, from the first column.
        character(*), intent(in) :: name
        type(string), intent(in) :: line_list(:)
        integer                  :: i
        call say("-- " // name)
        do i = 1, size(line_list)
            call say(line_list(i)%s)
        end do
    end subroutine

    function here() result(directory)
        ! RETURN: the directory this program stands in, with a '/' at its
        !         end; '' where it was called without one.
        character(:), allocatable :: directory
        character(4096)           :: path
        call get_command_argument(0, path)
        directory = path(1:index(path, "/", back = .true.))
    end function

    subroutine view(key_list)
        ! RETURN: nothing; the viewer ran on the sample, 'key_list' was
        !         pressed, the viewer quit, and what changed after each step
        !         was printed. Stops with 1 where libvterm is missing.
        type(string), intent(in)  :: key_list(:)
        type(Terminal)            :: t
        type(VtermError)          :: error
        type(Cell)                :: c
        type(string), allocatable :: argv(:)
        character(:), allocatable :: path, attributes
        integer                   :: unit, stat, i
        logical                   :: running
        i = c_mkdir(c_text(here() // "TMP"), int(o'755', c_int))
        path = here() // "TMP/race.txt"
        open(newunit = unit, file = path, status = "replace", action = "write")
        write(unit, '(a)') "## demo.py race -- three workers"
        write(unit, '(a)') "start"
        write(unit, '(a)') "##! potpourri"
        write(unit, '(a)') "worker B done: 5 jobs"
        write(unit, '(a)') "worker A done: 3 jobs"
        write(unit, '(a)') "worker C done: 2 jobs"
        write(unit, '(a)') "####"
        write(unit, '(a)') "all joined"
        write(unit, '(a)') "## the order between the markers is"
        write(unit, '(a)') "## free; the lines are not."
        close(unit)
        t = Terminal(9, 40, stat = stat, error = error)
        if( stat /= 0 ) then
            call say(error%message)
            stop 1, quiet = .true.
        end if
        call t%region("title",  row = 0)
        call t%region("body",   row = 1, row_n = 7)
        call t%region("status", row = -1)
        call t%on_change(show)
        call say("> viewer.exe race.txt")
        allocate(argv(0))
        call push(argv, here() // "viewer.exe")
        call push(argv, path)
        running = t%run(argv)
        c = t%cell(0, 1)
        attributes = c%attribute_text()
        if( len(attributes) == 0 ) attributes = "plain"
        call say("title bar: " // attributes)
        do i = 1, size(key_list)
            call say("> " // key_list(i)%s)
            if( len(key_list(i)%s) == 1 ) then
                running = t%send(key_list(i)%s)
            else
                running = t%press(key_list(i)%s)
            end if
        end do
        running = t%send("q")
        call say("> q -- exit status " // str(t%wait()))
        call t%close()
    end subroutine

end module screen_said

program screen
    use screen_said
    use hwut_text
    implicit none
    type(string), allocatable :: key_list(:)
    character(16)             :: choice

    call get_command_argument(1, choice)
    allocate(key_list(0))
    select case( trim(choice) )
    case( "open" )
    case( "scroll" )
        call push(key_list, "down"); call push(key_list, "down")
        call push(key_list, "j");    call push(key_list, "k")
    case default
        call say("choices: open, scroll")
        stop 1, quiet = .true.
    end select
    call view(key_list)
    call say("<hwut-end>")
end program screen
