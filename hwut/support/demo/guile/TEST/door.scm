#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; @hwut {
;;     title   = "Demo: a door's state machine, watched by a pype"
;;     pype    = "door.pype"
;;     choices {
;;         kept   { features = ["demo-guile", "demo-guile+cover-fsm-law-kept"] }
;;         broken { features = ["demo-guile", "demo-guile+cover-fsm-law-broken"] }
;;     }
;; }
;;
;; _____________________________________________________________________________
;; A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
;; may do.
;;
;; The application prints its log as it happens: noise, and a line 'door:
;; <event>' for each thing the door does. It prints no '<hwut-end>': the
;; header names 'door.pype', which stands between it and the comparison and
;; closes the stream at '<eof>'.
;;
;; 'door.pype' is a pype -- hwut's, in Python, whatever the application's
;; language: it parses the log and fires every event into a state machine
;; ('hwut_fsm'):
;;
;;     closed ---( open )---> open ---( close )---> closed
;;     closed ---( lock )---> locked ---( unlock )---> closed
;;     open   ---( slam )---> jammed          # forbidden
;;
;; kept     the door does what the model allows; the report shows which
;;          transitions were taken and which not, and 'ended in closed'.
;; broken   the controller locks an open door, slams it into a jam and
;;          tries to unlock it: each surprise is ONE 'BREACH' line, and the
;;          end outside the final states one more. The GOOD file holds them.
;;
;; Both choices pass on every run: what they print does not depend on time.
;; _____________________________________________________________________________

(define STORY-LIST
  '(("kept"   "open" "close" "lock" "unlock" "open" "close")
    ("broken" "open" "lock" "slam" "unlock")))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stdout."
  (display (string-concatenate text-list))
  (newline))

(define (main choice)
  "RETURN: exact integer, 0 -- the log of the door for 'choice', printed."
  (say "controller 2.1 up")
  (let loop ((event-list (assoc-ref STORY-LIST choice)) (number 1))
    (when (pair? event-list)
      (say "tick " (number->string number) ": sensors read")
      (say "door: " (car event-list))
      (loop (cdr event-list) (+ number 1))))
  (say "controller down")
  0)

(let ((argv (command-line)))
  (unless (and (= (length argv) 2) (assoc (cadr argv) STORY-LIST))
    (say "error: a choice is required: " (string-join (sort (map car STORY-LIST) string<?) ", "))
    (exit 1))
  (exit (main (cadr argv))))
