;; @hwut {
;;     title      = "hwut_fsm: a state machine as the test's model of the system"
;;     choices {
;;         dfa       { features = ["guile-fsm"] }
;;         forbidden { features = ["guile-fsm"] }
;;         masks     { features = ["guile-fsm"] }
;;         model     { features = ["guile-fsm"] }
;;         nfa       { features = ["guile-fsm"] }
;;         refused   { features = ["guile-fsm"] }
;;         report    { features = ["guile-fsm"] }
;;         syntax    { features = ["guile-fsm"] }
;;     }
;;     interactive = true
;; }
;;
;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;; _____________________________________________________________________________
;;
;; PURPOSE: The Guile port of 'python/TEST/test-hwut_fsm.py', choice for
;;          choice, held against its GOOD files by '.link'.
;; _____________________________________________________________________________
(add-to-load-path (string-append (dirname (canonicalize-path (current-filename))) "/.."))
(use-modules (hwut runner) (hwut pytext) (hwut fsm) (ice-9 exceptions))

;;  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
;;  a fault while busy crashes it -- which must never happen.
(define PROTOCOL "
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
")

(define (banner label)
  "RETURN: unspecified. Section heading."
  (display (string-append "\n--- " label " ---\n")))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline."
  (display (string-concatenate text-list))
  (newline))

(define-syntax-rule (fsm-error-said body ...)
  ;; RETURN: what 'body' returns; an '&fsm-error' it raises is printed as
  ;; Python prints 'FsmError: <message>'.
  (guard (e ((fsm-error? e) (say "FsmError: " (exception-message e))))
    body ...))

(define (path-text path)
  "RETURN: string, a path of 'fsm-path-to' as Python prints the tuple --
'None' for #f."
  (if path (py-tuple-repr path) "None"))

(define (run-syntax)
  "RETURN: unspecified. Models read from text and written back."
  (banner "the protocol, written back")
  (say (fsm->string (fsm-from-string PROTOCOL)))
  (banner "the author's form: 'state', a chain, ':', blanks around '-->'")
  (say (fsm->string (fsm-from-string "
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    "))))

(define (run-refused)
  "RETURN: unspecified. Each model that cannot be meant, and why."
  (for-each
   (lambda (text)
     (banner (string-join (string-split text #\newline) " | "))
     (fsm-error-said
      (fsm-from-string text)
      (say "accepted")))
   '("A ---( x )---> B\n: ---( x )---> C"
     "A ---(  )---> B"
     ": ---( x )---> B"
     "A B ---( x )---> C"
     "initial: A, B\nA ---( x )---> B"
     "forbidden: Q\nA ---( x )---> B"
     "# nothing but a comment")))

(define (run-dfa)
  "RETURN: unspecified. Events fired, one machine."
  (let ((m (fsm-from-string PROTOCOL)))
    (let loop ((event-list '("request" "release" "grant" "release" "jump" "request"))
               (number 1))
      (when (pair? event-list)
        (let ((moved (fsm-fire! m (car event-list) #:where number)))
          (say "    " (py-ljust (car event-list) 8) " -> " (py-ljust (py-bool moved) 5)
               " now " (py-ljust (fsm-state m) 8) " allowed: "
               (string-join (fsm-allowed m) ", ")))
        (loop (cdr event-list) (+ number 1))))
    (banner "questions where it stands")
    (say "can('grant')   " (py-bool (fsm-can? m "grant")))
    (say "can('release') " (py-bool (fsm-can? m "release")))
    (say "in_state('waiting') " (py-bool (fsm-in-state? m "waiting")))
    (say "trace: " (string-join
                    (map (lambda (t)
                           (string-append (py-str (car t)) ":" (caddr t) ">" (cadddr t)))
                         (fsm-trace m))
                    " "))))

(define (run-nfa)
  "RETURN: unspecified. DFA off: several states at once."
  (let ((m (fsm-from-string "
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    " #:dfa? #f)))
    (for-each (lambda (event)
                (fsm-fire! m event #:where (string-append "t=" event))
                (say "    after " event ": " (string-join (fsm-current m) ", ")))
              '("x" "z" "y"))
    (banner "'state' asked of a set")
    (fsm-reset! m)
    (fsm-fire! m "x")
    (fsm-error-said (say (fsm-state m)))))

(define (run-forbidden)
  "RETURN: unspecified. A forbidden state entered."
  (let ((m (fsm-from-string PROTOCOL)))
    (let loop ((event-list '("request" "grant" "fault")) (number 1))
      (when (pair? event-list)
        (say "    " (py-ljust (car event-list) 8) " -> "
             (py-bool (fsm-fire! m (car event-list) #:where number)))
        (loop (cdr event-list) (+ number 1))))
    (say "now in " (fsm-state m) " -- breaches: " (number->string (fsm-breach-n m)))))

(define (run-model)
  "RETURN: unspecified. The model alone."
  (let ((m (fsm-from-string (string-append PROTOCOL "\n    state limbo\n"
                                           "    limbo ---( kick )---> idle\n"))))
    (say "check: " (number->string (fsm-check m)))
    (banner "path_to")
    (for-each (lambda (state)
                (say "    " (py-ljust state 8) " " (path-text (fsm-path-to m state))))
              '("busy" "crashed" "limbo" "idle"))
    (fsm-fire! m "request")
    (say "    busy from now: " (path-text (fsm-path-to m "busy" #:start 'now)))
    (say "    state_reachable('idle', start='now'): "
         (py-bool (fsm-state-reachable? m "idle" #:start 'now)))))

(define (run-report)
  "RETURN: unspecified. Coverage, and an end outside the final states."
  (let ((m (fsm-from-string PROTOCOL #:name "protocol")))
    (for-each (lambda (event) (fsm-fire! m event))
              '("request" "grant" "release" "request" "grant"))
    (say "report returns " (number->string (fsm-report m)))))

(define (run-masks)
  "RETURN: unspecified. The law changing while the machine runs."
  (let ((m (fsm-from-string PROTOCOL)))
    (banner "'grant' disallowed in every state, since line 2")
    (fsm-disallow! m "grant" #:where 2)
    (fsm-fire! m "request" #:where 3)
    (say "    allowed now: " (string-join (fsm-allowed m) ", ") " -- can('grant'): "
         (py-bool (fsm-can? m "grant")))
    (fsm-fire! m "grant" #:where 4)
    (say "    path_to('busy'):               " (path-text (fsm-path-to m "busy")))
    (say "    path_to('busy', masked=False): "
         (path-text (fsm-path-to m "busy" #:masked? #f)))
    (say "    check(): " (number->string (fsm-check m)))
    (say "    check(masked=False): " (number->string (fsm-check m #:masked? #f)))
    (banner "allowed again; 'busy' forbidden while standing in it")
    (fsm-allow! m "grant" #:where 5)
    (fsm-fire! m "grant" #:where 6)
    (fsm-forbid! m "busy" #:where 7)
    (fsm-fire! m "release" #:where 8)
    (fsm-fire! m "request" #:where 9)
    (fsm-fire! m "grant" #:where 10)
    (banner "permitted: 'busy', and the model's own 'crashed'")
    (fsm-permit! m "busy" #:where 11)
    (fsm-permit! m "crashed" #:where 12)
    (let ((moved (fsm-fire! m "fault" #:where 13)))
      (say "    fault -> " (py-bool moved) " -- now in " (fsm-state m)))
    (banner "a phase: 'release' disallowed in 'busy' for a block")
    (fsm-reset! m)
    (fsm-fire! m "request") (fsm-fire! m "grant")
    (fsm-disallowed m "release" (lambda () (fsm-fire! m "release" #:where 20))
                    #:state "busy" #:where "phase")
    (fsm-fire! m "release" #:where 21)
    (fsm-disallow! m "cancel" #:where 22)
    (fsm-report m)
    (banner "refused: a word the model never names")
    (for-each (lambda (call) (fsm-error-said (call)))
              (list (lambda () (fsm-disallow! m "jump"))
                    (lambda () (fsm-forbid! m "limbo"))
                    (lambda () (fsm-allow! m "grant" #:state "nowhere"))))))

(hwut-runner-run
 (make-hwut-runner (command-line)
                   "hwut_fsm: a state machine as the test's model of the system"
                   `(("syntax"    . ,run-syntax)
                     ("refused"   . ,run-refused)
                     ("dfa"       . ,run-dfa)
                     ("nfa"       . ,run-nfa)
                     ("forbidden" . ,run-forbidden)
                     ("model"     . ,run-model)
                     ("report"    . ,run-report)
                     ("masks"     . ,run-masks))))
