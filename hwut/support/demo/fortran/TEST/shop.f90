! @hwut {
!     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
!     build     { framework = "make", target = "%.exe" }
!     tolerance { stderr_ignored = true }
!     choices {
!         sell   { features = ["demo-fortran+cover-unordered-table", "demo-fortran+cover-stderr-ignored", "demo-fortran+cover-collision"] }
!         report { features = ["demo-fortran+cover-output-file", "demo-fortran+cover-keyed-table-separator", "demo-fortran+cover-dependency",
!                              "demo-fortran+cover-frame-scripts", "demo-fortran+cover-test-scripts", "demo-fortran+cover-stderr-ignored"]
!                  output   = ["<stdout>", "stock.csv"] }
!     }
! }
!
! _____________________________________________________________________________
! SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
!          comes in, three clerks sell at once, and the stock is reported.
! REQUIREMENT  Every movement of the stock is journalled, so that the stock
!              always ADDS UP: opening quantity plus the journal's movements.
!
! THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
! this file, read it first. hwut, when it enters this directory:
!
!     on_entry        'make ... && ./fixture.exe open': the helpers built, a
!                     fresh 'TMP/shop.db', stocked
!     on_before_test  './fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
!     on_after_test   './fixture.exe check after ...': around every test run,
!                     whether the stock adds up, into 'TMP/frame.log'
!     on_exit         './fixture.exe close'
!     apps            'delivery.json' is a test, though it carries no header:
!                     'admit' takes it out of the files hwut ignores by
!                     default ('*.json'); 'execute' says how it is run --
!                     'shop.exe deliver delivery.json'.
!     collision       'delivery.json' and 'shop.f90 sell' both write the
!                     database; hwut never runs the two at once.
!     dependency      'shop.f90 report' runs after both, whatever their
!                     verdict: it reports what they left.
!
! STDERR  Every SQL statement is logged on stderr, as a server would; the
! header says 'stderr_ignored = true': the words there are on purpose.
!
! CHOICES
!
! sell     three clerks sell at once, each an OpenMP thread with a connection
!          of its own. The sales are printed as '##! table unordered sep={;}':
!          rows of 'item;qty', in any order -- 'apple;1' stands four times.
! report   the stock, as '##! table key=0 sep={;}', and the same rows written
!          to 'stock.csv' ('output' names it; its GOOD is the Python
!          demonstration's, by '.link'). Then the frame log: what
!          'on_before_test' and 'on_after_test' found around the delivery and
!          the sale ('##! potpourri'), and before this report.
! deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
!          delivery note: every line on the stock and into the journal, in
!          one transaction. Fortran reads no JSON: the note is scanned here,
!          as far as a delivery note goes.
! _____________________________________________________________________________
module shop_cases
    use, intrinsic :: iso_c_binding, only: c_ptr
    use, intrinsic :: iso_fortran_env, only: error_unit
    use shop_db
    use hwut_text
    implicit none
    private
    public :: deliver, sell, report

contains

    function here() result(directory)
        ! RETURN: the directory this program stands in, with a '/' at its
        !         end; '' where it was called without one.
        character(:), allocatable :: directory
        character(4096)           :: path
        call get_command_argument(0, path)
        directory = path(1:index(path, "/", back = .true.))
    end function

    function connect() result(db)
        ! RETURN: the connection to the shop's database, every statement it
        !         executes logged on stderr. Exits 1 where the database does
        !         not stand: 'on_entry' writes it.
        type(c_ptr) :: db
        if( .not. exists_f(here() // "TMP/shop.db") ) then
            write(error_unit, '(a)') "shop.f90: no " // here() // "TMP/shop.db -- 'on_entry' writes it; " &
                                     // "by hand: 'hwut.execute fixture open'"
            stop 1, quiet = .true.
        end if
        db = connected(here() // "TMP/shop.db", trace_f = .true.)
    end function

    integer function moved(db, item, delta, source) result(code)
        ! RETURN: SQLITE_DONE, the stock of 'item' changed by 'delta' and the
        !         change journalled, in one transaction; SQLite's fault code,
        !         else (the transaction rolled back).
        type(c_ptr), intent(in)  :: db
        character(*), intent(in) :: item, source
        integer, intent(in)      :: delta
        type(Statement)          :: s
        s = prepared(db, "BEGIN IMMEDIATE")
        code = s%step(); call s%finalize()
        if( code /= SQLITE_DONE ) return
        s = prepared(db, "UPDATE stock SET qty = qty + ? WHERE item = ?")
        call s%bind_int(1, delta); call s%bind_text(2, item)
        code = s%step(); call s%finalize()
        if( code == SQLITE_DONE ) then
            s = prepared(db, "INSERT INTO journal VALUES (?, ?, ?)")
            call s%bind_text(1, item); call s%bind_int(2, delta); call s%bind_text(3, source)
            code = s%step(); call s%finalize()
        end if
        if( code /= SQLITE_DONE ) then
            call execute(db, "ROLLBACK")
            return
        end if
        s = prepared(db, "COMMIT")
        code = s%step(); call s%finalize()
    end function

    ! _________________________________________________________________________
    ! deliver -- the delivery note
    !
    subroutine tokens_of(text, token)
        ! RETURN: nothing; 'token' holds the JSON tokens of 'text' in order:
        !         a string without its quotes (no escapes: a delivery note
        !         has none), a number, or one of '{}[]:,'.
        character(*), intent(in)               :: text
        type(string), allocatable, intent(out) :: token(:)
        integer                                :: i, j
        allocate(token(0))
        i = 1
        do while( i <= len(text) )
            select case( text(i:i) )
            case( '"' )
                j = index(text(i + 1:), '"') + i
                call push(token, text(i + 1:j - 1))
                i = j + 1
            case( "{", "}", "[", "]", ":", "," )
                call push(token, text(i:i))
                i = i + 1
            case( "-", "0":"9" )
                j = i
                do while( j < len(text) )
                    if( verify(text(j + 1:j + 1), "0123456789") /= 0 ) exit
                    j = j + 1
                end do
                call push(token, text(i:j))
                i = j + 1
            case default
                i = i + 1
            end select
        end do
    end subroutine

    subroutine deliver(path)
        ! RETURN: nothing; the delivery note in 'path' is booked and printed.
        character(*), intent(in)  :: path
        type(string), allocatable :: token(:), item(:)
        integer, allocatable      :: qty(:)
        character(:), allocatable :: note, supplier, text
        character(4096)           :: buffer
        type(c_ptr)               :: db
        type(Statement)           :: s
        integer                   :: unit, status, i, code, value
        text = ""
        open(newunit = unit, file = path, status = "old", action = "read")
        do
            read(unit, '(a)', iostat = status) buffer
            if( status /= 0 ) exit
            text = text // trim(buffer) // NL
        end do
        close(unit)
        call tokens_of(text, token)
        allocate(item(0), qty(0))
        do i = 1, size(token) - 2
            if( token(i + 1)%s /= ":" ) cycle
            select case( token(i)%s )
            case( "note" );     note     = token(i + 2)%s
            case( "supplier" ); supplier = token(i + 2)%s
            case( "item" );     call push(item, token(i + 2)%s)
            case( "qty" )
                read(token(i + 2)%s, *) value
                qty = [qty, value]
            end select
        end do
        db = connect()
        call execute(db, "BEGIN IMMEDIATE")
        do i = 1, size(item)
            s = prepared(db, "UPDATE stock SET qty = qty + ? WHERE item = ?")
            call s%bind_int(1, qty(i)); call s%bind_text(2, item(i)%s)
            code = s%step(); call s%finalize()
            s = prepared(db, "INSERT INTO journal VALUES (?, ?, ?)")
            call s%bind_text(1, item(i)%s); call s%bind_int(2, qty(i)); call s%bind_text(3, note)
            code = s%step(); call s%finalize()
        end do
        call execute(db, "COMMIT")
        call disconnect(db)
        call say("delivery note " // note // " from " // supplier // ":")
        do i = 1, size(item)
            call say("    " // item(i)%s // repeat(" ", max(0, 6 - len(item(i)%s))) // " +" // str(qty(i)))
        end do
    end subroutine

    ! _________________________________________________________________________
    ! sell -- three clerks at once
    !
    subroutine sell()
        ! RETURN: nothing; three clerks sold at once; every sale is printed.
        character(5), parameter :: CLERK(3)    = ["anna ", "ben  ", "chloe"]
        character(5), parameter :: GOODS(3, 3) = reshape(["apple", "apple", "pear ", &
                                                          "apple", "plum ", "     ", &
                                                          "apple", "     ", "     "], [3, 3])
        type(string)              :: sale(6), error_list(3)
        type(c_ptr)               :: db
        integer                   :: sale_n, error_n, k, j, code
        db = connect()
        call disconnect(db)
        sale_n = 0
        error_n = 0
        !$omp parallel do num_threads(3) private(db, j, code) schedule(static, 1)
        do k = 1, 3
            db = connected(here() // "TMP/shop.db", trace_f = .true.)
            do j = 1, 3
                if( GOODS(j, k) == "" ) exit
                code = moved(db, trim(GOODS(j, k)), -1, trim(CLERK(k)))
                !$omp critical (sales)
                if( code == SQLITE_DONE ) then
                    sale_n = sale_n + 1
                    sale(sale_n)%s = trim(GOODS(j, k)) // ";1"
                else if( error_n < 3 ) then
                    error_n = error_n + 1
                    error_list(error_n)%s = trim(CLERK(k)) // ": " // error_text(db)
                end if
                !$omp end critical (sales)
                if( code /= SQLITE_DONE ) exit
            end do
            call disconnect(db)
        end do
        !$omp end parallel do
        if( error_n > 0 ) then
            write(error_unit, '(a)') "shop.f90: a sale failed -- " // join(error_list(1:error_n), "; ")
            stop 1, quiet = .true.
        end if
        call say("sales, item;qty -- in the order the clerks booked them:")
        call say("##! table unordered sep={;}")
        do k = 1, sale_n
            call say(sale(k)%s)
        end do
        call say("####")
    end subroutine

    ! _________________________________________________________________________
    ! report -- the stock and the frame
    !
    subroutine report()
        ! RETURN: nothing; prints the stock and the frame log; writes
        !         'stock.csv'.
        type(string), allocatable :: item(:), line_list(:), sorted(:)
        integer, allocatable      :: qty(:)
        character(4096)           :: buffer
        type(c_ptr)               :: db
        type(Statement)           :: s
        integer                   :: unit, status, i, k
        db = connect()
        allocate(item(0), qty(0))
        s = prepared(db, "SELECT item, qty FROM stock ORDER BY qty, item")
        do while( s%step() == SQLITE_ROW )
            call push(item, s%column_text(0))
            qty = [qty, s%column_int(1)]
        end do
        call s%finalize()
        call disconnect(db)
        sorted = item
        call sort_strings(sorted)
        open(newunit = unit, file = here() // "stock.csv", status = "replace", action = "write")
        write(unit, '(a)') "item;qty"
        do k = 1, size(sorted)
            i = text_index(item, sorted(k)%s)
            write(unit, '(a)') item(i)%s // ";" // str(qty(i))
        end do
        close(unit)
        call say("stock, item;qty (also written to stock.csv):")
        call say("##! table key=0 sep={;}")
        do i = 1, size(item)
            call say(item(i)%s // ";" // str(qty(i)))
        end do
        call say("####")
        allocate(line_list(0))
        open(newunit = unit, file = here() // "TMP/frame.log", status = "old", action = "read")
        do
            read(unit, '(a)', iostat = status) buffer
            if( status /= 0 ) exit
            call push(line_list, trim(buffer))
        end do
        close(unit)
        call say("the frame, around the delivery and the sale:")
        call say("##! potpourri")
        do i = 1, size(line_list)
            if( index(line_list(i)%s, "shop.f90 report") == 0 ) call say(line_list(i)%s)
        end do
        call say("####")
        do i = 1, size(line_list)
            if( index(line_list(i)%s, "shop.f90 report") /= 0 ) call say(line_list(i)%s)
        end do
    end subroutine

end module shop_cases

program shop
    use shop_cases
    use hwut_text, only: say
    implicit none
    character(4096) :: command, path

    call get_command_argument(1, command)
    call get_command_argument(2, path)
    select case( trim(command) )
    case( "deliver" ); call deliver(trim(path))
    case( "sell" );    call sell()
    case( "report" );  call report()
    case default
        call say("choices: sell, report")
        stop 1, quiet = .true.
    end select
    call say("<hwut-end>")
end program shop
