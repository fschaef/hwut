#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; @hwut {
;;     title   = "Demo: what hwut tolerates, and where it is said"
;;     choices {
;;         plain       { features = ["demo-guile", "demo-guile+cover-exact-comparison"] }
;;         tolerance   { features = ["demo-guile", "demo-guile+cover-equivalence-pattern", "demo-guile+cover-numeric-ratio"]
;;                       tolerance {
;;                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
;;                           numeric_ratio = 0.01
;;                       } }
;;         constraints { features = ["demo-guile", "demo-guile+cover-constraints"]
;;                       tolerance {
;;                           constraints = ["load >= 0 and load <= 100",
;;                                          "even % 2 == 0",
;;                                          "twice == 2 * once"]
;;                       } }
;;         analogies   { features = ["demo-guile", "demo-guile+cover-analogies"] }
;;         race        { features = ["demo-guile", "demo-guile+cover-order-free-block"] }
;;         pool        { features = ["demo-guile", "demo-guile+cover-potpourri-subset-duplicates"] }
;;         progress    { features = ["demo-guile", "demo-guile+cover-visible-nothing"]
;;                       tolerance { nothing = ["[.]+"] } }
;;         lisp        { features = ["demo-guile", "demo-guile+cover-analogy-markers"]
;;                       tolerance { analogy = ["{", "}"] } }
;;         clusters    { features = ["demo-guile", "demo-guile+cover-point-cloud-pair-distance"] }
;;     }
;; }
;;
;; _____________________________________________________________________________
;; A TEST APPLICATION OF HWUT, FOR READING -- in Scheme (GNU Guile).
;;
;;     hwut.run                    runs every choice below, compares with GOOD/
;;     hwut.play demo.scm plain    runs one choice and records it in OUT/
;;     hwut.accept demo.scm plain  blesses that recording as GOOD
;;     hwut.config.show demo.scm   prints what hwut READ from the header above
;;
;; The header above is the whole configuration: a title, and one scope per
;; choice. hwut calls 'guile --no-auto-compile demo.scm <choice>' (the 'scheme'
;; interpreter of 'hwut-root.conf') and compares what it prints on stdout
;; with 'GOOD/demo.scm--<choice>.txt' -- a '.link' to the Python demo's GOOD:
;; the same choice prints the same text. '<hwut-end>' closes the stream.
;;
;; Every run is seeded by the clock, so the output differs from run to run --
;; and every choice passes anyway. What each choice shows, and why it passes,
;; is said in '../../python/TEST/demo.py' and in 'README.txt' beside this file.
;;
;; This file needs no test support: Guile's own threads, mutexes and random
;; state. The workers of 'race' and 'pool' are POSIX threads.
;; _____________________________________________________________________________
(use-modules (ice-9 threads) (srfi srfi-1))

(define GREETING-LIST '("hello" "bonjour" "hallo" "buongiorno" "hola" "ahoj"))

(set! *random-state* (seed->random-state (+ (* (car (gettimeofday)) 1000000) (cdr (gettimeofday)))))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stdout."
  (display (string-concatenate text-list))
  (newline))

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

(define (right text width)
  "RETURN: string, 'text' padded with blanks on the left to 'width'."
  (string-pad text (max width (string-length text))))

(define (uniform low high)
  "RETURN: inexact real, drawn uniformly from [low, high]."
  (+ low (* (- high low) (random:uniform))))

(define (randint low high)
  "RETURN: exact integer, drawn uniformly from low .. high, both included."
  (+ low (random (+ (- high low) 1))))

(define (sample-two low high)
  "RETURN: list of two different exact integers, drawn from low .. high-1."
  (let* ((a (+ low (random (- high low))))
         (b (let loop () (let ((b (+ low (random (- high low))))) (if (= a b) (loop) b)))))
    (list a b)))

(define (hex n width upper?)
  "RETURN: string, 'n' in hexadecimal, zero-padded to 'width'."
  (let ((text (number->string n 16)))
    (string-pad (if upper? (string-upcase text) text) (max width (string-length text)) #\0)))

(define (plain)
  "RETURN: unspecified. Prints what never varies."
  (say "the first line")
  (say "the second line: 1 2 3"))

(define (tolerance)
  "RETURN: unspecified. Prints a greeting and a value, both drawn at random."
  (say "greeting: " (list-ref GREETING-LIST (random (length GREETING-LIST))) ", world")
  (say "value:    " (fixed (uniform 19.91 20.09) 2)))

(define (constraints)
  "RETURN: unspecified. Prints bindings, each drawn at random, each lawful."
  (say "load  ((load: " (fixed (uniform 0.0 100.0) 1) ")) %")
  (say "even  ((even: " (number->string (* 2 (randint 0 500))) "))")
  (let ((once (randint 1 50)))
    (say "once  ((once: " (number->string once) "))")
    (say "twice ((twice: " (number->string (* 2 once)) "))")))

(define (analogies)
  "RETURN: unspecified. Prints two handles, each drawn at random, each used
consistently from opening to closing."
  (let* ((pair   (sample-two #x1000 #x10000))
         (first  (hex (car pair) 4 #f))
         (second (hex (cadr pair) 4 #f)))
    (say "open  ((" first ")) input.txt")
    (say "open  ((" second ")) output.txt")
    (say "read  ((" first ")) 17 lines")
    (say "write ((" second ")) 17 lines")
    (say "close ((" first "))")
    (say "close ((" second "))")))

(define (race)
  "RETURN: unspecified. Three workers print as they finish; the order is the
scheduler's, the facts are not. The program frames the unordered block
itself: '##! potpourri' ... '####'."
  (let* ((lock (make-mutex))
         (work (lambda (name jobs)
                 (usleep (inexact->exact (round (uniform 0.0 20000.0))))
                 (with-mutex lock
                   (say "worker " name " done: " (number->string jobs) " jobs")))))
    (say "start")
    (say "##! potpourri")
    (force-output)
    (for-each join-thread
              (map (lambda (args) (call-with-new-thread (lambda () (apply work args))))
                   '(("A" 3) ("B" 5) ("C" 2))))
    (say "####")
    (say "all joined")))

(define (pool)
  "RETURN: unspecified. Four workers take twelve jobs from one queue; each
reports the job it finished. Who takes how many is the scheduler's."
  (let* ((lock      (make-mutex))
         (job-list  (iota 12))
         (done-list '())
         (take!     (lambda ()                 ; #t where a job was taken
                      (with-mutex lock
                        (and (pair? job-list) (begin (set! job-list (cdr job-list)) #t)))))
         (work      (lambda (name)
                      (let loop ()
                        (when (take!)
                          (usleep (inexact->exact (round (uniform 0.0 5000.0))))
                          (with-mutex lock
                            (set! done-list (cons (string-append "job done by worker " name)
                                                  done-list)))
                          (loop))))))
    (for-each join-thread
              (map (lambda (name) (call-with-new-thread (lambda () (work name))))
                   '("A" "B" "C" "D")))
    (say "twelve jobs, four workers:")
    (say "##! potpourri subset duplicates")
    (for-each say (reverse done-list))
    (say "####")
    (say "jobs done: " (number->string (length done-list)))))

(define (progress)
  "RETURN: unspecified. A download that prints dots while it waits; how many
is the network's."
  (say "connecting to mirror")
  (do ((i (randint 0 3) (- i 1))) ((= i 0))
    (say (make-string (randint 1 8) #\.)))
  (say "connected")
  (say "received 1024 bytes"))

(define (lisp)
  "RETURN: unspecified. A Lisp session at its prompt: two objects, each
printed with its address '{...}', drawn anew per run, and each used again."
  (let* ((pair   (sample-two #x1000000000 #x1100000000))
         (table  (hex (car pair) 0 #t))
         (thread (hex (cadr pair) 0 #t)))
    (say "* (defvar *cache* (make-hash-table))")
    (say "#<HASH-TABLE :TEST EQL :COUNT 0 {" table "}>")
    (say "* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))")
    (say "#<THREAD \"worker\" RUNNING {" thread "}>")
    (say "* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))")
    (say "#<THREAD \"worker\" RUNNING {" thread "}>")
    (say "* *cache*")
    (say "#<HASH-TABLE :TEST EQL :COUNT 1 {" table "}>")))

(define (distance2 p c)
  "RETURN: real, the squared distance of the points 'p' and 'c', pairs (x . y)."
  (+ (expt (- (car p) (car c)) 2) (expt (- (cdr p) (cdr c)) 2)))

(define (arg-best item-list score better?)
  "RETURN: the item of 'item-list' whose 'score' is best by 'better?' -- the
first of equals, as Python's 'min'/'max' with 'key'."
  (fold (lambda (item best) (if (better? (score item) (score best)) item best))
        (car item-list) (cdr item-list)))

(define (clusters)
  "RETURN: unspecified. Clusters 90 noisy points around three centres and
prints the centroids in the order the run found them."
  (let* ((centre-list '((1.0 . 1.0) (5.0 . 4.0) (9.0 . 1.0)))
         (point-list  (list->vector
                       (append-map (lambda (c)
                                     (map (lambda (_) (cons (+ (car c) (* 0.3 (random:normal)))
                                                            (+ (cdr c) (* 0.3 (random:normal)))))
                                          (iota 30)))
                                   centre-list))))
    ;;  Fisher-Yates, as Python's 'shuffle'.
    (do ((i (- (vector-length point-list) 1) (- i 1))) ((< i 1))
      (let* ((j (random (+ i 1))) (t (vector-ref point-list i)))
        (vector-set! point-list i (vector-ref point-list j))
        (vector-set! point-list j t)))
    (let* ((point-list (vector->list point-list))
           ;;  The start: one point at random, then twice the point farthest
           ;;  from every start chosen so far -- one start per cluster.
           (start-list (let loop ((s (list (list-ref point-list (random 90)))))
                         (if (= (length s) 3)
                             s
                             (loop (append s (list (arg-best point-list
                                                             (lambda (p) (apply min (map (lambda (c) (distance2 p c)) s)))
                                                             >)))))))
           (centroid-list
            (let loop ((c start-list) (round-n 10))
              (if (= round-n 0)
                  c
                  (let ((member-v (make-vector 3 '())))
                    (for-each (lambda (p)
                                (let ((i (arg-best '(0 1 2) (lambda (i) (distance2 p (list-ref c i))) <)))
                                  (vector-set! member-v i (cons p (vector-ref member-v i)))))
                              point-list)
                    (loop (map (lambda (m)
                                 (let ((m (reverse m)))
                                   (cons (/ (apply + (map car m)) (length m))
                                         (/ (apply + (map cdr m)) (length m)))))
                               (vector->list member-v))
                          (- round-n 1)))))))
      (say "centroids (x y), in the order found:")
      (say "##! point-cloud limit=0.3 pair dist=Linf")
      (for-each (lambda (c) (say "    " (right (fixed (car c) 2) 5) " " (right (fixed (cdr c) 2) 5)))
                centroid-list)
      (say "####"))))

(define CHOICE-LIST
  `(("plain" . ,plain) ("tolerance" . ,tolerance) ("constraints" . ,constraints)
    ("analogies" . ,analogies) ("race" . ,race) ("pool" . ,pool)
    ("progress" . ,progress) ("lisp" . ,lisp) ("clusters" . ,clusters)))

(let* ((argv   (command-line))
       (choice (if (> (length argv) 1) (cadr argv) ""))
       (entry  (assoc choice CHOICE-LIST)))
  (unless entry
    (say "choices: " (string-join (map car CHOICE-LIST) ", "))
    (exit 1))
  ((cdr entry))
  (say "<hwut-end>"))
