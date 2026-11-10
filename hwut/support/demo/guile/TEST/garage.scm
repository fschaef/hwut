#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; @hwut {
;;     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
;;     interactive = true
;;     choices {
;;         space       { features = ["demo-guile+cover-space-from-hocon", "demo-guile+cover-space-iterator", "demo-guile+cover-hwut-runner"]
;;                       tolerance { constraints = ["mismatches == 0"] } }
;;         random      { features = ["demo-guile+cover-deterministic-stream", "demo-guile+cover-hwut-runner"]
;;                       tolerance { constraints = ["mismatches == 0"] } }
;;         race-naive  { features = ["demo-guile+cover-deterministic-timeline", "demo-guile+cover-space-iterator", "demo-guile+cover-hwut-runner"]
;;                       tolerance { constraints = ["overbooked > 0"] } }
;;         race-atomic { features = ["demo-guile+cover-deterministic-timeline", "demo-guile+cover-space-iterator", "demo-guile+cover-hwut-runner"]
;;                       tolerance { constraints = ["overbooked == 0"] } }
;;     }
;; }
;;
;; _____________________________________________________________________________
;; SUBJECT  the counter of free spaces at a garage's gates: which cars it
;;          admits, which it refuses, and how many stand inside.
;; REQUIREMENT  The garage admits a car only while a space is free, lets a car
;;              out only while one stands inside, and never holds more cars
;;              than it has spaces -- also when two gates admit at once.
;;
;; No choice writes its cases out by hand. Each GENERATES them, with the
;; Scheme test support (hwut/support/test_writing/guile, found through
;; 'support-path.scm'):
;;
;; space        'garage-space.hocon' read by '(hwut hocon)'; every combination
;;              walked by '(hwut space-iterator)': 3 x 5 x 4 = 60 cases,
;;              checked against the model.
;; random       '(make-deterministic-stream 4711)' draws 1000 cars: the same
;;              draw on every machine and in every language hwut supports,
;;              so the GOOD is the Python demo's, exactly.
;; race-naive   two gates, one free space, all six interleavings of two
;;              two-step gates played by '(hwut deterministic-timeline)' --
;;              'fire' an ordinary procedure, no coroutine. 'overbooked > 0':
;;              the GOOD is the accepted violation report.
;; race-atomic  the same, the gate checking and admitting in ONE step.
;;
;; THE FRONT END is '(hwut runner)': the choice map below is the whole
;; command line, '--hwut-info' included; 'interactive = true' runs every
;; choice in one Guile process. '../../python/TEST/garage.py' says more.
;; _____________________________________________________________________________
(load "support-path.scm")
(use-modules (hwut runner) (hwut hocon) (hwut space-iterator)
             (hwut deterministic-random) (hwut deterministic-timeline)
             (ice-9 rdelim) (srfi srfi-1))

(define HERE (dirname (canonicalize-path (current-filename))))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stdout."
  (display (string-concatenate text-list))
  (newline))

(define (left text width)
  "RETURN: string, 'text' padded with blanks on the right to 'width'."
  (string-pad-right text (max width (string-length text))))

(define (right text width)
  "RETURN: string, 'text' padded with blanks on the left to 'width'."
  (string-pad text (max width (string-length text))))

(define (int n) "RETURN: string, the exact integer 'n' in decimal." (number->string n))

;;  ------------------------------------------------- the unit under test
;;  A garage is a vector #(capacity occupied).
(define (make-garage capacity)       "RETURN: garage, empty, of 'capacity' spaces." (vector capacity 0))
(define (garage-capacity g)          "RETURN: exact integer, the spaces."           (vector-ref g 0))
(define (garage-occupied g)          "RETURN: exact integer, the cars inside."      (vector-ref g 1))
(define (garage-occupied-set! g n)   "RETURN: unspecified."                         (vector-set! g 1 n))

(define (garage-free g)
  "RETURN: exact integer, the number of spaces free now -- negative where the
garage is overbooked."
  (- (garage-capacity g) (garage-occupied g)))

(define (garage-arrive! g)
  "RETURN: #t, a car was admitted, if a space was free; #f, else (the car is
refused)."
  (and (> (garage-free g) 0)
       (begin (garage-occupied-set! g (+ (garage-occupied g) 1)) #t)))

(define (garage-leave! g)
  "RETURN: #t, a car drove out, if one stood inside; #f, else."
  (and (> (garage-occupied g) 0)
       (begin (garage-occupied-set! g (- (garage-occupied g) 1)) #t)))

;;  ------------------------------------- space -- the tested space from HOCON
(define (read-space path)
  "RETURN: list of (name . values), the dimensions of the space in 'path', in
the order written. Every fault the HOCON reader found is printed with '!!'
first."
  (let ((line-list (call-with-input-file path
                     (lambda (port)
                       (let loop ((i 1) (result '()))
                         (let ((text (read-line port)))
                           (if (eof-object? text)
                               (reverse result)
                               (loop (+ i 1) (cons (make-source-line text i 0) result)))))))))
    (call-with-values (lambda () (hocon-parse line-list (basename path)))
      (lambda (document fault-list)
        (for-each (lambda (fault) (say "!! " (hocon-fault->string fault))) fault-list)
        (map (lambda (entry)
               (cons (hocon-entry-key entry)
                     (map hocon-scalar-value (hocon-list-items (hocon-entry-node entry)))))
             (hocon-object-entries (hocon-entry-node (hocon-object-get document "space"))))))))

(define (list-text value-list)
  "RETURN: string, the integers 'value-list' as Python prints a list: '[1, 2]'."
  (string-append "[" (string-join (map int value-list) ", ") "]"))

(define (space)
  "RETURN: unspecified. Prints every case of the space as a matrix cell."
  (let* ((dimension-list (read-space (string-append HERE "/garage-space.hocon")))
         (value-list     (map cdr dimension-list))
         (row-table      (make-hash-table))
         (mismatch-n     0))
    (say "space: " (string-join (map (lambda (d) (string-append (car d) " " (list-text (cdr d))))
                                     dimension-list)
                                "  x  "))
    (say "cell: cars inside / cars refused at the gate ('!!' differs from the model)")
    (space-for-each
     (lambda (capacity arriving leaving)
       (let* ((garage   (make-garage capacity))
              (refused  (count not (map (lambda (i) (garage-arrive! garage)) (iota arriving))))
              (left-n   (length (filter-map (lambda (i) (garage-leave! garage)) (iota leaving))))
              (admitted (min arriving capacity))
              (expected (list (- admitted (min leaving admitted)) (- arriving admitted)))
              (got      (list (garage-occupied garage) refused))
              (mark     (if (equal? got expected) "  " "!!"))
              (key      (list capacity arriving)))
         (unless (equal? got expected) (set! mismatch-n (+ mismatch-n 1)))
         (hash-set! row-table key (append (hash-ref row-table key '())
                                          (list (string-append (int (car got)) "/" (int (cadr got)) mark))))))
     value-list)
    (for-each
     (lambda (capacity)
       (say (string-trim-right
             (string-append "capacity " (int capacity) "   "
                            (string-join (map (lambda (l) (string-append "leave " (left (int l) 3)))
                                              (caddr value-list))
                                         "  "))))
       (for-each (lambda (arriving)
                   (say (string-trim-right
                         (string-append "  arrive " (int arriving) "   "
                                        (string-join (map (lambda (c) (left c 9))
                                                          (hash-ref row-table (list capacity arriving)))
                                                     "  ")))))
                 (cadr value-list)))
     (car value-list))
    (say "cases " (int (* (hash-count (const #t) row-table) (length (caddr value-list))))
         ", differing from the model ((mismatches: " (int mismatch-n) "))")))

;;  -------------------- random -- a deterministic stream of arrivals and departures
(define (random-stream)
  "RETURN: unspecified. Prints the summary of 1000 drawn cars, model-checked."
  (let ((stream    (make-deterministic-stream 4711))
        (garage    (make-garage 5))
        (histogram (make-vector 6 0)))
    (let loop ((i 0) (model 0) (arrive 0) (refused 0) (leave 0) (empty 0) (mismatch-n 0) (strip '()))
      (if (< i 1000)
          (let* ((in?      (stream-coin stream 0.55))
                 (ok?      (if in? (garage-arrive! garage) (garage-leave! garage)))
                 (model    (if in? (min 5 (+ model 1)) (max 0 (- model 1)))))
            (vector-set! histogram (garage-occupied garage)
                         (+ 1 (vector-ref histogram (garage-occupied garage))))
            (loop (+ i 1) model
                  (if in? (+ arrive 1) arrive)
                  (if (and in? (not ok?)) (+ refused 1) refused)
                  (if in? leave (+ leave 1))
                  (if (and (not in?) (not ok?)) (+ empty 1) empty)
                  (if (= (garage-occupied garage) model) mismatch-n (+ mismatch-n 1))
                  (cons (if in? #\+ #\-) strip)))
          (begin
            (say "seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves")
            (say "first 60: " (substring (list->string (reverse strip)) 0 60))
            (say "arrivals " (int arrive) ", refused " (int refused) "; departures " (int leave)
                 ", from an empty garage " (int empty))
            (say "cars inside after each event:")
            (for-each (lambda (n)
                        (let ((count (vector-ref histogram n)))
                          (say "    " (int n) "  " (right (int count) 4) "  "
                               (make-string (quotient count 10) #\#))))
                      (iota 6))
            (say "steps differing from the model ((mismatches: " (int mismatch-n) "))"))))))

;;  ------------------------------------------ race -- two gates on drawn timelines
(define (make-gate name timeline garage atomic? log!)
  "RETURN: trigger, a gate on 'timeline': its first tick checks, its second
admits -- or, 'atomic?', checks and admits at once and then opens."
  (let ((step 0) (saw-free? #f))
    (make-trigger
     timeline name
     #:fire (lambda (self tick)
              (cond ((and (= step 0) atomic?)
                     (set! saw-free? (garage-arrive! garage))
                     (log! (string-append name (if saw-free? " checks+admits" " refuses"))))
                    ((= step 0)
                     (set! saw-free? (> (garage-free garage) 0))
                     (log! (string-append name " sees " (int (garage-free garage)) " free")))
                    (atomic?
                     (log! (string-append name (if saw-free? " opens" " stays shut"))))
                    (saw-free?
                     (garage-occupied-set! garage (+ 1 (garage-occupied garage)))   ; the naive admit
                     (log! (string-append name " admits")))
                    (else
                     (log! (string-append name " refuses"))))
              (set! step (+ step 1))))))

(define (interleaving-list)
  "RETURN: list of (timeline-a timeline-b), every pair of timelines in four
ticks in which each of two gates fires twice, never at the same tick."
  (let ((result '())
        (line   (lambda (x y) (list->string (map (lambda (t) (if (or (= t x) (= t y)) #\1 #\space))
                                                 (iota 4))))))
    (space-for-each (lambda (a1 a2 b1 b2)
                      (when (and (< a1 a2) (< b1 b2)
                                 (= 4 (length (delete-duplicates (list a1 a2 b1 b2)))))
                        (set! result (cons (list (line a1 a2) (line b1 b2)) result))))
                    (make-list 4 (iota 4)))
    (reverse result)))

(define (race atomic?)
  "RETURN: unspecified. Plays every interleaving of two gates at one space."
  (say "one free space, two gates, one car at each; timelines: a digit fires")
  (say "    gate A  gate B  what happens                                    inside")
  (let ((overbooked-n 0))
    (for-each
     (lambda (pair)
       (let* ((garage     (make-garage 1))
              (event-list '())
              (log!       (lambda (text) (set! event-list (append event-list (list text)))))
              (gate-list  (list (make-gate "A" (car pair) garage atomic? log!)
                                (make-gate "B" (cadr pair) garage atomic? log!))))
         (timeline-run (lambda () (dispatcher-run (make-dispatcher gate-list))))
         (let ((over? (> (garage-occupied garage) (garage-capacity garage))))
           (when over? (set! overbooked-n (+ overbooked-n 1)))
           (say (string-trim-right
                 (string-append "    \"" (car pair) "\"  \"" (cadr pair) "\"  "
                                (left (string-join event-list ", ") 46) "  "
                                (int (garage-occupied garage)) " " (if over? "!!" "  ")))))))
     (interleaving-list))
    (say "interleavings overbooking the garage ((overbooked: " (int overbooked-n) ")) of "
         (int (length (interleaving-list))))))

(hwut-runner-run
 (make-hwut-runner (command-line)
                   "Demo: a garage's space counter -- a space, a stream and races, generated;"
                   `(("space"       . ,space)
                     ("random"      . ,random-stream)
                     ("race-naive"  . ,(lambda () (race #f)))
                     ("race-atomic" . ,(lambda () (race #t))))))
