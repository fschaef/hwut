;; @hwut {
;;     title      = "space_iterator: every combination of a parameter basis"
;;     choices {
;;         product { features = ["guile-space"] }
;;         edges   { features = ["guile-space"] }
;;     }
;;     interactive = true
;; }
;;
;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;; _____________________________________________________________________________
;;
;; PURPOSE: The Guile port of 'python/TEST/test-space-iterator.py', choice
;;          for choice, held against its GOOD files by '.link'.
;; _____________________________________________________________________________
(add-to-load-path (string-append (dirname (canonicalize-path (current-filename))) "/.."))
(use-modules (hwut runner) (hwut pytext) (hwut space-iterator))

(define (banner label)
  "RETURN: unspecified. Section heading."
  (display (string-append "\n--- " label " ---\n")))

(define (points basis)
  "RETURN: unspecified. Every point of 'basis', one per line, then the count."
  (let ((n (space-for-each
            (lambda value-list
              (display (string-append "  (" (py-join ", " (map py-str value-list)) ")\n")))
            basis)))
    (display (string-append "  " (number->string n) " point(s)\n"))))

(define (run-product)
  "RETURN: unspecified. Three dimensions; the rightmost changes fastest."
  (banner "[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points")
  (points '((0 2 4) ("otto" "heinz") (1 2))))

(define (run-edges)
  "RETURN: unspecified. The empty basis, an empty dimension, one dimension."
  (banner "an EMPTY basis -- one point, the empty one")
  (points '())
  (banner "a basis with an EMPTY dimension -- nothing")
  (points '((1 2) () (3)))
  (banner "ONE dimension -- its values one by one")
  (points '(("a" "b" "c"))))

(hwut-runner-run
 (make-hwut-runner (command-line)
                   "space_iterator: every combination of a parameter basis"
                   `(("product" . ,run-product)
                     ("edges"   . ,run-edges))))
