! _____________________________________________________________________________
! THE SHOP'S DATABASE, FOR 'shop.f90' AND 'fixture.f90' -- no test: SQLite
! through ISO_C_BINDING, the few functions of 'libsqlite3' the shop needs, as
! Python's 'sqlite3' gives them to 'shop.py'. Link: '-lsqlite3'; no header is
! needed to build.
!
!     use shop_db
!     type(c_ptr)     :: db
!     type(Statement) :: s
!     db = connected("TMP/shop.db", trace_f = .true.)  -- every statement on stderr
!     call execute(db, "BEGIN IMMEDIATE")
!     s = prepared(db, "UPDATE stock SET qty = qty + ? WHERE item = ?")
!     call s%bind_int(1, -1); call s%bind_text(2, "apple")
!     status = s%step()                                -- SQLITE_ROW, SQLITE_DONE, ...
!     call s%finalize()
!
! A STATEMENT THAT FAILS stops nothing: 'step' answers SQLite's code and
! 'error_text' its words -- the caller decides, as a Python caller catches
! 'sqlite3.Error' or does not. 'execute' stops the program with the words
! ('error stop'), the uncaught exception.
!
! THE TRACE is Python's 'set_trace_callback': each statement, its values
! bound in ('sqlite3_expanded_sql'), on stderr as 'sql: <statement>'.
! _____________________________________________________________________________
module shop_db
    use, intrinsic :: iso_c_binding
    use, intrinsic :: iso_fortran_env, only: error_unit
    use hwut_posix, only: c_text, c_string
    implicit none
    private
    public :: Statement, connected, execute, prepared, disconnect, error_text, exists_f, make_directory
    public :: SQLITE_OK, SQLITE_ROW, SQLITE_DONE

    integer(c_int), parameter :: SQLITE_OK = 0, SQLITE_ROW = 100, SQLITE_DONE = 101
    integer(c_intptr_t), parameter :: SQLITE_TRANSIENT = -1      ! '(sqlite3_destructor_type)-1'

    type :: Statement
        type(c_ptr) :: handle  = c_null_ptr
        type(c_ptr) :: db      = c_null_ptr
        logical     :: trace_f = .false.
    contains
        procedure :: bind_int  => statement_bind_int
        procedure :: bind_text => statement_bind_text
        procedure :: step      => statement_step
        procedure :: column_int  => statement_column_int
        procedure :: column_text => statement_column_text
        procedure :: finalize  => statement_finalize
    end type

    ! Whether the connection at the address traces: one connection's word,
    ! held per program (a shop opens few).
    type(c_ptr), save :: traced(16) = c_null_ptr
    integer, save     :: traced_n   = 0

    interface
        integer(c_int) function sqlite3_open(path, db) bind(c, name="sqlite3_open")
            import :: c_int, c_char, c_ptr
            character(kind=c_char), intent(in) :: path(*)
            type(c_ptr), intent(out)           :: db
        end function
        integer(c_int) function sqlite3_close(db) bind(c, name="sqlite3_close")
            import :: c_int, c_ptr
            type(c_ptr), value :: db
        end function
        integer(c_int) function sqlite3_busy_timeout(db, ms) bind(c, name="sqlite3_busy_timeout")
            import :: c_int, c_ptr
            type(c_ptr), value    :: db
            integer(c_int), value :: ms
        end function
        integer(c_int) function sqlite3_prepare_v2(db, sql, n, statement, tail) bind(c, name="sqlite3_prepare_v2")
            import :: c_int, c_char, c_ptr
            type(c_ptr), value                 :: db
            character(kind=c_char), intent(in) :: sql(*)
            integer(c_int), value              :: n
            type(c_ptr), intent(out)           :: statement
            type(c_ptr), value                 :: tail
        end function
        integer(c_int) function sqlite3_bind_int(statement, i, value) bind(c, name="sqlite3_bind_int")
            import :: c_int, c_ptr
            type(c_ptr), value    :: statement
            integer(c_int), value :: i, value
        end function
        integer(c_int) function sqlite3_bind_text(statement, i, text, n, destructor) bind(c, name="sqlite3_bind_text")
            import :: c_int, c_char, c_ptr, c_intptr_t
            type(c_ptr), value                 :: statement
            integer(c_int), value              :: i
            character(kind=c_char), intent(in) :: text(*)
            integer(c_int), value              :: n
            integer(c_intptr_t), value         :: destructor
        end function
        integer(c_int) function sqlite3_step(statement) bind(c, name="sqlite3_step")
            import :: c_int, c_ptr
            type(c_ptr), value :: statement
        end function
        integer(c_int) function sqlite3_column_int(statement, i) bind(c, name="sqlite3_column_int")
            import :: c_int, c_ptr
            type(c_ptr), value    :: statement
            integer(c_int), value :: i
        end function
        type(c_ptr) function sqlite3_column_text(statement, i) bind(c, name="sqlite3_column_text")
            import :: c_int, c_ptr
            type(c_ptr), value    :: statement
            integer(c_int), value :: i
        end function
        integer(c_int) function sqlite3_finalize(statement) bind(c, name="sqlite3_finalize")
            import :: c_int, c_ptr
            type(c_ptr), value :: statement
        end function
        type(c_ptr) function sqlite3_expanded_sql(statement) bind(c, name="sqlite3_expanded_sql")
            import :: c_ptr
            type(c_ptr), value :: statement
        end function
        subroutine sqlite3_free(pointer) bind(c, name="sqlite3_free")
            import :: c_ptr
            type(c_ptr), value :: pointer
        end subroutine
        type(c_ptr) function sqlite3_errmsg(db) bind(c, name="sqlite3_errmsg")
            import :: c_ptr
            type(c_ptr), value :: db
        end function
        integer(c_int) function c_mkdir(path, mode) bind(c, name="mkdir")
            import :: c_int, c_char
            character(kind=c_char), intent(in) :: path(*)
            integer(c_int), value              :: mode
        end function
    end interface

contains

    logical function exists_f(path)
        ! RETURN: .true., a file 'path' stands; .false., else.
        character(*), intent(in) :: path
        inquire(file = path, exist = exists_f)
    end function

    subroutine make_directory(path)
        ! RETURN: nothing; the directory 'path' stands -- made where it did
        !         not ('os.makedirs(path, exist_ok=True)', one level).
        character(*), intent(in) :: path
        integer(c_int)           :: ignored
        ignored = c_mkdir(c_text(path), int(o'755', c_int))
    end subroutine

    function connected(path, trace_f) result(db)
        ! RETURN: the connection to the database 'path', waiting up to 10 s
        !         for a lock another holds; every statement it steps logged on
        !         stderr where 'trace_f'. Stops the program where SQLite
        !         cannot open the file.
        character(*), intent(in)      :: path
        logical, intent(in), optional :: trace_f
        type(c_ptr)                   :: db
        integer(c_int)                :: code
        code = sqlite3_open(c_text(path), db)
        if( code /= SQLITE_OK ) error stop "sqlite3.OperationalError: unable to open " // path
        code = sqlite3_busy_timeout(db, 10000_c_int)
        if( present(trace_f) ) then
            if( trace_f ) then
                !$omp critical (shop_db_traced)
                traced_n = traced_n + 1
                traced(traced_n) = db
                !$omp end critical (shop_db_traced)
            end if
        end if
    end function

    subroutine disconnect(db)
        ! RETURN: nothing; the connection 'db' is closed.
        type(c_ptr), intent(in) :: db
        integer(c_int)          :: ignored
        ignored = sqlite3_close(db)
    end subroutine

    function error_text(db) result(text)
        ! RETURN: SQLite's words on the last fault of the connection 'db'.
        type(c_ptr), intent(in)   :: db
        character(:), allocatable :: text
        text = c_string(sqlite3_errmsg(db))
    end function

    function prepared(db, sql) result(self)
        ! RETURN: the statement 'sql' on the connection 'db', ready to be
        !         bound and stepped. Stops the program where 'sql' is no
        !         statement SQLite understands.
        type(c_ptr), intent(in)  :: db
        character(*), intent(in) :: sql
        type(Statement)          :: self
        integer                  :: i
        if( sqlite3_prepare_v2(db, c_text(sql), -1_c_int, self%handle, c_null_ptr) /= SQLITE_OK ) &
            error stop "sqlite3.OperationalError: " // error_text(db)
        self%db = db
        !$omp critical (shop_db_traced)
        do i = 1, traced_n
            if( c_associated(traced(i), db) ) self%trace_f = .true.
        end do
        !$omp end critical (shop_db_traced)
    end function

    subroutine execute(db, sql)
        ! RETURN: nothing; the statement 'sql', without values, was stepped
        !         to its end. Stops the program where it failed.
        type(c_ptr), intent(in)  :: db
        character(*), intent(in) :: sql
        type(Statement)          :: s
        integer(c_int)           :: code
        s = prepared(db, sql)
        code = s%step()
        call s%finalize()
        if( code /= SQLITE_DONE .and. code /= SQLITE_ROW ) &
            error stop "sqlite3.OperationalError: " // error_text(db)
    end subroutine

    subroutine statement_bind_int(self, i, value)
        ! RETURN: nothing; the 'i'-th '?' of the statement (from 1) is 'value'.
        class(Statement), intent(inout) :: self
        integer, intent(in)             :: i, value
        integer(c_int)                  :: ignored
        ignored = sqlite3_bind_int(self%handle, int(i, c_int), int(value, c_int))
    end subroutine

    subroutine statement_bind_text(self, i, text)
        ! RETURN: nothing; the 'i'-th '?' of the statement (from 1) is 'text',
        !         copied by SQLite.
        class(Statement), intent(inout) :: self
        integer, intent(in)             :: i
        character(*), intent(in)        :: text
        integer(c_int)                  :: ignored
        ignored = sqlite3_bind_text(self%handle, int(i, c_int), text, int(len(text), c_int), SQLITE_TRANSIENT)
    end subroutine

    integer function statement_step(self) result(code)
        ! RETURN: SQLITE_ROW, a row stands to be read; SQLITE_DONE, the
        !         statement ran to its end; SQLite's fault code, else. The
        !         first step of a traced statement is logged on stderr.
        class(Statement), intent(inout) :: self
        type(c_ptr)                     :: expanded
        if( self%trace_f ) then
            expanded = sqlite3_expanded_sql(self%handle)
            !$omp critical (shop_db_log)
            write(error_unit, '(a)') "sql: " // c_string(expanded)
            flush(error_unit)
            !$omp end critical (shop_db_log)
            call sqlite3_free(expanded)
            self%trace_f = .false.
        end if
        code = sqlite3_step(self%handle)
    end function

    integer function statement_column_int(self, i) result(value)
        ! RETURN: the 'i'-th column (from 0) of the row stepped to, an integer.
        class(Statement), intent(in) :: self
        integer, intent(in)          :: i
        value = sqlite3_column_int(self%handle, int(i, c_int))
    end function

    function statement_column_text(self, i) result(text)
        ! RETURN: the 'i'-th column (from 0) of the row stepped to, a text.
        class(Statement), intent(in) :: self
        integer, intent(in)          :: i
        character(:), allocatable    :: text
        text = c_string(sqlite3_column_text(self%handle, int(i, c_int)))
    end function

    subroutine statement_finalize(self)
        ! RETURN: nothing; the statement is gone.
        class(Statement), intent(inout) :: self
        integer(c_int)                  :: ignored
        ignored = sqlite3_finalize(self%handle)
        self%handle = c_null_ptr
    end subroutine

end module shop_db
