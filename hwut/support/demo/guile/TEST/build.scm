#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; @hwut {
;;     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
;;     pype    = "build.pypes"
;;     same    = true
;;     choices = ["serial", "parallel"]
;;     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
;;                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
;;                 "pype-quantity", "pype-anchors-globs-flush"]
;;     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
;; }
;;
;; _____________________________________________________________________________
;; SUBJECT  the log of a recursive build -- configure, then the directories
;;          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
;;          a pype system makes of it.
;; REQUIREMENT  A parallel build builds what the serial build builds: the same
;;              sources, the same warnings, the same archives and the same
;;              program, linked from the same parts.
;;
;; The application only REPORTS the build as it happens, as 'make -w' would.
;; The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
;; between it and the comparison (hwut runs it; the application prints no
;; '<hwut-end>'): 'normalise.pype' strips a parallel job's tag, 'build.pype'
;; makes the summary -- see their own comments, and
;; '../../python/TEST/build.py'.
;;
;; 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.scm.txt'. Serial or
;; parallel, the summary must be the same. The laws: the compile times sum
;; to under 5 s, and nothing in the log broke the build's grammar.
;; _____________________________________________________________________________
(use-modules (ice-9 threads) (srfi srfi-1))

;;  What each directory does: its sources, warnings and products.
(define DIRECTORY-LIST
  '(("lib"         ("lib/str.c" "lib/num.c" "lib/map.c")
                   (("lib/num.c" . "lib/num.c:14:9: warning: unused variable 'n'"))
                   "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o")
    ("app/plugins" ("app/plugins/png.c" "app/plugins/svg.c")
                   (("app/plugins/svg.c" . "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'"))
                   "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o")
    ("app"         ("app/main.c" "app/cli.c")
                   ()
                   "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a")))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stdout, flushed."
  (display (string-concatenate text-list))
  (newline)
  (force-output))

(define (fixed x digit-n)
  "RETURN: string, 'x' with 'digit-n' digits after the point, rounded as
Python's '%.<n>f' rounds: the exact binary value, half to even."
  (let* ((scale (expt 10 digit-n))
         (n     (round (* (inexact->exact x) scale)))
         (body  (number->string (abs n)))
         (body  (if (<= (string-length body) digit-n)
                    (string-append (make-string (- (+ digit-n 1) (string-length body)) #\0) body)
                    body))
         (cut   (- (string-length body) digit-n)))
    (string-append (if (< n 0) "-" "")
                   (substring body 0 cut)
                   (if (> digit-n 0) (string-append "." (substring body cut)) ""))))

(define (compile-lines name)
  "RETURN: list of strings, what building directory 'name' prints, its
sources compiled in the time each takes."
  (let ((spec (assoc-ref DIRECTORY-LIST name)))
    (append-map
     (lambda (source)
       (let* ((took  (+ 0.04 (* 0.08 (random:uniform))))
              (spent (if (< took 0.1)
                         (string-append (number->string (inexact->exact (truncate (* took 1000)))) " ms")
                         (string-append (fixed took 2) " s")))
              (object (string-append (substring source 0 (- (string-length source) 2)) ".o")))
         (usleep (inexact->exact (round (* took 1000000))))
         (cons (string-append "cc -c " source " -o " object " (took " spent ")")
               (let ((warning (assoc-ref (cadr spec) source)))
                 (if warning (list warning) '())))))
     (car spec))))

(define* (directory-block name level #:optional (inner #f))
  "RETURN: list of strings, the block 'make -w' prints for 'name' at
'level', the block of 'inner' nested before the product."
  (let ((head (string-append "make[" (number->string level) "]: ")))
    (append (list (string-append head "Entering directory '" name "'"))
            (compile-lines name)
            (if inner (directory-block inner (+ level 1)) '())
            (list (caddr (assoc-ref DIRECTORY-LIST name))
                  (string-append head "Leaving directory '" name "'")))))

(define (configure)
  "RETURN: unspecified. Prints what 'configure' prints, and that make enters
the top directory."
  (say "configure: checking for cc... cc")
  (say "configure: checking for ar... ar")
  (say "make: Entering directory 'demo'"))

(define (serial)
  "RETURN: unspecified. Builds one directory after the other."
  (configure)
  (for-each say (directory-block "lib" 1))
  (for-each say (directory-block "app" 1 "app/plugins"))
  (say "make: Leaving directory 'demo'"))

(define (parallel)
  "RETURN: unspecified. Builds 'lib' and 'app' at once. Each job prints its
block whole when done ('make -O'), every line tagged with the job; which job
finishes first is the scheduler's."
  (configure)
  (let* ((lock (make-mutex))
         (job  (lambda (slot name inner)
                 (let ((block (directory-block name 1 inner)))
                   (with-mutex lock
                     (for-each (lambda (line) (say "job" (number->string slot) ": " line)) block))))))
    (for-each join-thread
              (list (call-with-new-thread (lambda () (job 1 "lib" #f)))
                    (call-with-new-thread (lambda () (job 2 "app" "app/plugins"))))))
  (say "make: Leaving directory 'demo'"))

(define CHOICE-LIST `(("serial" . ,serial) ("parallel" . ,parallel)))

(set! *random-state* (seed->random-state (let ((t (gettimeofday))) (+ (* (car t) 1000000) (cdr t)))))
(let* ((argv   (command-line))
       (choice (if (> (length argv) 1) (cadr argv) ""))
       (entry  (assoc choice CHOICE-LIST)))
  (unless entry
    (say "choices: " (string-join (map car CHOICE-LIST) ", "))
    (exit 1))
  ((cdr entry)))
