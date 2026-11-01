! @hwut {
!     title      = "space_iterator: every combination of a parameter basis"
!     build      { framework = "make", executable = "%.exe" }
!     choices {
!         product { features = ["fortran-space"] }
!         edges   { features = ["fortran-space"] }
!     }
!     interactive = true
! }
!
! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: The Fortran port of 'python/TEST/test-space-iterator.py', held
!          against its GOOD files by '.link'. A basis is a list of
!          dimensions, each a list of the values' texts; the points are the
!          columns of 'product_points'.
! _____________________________________________________________________________
module test_space_iterator_choices
    use hwut_text
    use hwut_runner
    use space_iterator
    implicit none

    type :: dimension
        type(string), allocatable :: value(:)
    end type

contains

    subroutine banner(label)
        character(*), intent(in) :: label
        call say("")
        call say("--- " // label // " ---")
    end subroutine

    function texts(value) result(dim)
        ! RETURN: a dimension of the values 'value', blanks at their ends
        !         dropped -- a Fortran array constructor pads to one length.
        character(*), intent(in) :: value(:)
        type(dimension)          :: dim
        integer                  :: i
        allocate(dim%value(size(value)))
        do i = 1, size(value)
            dim%value(i)%s = trim(value(i))
        end do
    end function

    subroutine points(basis)
        ! RETURN: nothing; every point of 'basis' was printed, one per line,
        !         then the count.
        type(dimension), intent(in) :: basis(:)
        integer, allocatable        :: point(:, :)
        type(string), allocatable   :: shown(:)
        integer                     :: p, i
        point = product_points([(size(basis(i)%value), i = 1, size(basis))])
        allocate(shown(size(basis)))
        do p = 1, size(point, 2)
            do i = 1, size(basis)
                shown(i) = basis(i)%value(point(i, p))
            end do
            call say("  (" // join(shown, ", ") // ")")
        end do
        call say("  " // str(size(point, 2)) // " point(s)")
    end subroutine

    subroutine run_product()
        call banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points")
        call points([texts(["0", "2", "4"]), texts(["otto ", "heinz"]), texts(["1", "2"])])
    end subroutine

    subroutine run_edges()
        type(dimension) :: none(0)
        character(1)    :: empty(0)
        call banner("an EMPTY basis -- one point, the empty one")
        call points(none)
        call banner("a basis with an EMPTY dimension -- nothing")
        call points([texts(["1", "2"]), texts(empty), texts(["3"])])
        call banner("ONE dimension -- its values one by one")
        call points([texts(["a", "b", "c"])])
    end subroutine

end module test_space_iterator_choices

program test_space_iterator
    ! THE CHOICES ARE MODULE PROCEDURES: a procedure pointer to an internal
    ! one would need a trampoline, and with it an executable stack.
    use hwut_runner
    use test_space_iterator_choices
    implicit none
    type(HwutRunner) :: runner
    runner = HwutRunner("space_iterator: every combination of a parameter basis", [ &
                 HwutChoice("product", run_product), HwutChoice("edges", run_edges)])
    call runner%run()
end program test_space_iterator
