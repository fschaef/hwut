! @hwut {
!     title   = "Demo: a door's state machine, watched by a pype"
!     build   { framework = "make", executable = "%.exe" }
!     pype    = "door.pype"
!     choices {
!         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
!         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
!     }
! }
!
! _____________________________________________________________________________
! A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
! may do.
!
! The application prints its log as it happens: noise, and a line 'door:
! <event>' for each thing the door does. It prints no '<hwut-end>': the
! header names 'door.pype', which stands between it and the comparison and
! closes the stream at '<eof>'.
!
! 'door.pype' parses the log and fires every event into a state machine:
!
!     closed ---( open )---> open ---( close )---> closed
!     closed ---( lock )---> locked ---( unlock )---> closed
!     open   ---( slam )---> jammed          # forbidden
!
! The pype is the Python demonstration's, unchanged: a pype script is
! hwut.pype's language, whatever language the application is written in --
! so its machine is the Python 'hwut_fsm' (the Fortran one, 'hwut_fsm.f90',
! serves a Fortran test that holds its model itself).
!
! kept     the door does what the model allows; the report shows which
!          transitions were taken and which not, and 'ended in closed'.
! broken   the controller locks an open door, slams it into a jam and tries
!          to unlock it: each surprise is ONE 'BREACH' line, the end outside
!          the final states one more. The GOOD file holds them.
!
! Both choices pass on every run: what they print does not depend on time.
! _____________________________________________________________________________
program door
    use hwut_text
    implicit none
    character(16)             :: choice
    character(8), allocatable :: story(:)
    integer                   :: number

    call get_command_argument(1, choice)
    select case( trim(choice) )
    case( "kept" );   story = ["open  ", "close ", "lock  ", "unlock", "open  ", "close "]
    case( "broken" ); story = ["open  ", "lock  ", "slam  ", "unlock"]
    case default
        call say("error: a choice is required: broken, kept")
        stop 1, quiet = .true.
    end select

    call say("controller 2.1 up")
    do number = 1, size(story)
        call say("tick " // str(number) // ": sensors read")
        call say("door: " // trim(story(number)))
    end do
    call say("controller down")
end program door
