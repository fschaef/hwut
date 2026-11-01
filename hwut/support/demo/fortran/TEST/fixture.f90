! _____________________________________________________________________________
! THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
!
!     fixture.exe open           a fresh 'TMP/shop.db', stocked as below, and an
!                                empty 'TMP/frame.log' ('on_entry', and
!                                'hwut.execute fixture open')
!     fixture.exe close          both removed ('on_exit')
!     fixture.exe check <when> <app> [<choice>]
!                                'when' is 'before' or 'after': whether the
!                                stock adds up around the test run '<app>
!                                <choice>', appended to 'TMP/frame.log'
!                                ('on_before_test', 'on_after_test')
!
! 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
! which hwut sets for the run the check stands around; a test without choices
! has none. 'check' concerns the shop's tests alone. The stock ADDS UP where
! every item's quantity is its opening quantity plus every movement of the
! journal.
! _____________________________________________________________________________
module shop_fixture
    use shop_db
    use hwut_text
    implicit none
    private
    public :: open_shop, close_shop, check

    character(5), parameter :: OPENING_ITEM(3) = ["apple", "pear ", "plum "]
    integer, parameter      :: OPENING_QTY(3)  = [10, 5, 5]

contains

    function here() result(directory)
        ! RETURN: the directory this program stands in, with a '/' at its
        !         end; '' where it was called without one.
        character(:), allocatable :: directory
        character(4096)           :: path
        call get_command_argument(0, path)
        directory = path(1:index(path, "/", back = .true.))
    end function

    subroutine removed(path)
        ! RETURN: nothing; no file 'path' stands any more.
        character(*), intent(in) :: path
        integer                  :: unit
        if( .not. exists_f(path) ) return
        open(newunit = unit, file = path)
        close(unit, status = "delete")
    end subroutine

    subroutine open_shop()
        ! RETURN: nothing; a fresh, stocked database and an empty log stand.
        call make_directory(here() // "TMP")
        call removed(here() // "TMP/shop.db")
        call removed(here() // "TMP/frame.log")
        call stocked(here() // "TMP/shop.db")
        call empty_log(here() // "TMP/frame.log")
    end subroutine

    subroutine stocked(path)
        ! RETURN: nothing; the database 'path' holds the three tables, the
        !         opening stock in 'opening' and in 'stock', an empty journal.
        use, intrinsic :: iso_c_binding, only: c_ptr
        character(*), intent(in) :: path
        type(c_ptr)              :: db
        type(Statement)          :: s
        integer                  :: i, code
        db = connected(path)
        call execute(db, "BEGIN")
        call execute(db, "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)")
        call execute(db, "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)")
        call execute(db, "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)")
        do i = 1, size(OPENING_ITEM)
            s = prepared(db, "INSERT INTO opening VALUES (?, ?)")
            call s%bind_text(1, trim(OPENING_ITEM(i))); call s%bind_int(2, OPENING_QTY(i))
            code = s%step(); call s%finalize()
            s = prepared(db, "INSERT INTO stock   VALUES (?, ?)")
            call s%bind_text(1, trim(OPENING_ITEM(i))); call s%bind_int(2, OPENING_QTY(i))
            code = s%step(); call s%finalize()
        end do
        call execute(db, "COMMIT")
        call disconnect(db)
    end subroutine

    subroutine empty_log(path)
        ! RETURN: nothing; the file 'path' stands, empty.
        character(*), intent(in) :: path
        integer                  :: unit
        open(newunit = unit, file = path, status = "replace", action = "write")
        close(unit)
    end subroutine

    subroutine close_shop()
        ! RETURN: nothing; the database and the log are removed.
        call removed(here() // "TMP/shop.db")
        call removed(here() // "TMP/frame.log")
    end subroutine

    logical function adds_up()
        ! RETURN: .true., if every item's stock is its opening quantity plus
        !         its journal's movements; .false., else.
        use, intrinsic :: iso_c_binding, only: c_ptr
        type(c_ptr)     :: db
        type(Statement) :: s
        db = connected(here() // "TMP/shop.db")
        s = prepared(db, "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty" &
                         // "  FROM opening o JOIN stock s ON s.item = o.item" &
                         // "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item")
        adds_up = .true.
        do while( s%step() == SQLITE_ROW )
            if( s%column_int(1) /= s%column_int(2) ) adds_up = .false.
        end do
        call s%finalize()
        call disconnect(db)
    end function

    subroutine check(when, test, choice)
        ! RETURN: nothing; one line was appended to the log for a run of a
        !         shop test -- none for any other test.
        character(*), intent(in)  :: when, test, choice
        character(:), allocatable :: run
        character(6)              :: when_padded
        character(15)             :: run_padded
        integer                   :: unit
        if( test /= "delivery.json" .and. test /= "shop.f90" ) return
        run = trim(test // " " // choice)
        when_padded = when
        run_padded  = run
        open(newunit = unit, file = here() // "TMP/frame.log", position = "append", action = "write")
        write(unit, '(a)') when_padded // " " // run_padded // run(min(len(run), 15) + 1:) // " " &
                           // trim(merge("stock adds up", "STOCK BROKEN ", adds_up()))
        close(unit)
    end subroutine

end module shop_fixture

program fixture
    use, intrinsic :: iso_fortran_env, only: error_unit
    use shop_fixture
    implicit none
    character(64) :: command, when, test, choice

    call get_command_argument(1, command)
    call get_command_argument(2, when)
    call get_command_argument(3, test)
    call get_command_argument(4, choice)
    select case( trim(command) )
    case( "open" );  call open_shop()
    case( "close" ); call close_shop()
    case( "check" ); call check(trim(when), trim(test), trim(choice))
    case default
        write(error_unit, '(a)') "usage: fixture.exe open | close | check before|after <app> <choice>"
        stop 2, quiet = .true.
    end select
end program fixture
