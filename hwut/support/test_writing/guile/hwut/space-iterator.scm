;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
;;;          'python/space_iterator.py'. The cartesian product of a basis,
;;;          the RIGHTMOST dimension changing fastest.
;;;
;;;     (space-for-each (lambda (x name number) (run-test x name number))
;;;                     '((0 2 4 6 8) ("otto" "heinz" "frieda") (1 2 3)))
;;;
;;;     (space-points basis)   ; the points, as a lazy SRFI-41 stream of lists
;;;
;;; Python's 'for a, b, c in do(basis)' unpacks a tuple; Scheme APPLIES the
;;; procedure to the point -- one argument per dimension, as the tuple
;;; unpacks. Python's generator is a lazy stream here: a point is made when
;;; it is asked for, so a large basis costs no memory. ('do' is Scheme's own
;;; loop syntax and is not taken.)
;;;
;;;     An empty basis yields exactly one point, the empty one: the procedure
;;;     is called once, with no argument. A basis with an empty dimension
;;;     yields nothing.
;;;_____________________________________________________________________________
(define-module (hwut space-iterator)
  #:use-module (srfi srfi-41)
  #:export (space-points space-for-each))

(define (space-points basis)
  "RETURN: SRFI-41 stream of lists, every point of the cartesian product of
'basis' (a list of lists: one per dimension) in order, the rightmost
dimension fastest; one empty point for an empty basis, none where a
dimension is empty."
  (if (null? basis)
      (stream '())
      (stream-of (cons head tail)
                 (head in (list->stream (car basis)))
                 (tail in (space-points (cdr basis))))))

(define (space-for-each procedure basis)
  "RETURN: exact integer, the number of points; 'procedure' was applied to
every point of 'basis' in order, one argument per dimension."
  (stream-fold (lambda (n point) (apply procedure point) (+ n 1))
               0 (space-points basis)))
