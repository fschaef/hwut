;; @hwut {
;;     title      = "TriggerDispatcher: schedule, priority, and the end of time"
;;     choices {
;;         abstract    { features = ["guile-timeline"] }
;;         cancel      { features = ["guile-timeline"] }
;;         edges       { features = ["guile-timeline"] }
;;         priority    { features = ["guile-timeline"] }
;;         schedule    { features = ["guile-timeline"] }
;;         stable      { features = ["guile-timeline"] }
;;         stop        { features = ["guile-timeline"] }
;;         termination { features = ["guile-timeline"] }
;;         yielding    { features = ["guile-timeline"] }
;;     }
;;     interactive = true
;; }
;;
;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;; _____________________________________________________________________________
;;
;; PURPOSE: The Guile port of 'python/TEST/test-deterministic-timeline.py',
;;          choice for choice, held against its GOOD files by '.link'.
;;
;; Python's trigger SUBCLASSES are closures here: 'speaking-trigger' is a
;; trigger whose 'fire' says so; the producer of 'yielding' keeps its item in
;; a variable its two procedures close over. Python's coroutines are TASKS --
;; suspended computations, paused by '(pause)' -- and 'fire' is an ordinary
;; procedure.
;; _____________________________________________________________________________
(add-to-load-path (string-append (dirname (canonicalize-path (current-filename))) "/.."))
(use-modules (hwut runner) (hwut pytext) (hwut deterministic-timeline)
             (ice-9 exceptions))

(define (banner label)
  "RETURN: unspecified. Section heading."
  (display (string-append "\n--- " label " ---\n")))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline."
  (display (string-concatenate text-list))
  (newline))

(define (say-fires self t)
  "RETURN: unspecified. Says that 'self' fired, and at which tick."
  (say "  [t:" (number->string t) "] " (trigger-name self) " fires"))

(define* (speaking-trigger name timeline #:key (silent? #f) (fire say-fires))
  "RETURN: trigger 'name' on 'timeline' that says what it is asked to do,
and when -- the Python test's SpeakingTrigger; 'silent?' keeps its end
quiet, 'fire' replaces what it does at a tick."
  (say "SETUP: " (py-ljust name 7) " |" timeline "|")
  (make-trigger timeline name
                #:fire fire
                #:on-termination
                (lambda (self end-tick)
                  (unless silent?
                    (say "  [end:" (number->string end-tick) "] " name " notified")))))

(define (mute-trigger name timeline)
  "RETURN: trigger that fires and keeps the base's silent 'on-termination'
-- the Python test's MuteTrigger."
  (say "SETUP: " (py-ljust name 7) " |" timeline "|  (no on_termination override)")
  (make-trigger timeline name #:fire say-fires))

(define (dispatch trigger-list)
  "RETURN: unspecified. A dispatcher over 'trigger-list', run to completion."
  (timeline-run (lambda () (dispatcher-run (make-dispatcher trigger-list)))))

(define (run-schedule)
  "RETURN: unspecified. A digit's position is its tick."
  (banner "staggered: A at 0, B at 2, C at 4")
  (dispatch (list (speaking-trigger "A" "1    ")
                  (speaking-trigger "B" "  1  ")
                  (speaking-trigger "C" "    1")))
  (banner "a SHORT timeline stops contributing; the long one goes on")
  (dispatch (list (speaking-trigger "SHORT" "11")
                  (speaking-trigger "LONG"  "111111")))
  (banner "the SCHEDULE as built -- '[tick] (priority)name'")
  (say (dispatcher->string (make-dispatcher (list (speaking-trigger "A" "12")
                                                  (speaking-trigger "B" "21"))))))

(define (run-priority)
  "RETURN: unspecified. Lower digit first within one tick."
  (banner "digits swap between ticks: B leads at 0, A leads at 1")
  (dispatch (list (speaking-trigger "A" "21")
                  (speaking-trigger "B" "12")))
  (banner "0 is the strongest digit, 9 the weakest")
  (dispatch (list (speaking-trigger "WEAK"   "9")
                  (speaking-trigger "STRONG" "0"))))

(define (run-stable)
  "RETURN: unspecified. Equal digits fire in registration order."
  (banner "three triggers, all digit 1 at tick 0")
  (dispatch (list (speaking-trigger "first"  "1")
                  (speaking-trigger "second" "1")
                  (speaking-trigger "third"  "1")))
  (banner "registered BACKWARDS -- the order follows registration, not the name")
  (dispatch (list (speaking-trigger "third"  "1")
                  (speaking-trigger "second" "1")
                  (speaking-trigger "first"  "1"))))

(define (run-termination)
  "RETURN: unspecified. The end of the timeline is an event with a stated tick."
  (banner "end_tick is the LENGTH -- 5 characters, last firing at tick 0")
  (dispatch (list (speaking-trigger "EARLY" "1    ")))
  (banner "a trigger that NEVER fires is notified all the same")
  (dispatch (list (speaking-trigger "FIRES"  "1  ")
                  (speaking-trigger "SILENT" "   ")))
  (banner "the LONGEST timeline sets end_tick for everybody")
  (dispatch (list (speaking-trigger "SHORT" "1")
                  (speaking-trigger "LONG"  "1      ")))
  (banner "a trigger that does not override is simply silent at the end")
  (dispatch (list (speaking-trigger "SPEAKS" "1 ")
                  (mute-trigger     "MUTE"   "1 "))))

(define (run-yielding)
  "RETURN: unspecified. The run pauses for a consumer between firings: a
producer prepares one item per tick, the consumer -- another task -- takes
each before the next tick prepares one."
  (banner "producer fires at every tick; consumer waits between them")
  (let* ((item      #f)
         (finished? #f)
         (producer  (begin
                      (say "SETUP: " (py-ljust "PROD" 7) " |111|")
                      (make-trigger
                       "111" "PROD"
                       #:fire (lambda (self t)
                                (set! item (string-append "item@" (number->string t)))
                                (say "  [t:" (number->string t) "] PROD prepared " item))
                       #:on-termination (lambda (self end-tick)
                                          (set! finished? #t)
                                          (say "  [end:" (number->string end-tick)
                                               "] PROD announced end-of-stream")))))
         (consume   (lambda ()
                      (let loop ((taken 0))
                        (cond (item
                               (say "        consumer took " item)
                               (set! item #f)
                               (loop (+ taken 1)))
                              (finished?
                               (say "  consumer saw end-of-stream after "
                                    (number->string taken) " item(s)"))
                              (else (pause) (loop taken)))))))
    (timeline-run (lambda ()
                    (gather (lambda () (dispatcher-run (make-dispatcher (list producer))))
                            consume))))
  (newline)
  (say "Each item was taken BEFORE the next tick prepared one: the run yields."))

(define (run-stop)
  "RETURN: unspecified. A stopped run is an ended run: it still announces."
  (banner (string-append "stop() after the first tick -- ticks 1.. are not walked, "
                         "the announcement still comes"))
  (letrec* ((dispatcher #f)
            (stopper    (speaking-trigger
                         "STOPPER" "1111"
                         #:fire (lambda (self t)
                                  (say-fires self t)
                                  (say "  ... asks the dispatcher to stop")
                                  (dispatcher-stop! dispatcher))))
            (bystander  (speaking-trigger "OTHER" "1111")))
    (set! dispatcher (make-dispatcher (list stopper bystander)))
    (timeline-run (lambda () (dispatcher-run dispatcher))))
  (newline)
  (say "end_tick is still the timeline's length, not the tick the run stopped at."))

(define (run-cancel)
  "RETURN: unspecified. A cancellation is an abandonment: it announces nothing."
  (banner "cancel() the task carrying run() -- no announcement follows")
  (timeline-run
   (lambda ()
     (let* ((dispatcher (make-dispatcher (list (speaking-trigger "A" "1111111111"))))
            (task       (spawn (lambda () (dispatcher-run dispatcher)))))
       (pause)
       (cancel! task)
       (guard (e ((task-cancelled? e) (say "  run() was cancelled")))
         (await task)))))
  (newline)
  (say "No '[end:..]' line above: the triggers were abandoned, not ended."))

(define (run-edges)
  "RETURN: unspecified. Degenerate timelines announce and do not fail."
  (banner "an EMPTY timeline -- end_tick 0")
  (dispatch (list (speaking-trigger "EMPTY" "")))
  (banner "a timeline of BLANKS -- no digit, so nothing fires")
  (dispatch (list (speaking-trigger "BLANK" "    ")))
  (banner "NO TRIGGERS at all -- nothing to announce, and no failure")
  (dispatch '())
  (say "  (dispatcher ran; nothing was scheduled)")
  (banner "a timeline of blanks beside one that fires")
  (dispatch (list (speaking-trigger "BLANK" "   ")
                  (speaking-trigger "FIRES" " 1 "))))

(define (run-abstract)
  "RETURN: unspecified. 'fire' refuses; 'on-termination' is silent."
  (banner "the BASE 'fire' is abstract -- it refuses")
  (guard (e ((not-implemented-error? e)
             (say "  NotImplementedError -- as owed: a trigger must say what it does")))
    (dispatch (list (make-trigger "1" "BARE"))))
  (banner "the BASE 'on_termination' is optional -- it is silent")
  (trigger-on-termination (make-trigger "" "BARE") 0)
  (say "  returned quietly; nothing raised, nothing printed")
  (banner "a NAME given is the name kept")
  (say "  name: " (trigger-name (make-trigger "1" "GIVEN"))))

(hwut-runner-run
 (make-hwut-runner (command-line)
                   "TriggerDispatcher: schedule, priority, and the end of time"
                   `(("schedule"    . ,run-schedule)
                     ("priority"    . ,run-priority)
                     ("stable"      . ,run-stable)
                     ("termination" . ,run-termination)
                     ("yielding"    . ,run-yielding)
                     ("stop"        . ,run-stop)
                     ("cancel"      . ,run-cancel)
                     ("edges"       . ,run-edges)
                     ("abstract"    . ,run-abstract))))
