;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: RACES DRAWN AS STRINGS -- the port of
;;;          'python/deterministic_timeline.py' (its module docstring is the
;;;          manual): each character of a timeline is one tick, a digit fires
;;;          the trigger at that tick, the lower digit first within a tick,
;;;          equal digits in registration order. After the last tick every
;;;          trigger is told 'on-termination' with the timeline's LENGTH.
;;;
;;;     (timeline-run
;;;       (lambda ()
;;;         (dispatcher-run
;;;           (make-dispatcher
;;;             (list (make-trigger "1 1 3 1   1" "SUB"
;;;                                 #:fire (lambda (self t) (display t)))
;;;                   (make-trigger "2  121  1  " "NOM" #:fire ...))))))
;;;
;;; A TASK IS A SUSPENDED COMPUTATION. Python's asyncio needs 'async def' and
;;; 'await' on every frame between the loop and the place that yields;
;;; Scheme captures the frames themselves: '(pause)' -- asyncio.sleep(0) --
;;; is an 'abort-to-prompt' to the task's prompt, the handler keeps the
;;; DELIMITED CONTINUATION, and the scheduler resumes it later by calling it.
;;; So 'fire' is a plain procedure, and any procedure it calls may pause --
;;; nothing is coloured 'async'.
;;;
;;;     (timeline-run thunk)    asyncio.run: 'thunk' is the main task; runs
;;;                             every task until the main one ends; returns
;;;                             its value or raises what it raised
;;;     (spawn thunk)           asyncio.create_task: a task, queued
;;;     (pause)                 asyncio.sleep(0): back to the end of the queue
;;;     (await task)            the task's value, or what it raised
;;;     (gather thunk ...)      asyncio.gather: each a task, in that order;
;;;                             the list of their values
;;;     (cancel! task)          task.cancel(): at its next resumption the task
;;;                             raises '&task-cancelled' where it paused; an
;;;                             'await' of it raises the same
;;;
;;; THE CLASSES ARE RECORDS AND CLOSURES: a trigger is a record of its
;;; timeline, its name and two procedures -- 'fire' (abstract: the default
;;; raises '&not-implemented') and 'on-termination' (optional: the default is
;;; silent). Python's subclass is a closure over its own state.
;;;_____________________________________________________________________________
(define-module (hwut deterministic-timeline)
  #:use-module (srfi srfi-9)
  #:use-module (ice-9 exceptions)
  #:use-module (ice-9 q)
  #:export (make-trigger trigger? trigger-timeline trigger-name
            trigger-fire trigger-on-termination
            make-dispatcher dispatcher? dispatcher-run dispatcher-stop!
            dispatcher->string
            timeline-run spawn pause await gather cancel! task? task-done?
            &not-implemented not-implemented-error?
            &task-cancelled task-cancelled?))

;;  ---------------------------------------------------------- the exceptions
(define-exception-type &not-implemented &error
  make-not-implemented-error not-implemented-error?)

(define-exception-type &task-cancelled &error
  make-task-cancelled task-cancelled?)

;;  ------------------------------------------------------------------- tasks
;;  'state' is one of: ready (not yet started), suspended, done, failed,
;;  cancelled. 'resume' is the delimited continuation of a suspended task.
(define-record-type <task>
  (%make-task thunk state resume value cancel-asked?)
  task?
  (thunk         task-thunk)
  (state         task-state     set-task-state!)
  (resume        task-resume    set-task-resume!)
  (value         task-value     set-task-value!)
  (cancel-asked? task-cancel-asked? set-task-cancel-asked?!))

(define (task-done? task)
  "RETURN: #t, where 'task' has ended -- returned, raised or was cancelled;
#f, while it is queued or suspended."
  (memq (task-state task) '(done failed cancelled)))

;;  THE PROMPT every task runs under, and the loop the running code is in.
(define task-tag     (make-prompt-tag "hwut-task"))
(define current-loop (make-parameter #f))

(define (spawn thunk)
  "RETURN: task, 'thunk' to be run as a task of the running 'timeline-run',
queued at the end -- it starts when the running task pauses or ends."
  (let ((task (%make-task thunk 'ready #f #f #f)))
    (enq! (or (current-loop) (error "spawn: no timeline-run is running")) task)
    task))

(define (pause)
  "RETURN: unspecified, once every task queued before this one had its turn
(asyncio.sleep(0)); raises '&task-cancelled' where the task was cancelled
meanwhile. Outside any task it returns at once."
  (when (current-loop)
    (when (eq? (abort-to-prompt task-tag) 'cancel)
      (raise-exception (make-task-cancelled)))))

(define (await task)
  "RETURN: object, the value of 'task' once it has returned; raises what it
raised, or '&task-cancelled' where it was cancelled. The awaiting task
pauses until then."
  (let loop ()
    (case (task-state task)
      ((done)      (task-value task))
      ((failed)    (raise-exception (task-value task)))
      ((cancelled) (raise-exception (make-task-cancelled)))
      (else        (pause) (loop)))))

(define (gather . thunk-list)
  "RETURN: list, the values of the thunks of 'thunk-list', each run as its
own task, queued in the order given; raises what the first failing one
raised."
  (map await (map spawn thunk-list)))

(define (cancel! task)
  "RETURN: unspecified. 'task' is asked to end: where it has not ended, its
next resumption raises '&task-cancelled' at the place it paused."
  (unless (task-done? task)
    (set-task-cancel-asked?! task #t)))

(define (step! queue task)
  "RETURN: unspecified. 'task' runs until it pauses (and is queued again) or
ends (its state and value set)."
  (define (body)
    "RETURN: unspecified; the task's thunk ran to its end, value or exception kept."
    (with-exception-handler
     (lambda (e)
       (set-task-value! task e)
       (set-task-state! task (if (task-cancelled? e) 'cancelled 'failed))
       #f)
     (lambda ()
       (set-task-value! task ((task-thunk task)))
       (set-task-state! task 'done))
     #:unwind? #t))
  (call-with-prompt task-tag
    (lambda ()
      (case (task-state task)
        ((ready)     (if (task-cancel-asked? task)
                         (set-task-state! task 'cancelled)
                         (body)))
        ((suspended) ((task-resume task)
                      (if (task-cancel-asked? task) 'cancel 'go)))))
    (lambda (resume)
      ;;  THE TASK PAUSED: what remains of it is 'resume'.
      (set-task-resume! task resume)
      (set-task-state! task 'suspended)
      (enq! queue task))))

(define (timeline-run thunk)
  "RETURN: object, the value of 'thunk' run as the main task of a fresh
loop, every task it spawns stepped in turn, round robin, in queue order;
raises what the main task raised. Tasks still suspended when the main one
ends are abandoned."
  (let ((queue (make-q)))
    (parameterize ((current-loop queue))
      (let ((main (spawn thunk)))
        (let loop ()
          (unless (or (task-done? main) (q-empty? queue))
            (step! queue (deq! queue))
            (loop)))
        (case (task-state main)
          ((done)      (task-value main))
          ((failed)    (raise-exception (task-value main)))
          (else        (raise-exception (make-task-cancelled))))))))

;;  ---------------------------------------------------------------- triggers
(define-record-type <trigger>
  (%make-trigger timeline name fire on-termination)
  trigger?
  (timeline       trigger-timeline)
  (name           trigger-name)
  (fire           %trigger-fire)
  (on-termination %trigger-on-termination))

(define (abstract-fire self pseudo-time)
  "RETURN: never; raises '&not-implemented'. A trigger that does nothing when
its tick comes has no reason to stand in the timeline: the base refuses."
  (raise-exception
   (make-exception (make-not-implemented-error)
                   (make-exception-with-message
                    (string-append "trigger '" (trigger-name self)
                                   "' has no 'fire'")))))

(define (silent-on-termination self end-tick)
  "RETURN: unspecified. Does nothing: a trigger with nothing to wind down is
ordinary."
  *unspecified*)

(define* (make-trigger timeline #:optional (name "")
                       #:key (fire abstract-fire)
                             (on-termination silent-on-termination))
  "RETURN: trigger, firing at the ticks 'timeline' marks with a digit: then
'(fire trigger tick)' is called; once the timeline has passed,
'(on-termination trigger end-tick)'. 'name' \"\" is replaced by
'trigger-<address>'."
  (%make-trigger timeline
                 (if (string-null? name)
                     (string-append "trigger-" (number->string (object-address timeline)))
                     name)
                 fire on-termination))

(define (trigger-fire trigger pseudo-time)
  "RETURN: what the trigger's 'fire' returns; it may pause."
  ((%trigger-fire trigger) trigger pseudo-time))

(define (trigger-on-termination trigger end-tick)
  "RETURN: what the trigger's 'on-termination' returns."
  ((%trigger-on-termination trigger) trigger end-tick))

;;  -------------------------------------------------------------- dispatcher
(define-record-type <dispatcher>
  (%make-dispatcher running? trigger-list tick-vector)
  dispatcher?
  (running?     dispatcher-running? set-dispatcher-running!)
  (trigger-list dispatcher-trigger-list)
  (tick-vector  dispatcher-tick-vector))

(define (build trigger-list)
  "RETURN: vector, one entry per tick as long as the LONGEST timeline; entry
't' the list of (priority . trigger) whose timeline carries a digit at 't',
sorted by priority -- equal priorities in registration order (a stable
sort). No trigger, or none with a timeline, gives the empty vector."
  (let* ((end-tick (apply max 0 (map (lambda (t) (string-length (trigger-timeline t)))
                                     trigger-list)))
         (result   (make-vector end-tick '())))
    (for-each
     (lambda (trigger)
       (string-for-each-index
        (lambda (t)
          (let ((c (string-ref (trigger-timeline trigger) t)))
            (when (char-numeric? c)
              (vector-set! result t (cons (cons (char->digit c) trigger)
                                          (vector-ref result t))))))
        (trigger-timeline trigger)))
     trigger-list)
    (vector-map! (lambda (entry) (stable-sort (reverse entry)
                                              (lambda (a b) (< (car a) (car b)))))
                 result)
    result))

(define (char->digit c)
  "RETURN: exact integer, the value of the decimal digit 'c'."
  (- (char->integer c) (char->integer #\0)))

(define (string-for-each-index procedure text)
  "RETURN: unspecified; 'procedure' was called with every index of 'text'."
  (do ((i 0 (+ i 1))) ((= i (string-length text)))
    (procedure i)))

(define (vector-map! procedure v)
  "RETURN: unspecified; every element of 'v' replaced by 'procedure' of it."
  (do ((i 0 (+ i 1))) ((= i (vector-length v)))
    (vector-set! v i (procedure (vector-ref v i)))))

(define (make-dispatcher trigger-list)
  "RETURN: dispatcher over the triggers of 'trigger-list', its schedule
built (see 'build')."
  (%make-dispatcher #t trigger-list (build trigger-list)))

(define (dispatcher-stop! dispatcher)
  "RETURN: unspecified. The run leaves the timeline at the next firing; it
still announces termination on its way out."
  (set-dispatcher-running! dispatcher #f))

(define (dispatcher-run dispatcher)
  "RETURN: unspecified. Steps the timeline tick by tick, firing every
trigger due in priority order and PAUSING after each one, so that a
consumer of what it produced may progress.

THE ANNOUNCEMENT ALWAYS FOLLOWS: walked to its end or stopped, every
trigger is told '(on-termination trigger end-tick)', 'end-tick' the
timeline's LENGTH. A cancellation is not an ending: '&task-cancelled'
leaves through here and nothing is announced."
  (let ((tick-vector (dispatcher-tick-vector dispatcher)))
    (let tick-loop ((t 0))
      (when (and (< t (vector-length tick-vector)) (dispatcher-running? dispatcher))
        (let fire-loop ((due (vector-ref tick-vector t)))
          (when (and (pair? due) (dispatcher-running? dispatcher))
            (trigger-fire (cdar due) t)
            (pause)
            (fire-loop (cdr due))))
        (tick-loop (+ t 1))))
    (for-each (lambda (trigger)
                (trigger-on-termination trigger (vector-length tick-vector)))
              (dispatcher-trigger-list dispatcher))))

(define (dispatcher->string dispatcher)
  "RETURN: string, the built schedule, one line per firing --
'[tick] (priority)name', ticks ascending, within a tick in firing order --
after the line 'TriggerDispatcher'."
  (let ((tick-vector (dispatcher-tick-vector dispatcher)))
    (string-join
     (cons "TriggerDispatcher"
           (let loop ((t 0) (result '()))
             (if (= t (vector-length tick-vector))
                 (reverse result)
                 (loop (+ t 1)
                       (append (reverse
                                (map (lambda (entry)
                                       (string-append "[" (number->string t) "] ("
                                                      (number->string (car entry)) ")"
                                                      (trigger-name (cdr entry))))
                                     (vector-ref tick-vector t)))
                               result)))))
     "\n")))
