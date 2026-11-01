! SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
! _____________________________________________________________________________
!
! PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
!          'python/space_iterator.py': the cartesian product, the RIGHTMOST
!          dimension changing fastest. Fortran thinks in ARRAYS, so the
!          product is not walked but WRITTEN DOWN: one column per point, one
!          row per dimension, each entry a position (1 ..) into that
!          dimension's own values:
!
!     use space_iterator
!     integer, parameter   :: x(3) = [0, 2, 4]
!     type(string)         :: name(2)  ! "otto", "heinz"
!     integer, allocatable :: point(:, :)
!     point = product_points([size(x), size(name)])   -- shape (2, 6)
!     do p = 1, size(point, 2)
!         call run_test(x(point(1, p)), name(point(2, p))%s)
!     end do
!
! The p-th point is arithmetic, not a walk: position i of point p is
! 'mod((p - 1) / stride(i), extent(i)) + 1', 'stride(i)' the product of
! the extents right of i -- 'space_point' gives one point alone, for a space
! too large to write down.
!
! THE TWO EDGES FALL OUT OF THE ARITHMETIC: the number of points is
! 'product(extent)', and Fortran's 'product' of no factors is 1 -- an empty
! basis yields ONE point, the empty one (a column of no rows) -- and of a
! factor 0 is 0: a basis with an empty dimension yields nothing. Python's
! 'do' had to say both as special cases.
! _____________________________________________________________________________
module space_iterator
    implicit none
    private

    public :: product_points, space_point, point_n

contains

    pure integer function point_n(extent)
        ! RETURN: the number of points of the basis whose dimensions hold
        !         'extent' values each -- 1 for no dimension, 0 where one is
        !         empty.
        integer, intent(in) :: extent(:)
        point_n = product(extent)
    end function

    pure function space_point(extent, p) result(at)
        ! RETURN: the p-th point (1 <= p <= point_n(extent)) of the basis whose
        !         dimensions hold 'extent' values each: one position per
        !         dimension, 1 .. extent(i), the rightmost changing fastest.
        integer, intent(in) :: extent(:), p
        integer             :: at(lbound(extent, 1):ubound(extent, 1))
        integer             :: i
        do i = lbound(extent, 1), ubound(extent, 1)
            at(i) = mod((p - 1) / product(extent(i + 1:)), extent(i)) + 1
        end do
    end function

    pure function product_points(extent) result(point)
        ! RETURN: every point of the basis whose dimensions hold 'extent'
        !         values each, in order, as the columns of a matrix of shape
        !         (size(extent), point_n(extent)) -- see 'space_point'.
        integer, intent(in)  :: extent(:)
        integer, allocatable :: point(:, :)
        integer              :: p
        allocate(point(1:ubound(extent, 1), point_n(extent)))
        do concurrent( p = 1:point_n(extent) )
            point(:, p) = space_point(extent, p)
        end do
    end function

end module space_iterator
