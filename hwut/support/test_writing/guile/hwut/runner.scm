;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: THE FRONT END OF A HWUT TEST APPLICATION -- the port of
;;;          'python/hwut_runner.py' (read '../python/README-hwut_runner.txt').
;;;
;;;     (hwut-runner-run
;;;       (make-hwut-runner (command-line) "my title"
;;;                         `(("plain"  . ,run-plain)
;;;                           ("tricky" . ,run-tricky))))
;;;
;;; The command line selects the mode:
;;;
;;;     app --hwut-info      print the info block; exit 0.
;;;     app <choice>         run one choice; its output on stdout and stderr,
;;;                          then '<hwut-end>'. '-' runs a choice-less app.
;;;     app --interactive    choices are started via stdin, one per line:
;;;                              run <choice> <sink-out> <sink-err>
;;;                              info
;;;                              quit | q | exit
;;;                          answered on the ORIGINAL stdout: 'done <choice>
;;;                          <status>', 'fail <choice> <reason>', 'info:
;;;                          <line>', and 'bye' at the session's end.
;;;     app                  the choice-less test; where the app has choices,
;;;                          refused, naming them (services E-189).
;;;
;;; THE CHOICE MAP IS AN ASSOCIATION LIST of name and thunk; a single thunk in
;;; its place is the choice-less test (Python's key 'None').
;;;
;;; A CHOICE ENDS by returning (status 0), by '(exit n)' (status n -- Guile's
;;; 'exit' throws 'quit', which the runner catches in interactive mode, so a
;;; choice ends and the session goes on), or by an uncaught exception
;;; (status 1, the backtrace in the error sink). Interactive mode runs the
;;; choices one after another IN THIS PROCESS, as Python's default scheme
;;; does: fd 1 and fd 2 are pointed at the two sinks, the ports flushed
;;; before they are pointed back.
;;;_____________________________________________________________________________
(define-module (hwut runner)
  #:use-module (srfi srfi-9)
  #:use-module (ice-9 rdelim)
  #:export (make-hwut-runner hwut-runner? hwut-runner-run
            levenshtein-distance levenshtein-best-match))

(define-record-type <hwut-runner>
  (%make-hwut-runner argv title choice-alist choice-less? sorted-choice-list
                     happy-list same? control)
  hwut-runner?
  (argv               runner-argv)
  (title              runner-title)
  (choice-alist       runner-alist)              ; ((#f . thunk)): choice-less
  (choice-less?       runner-choice-less?)
  (sorted-choice-list runner-sorted-choice-list)  ; (#f) for choice-less
  (happy-list         runner-happy-list)
  (same?              runner-same?)
  (control            runner-control set-runner-control!))

(define* (make-hwut-runner argv title choice-map #:key (happy '()) (same? #f))
  "RETURN: hwut-runner, ready for 'hwut-runner-run'.

'argv' is the command line ('(command-line)': the script's name first);
'title' the info block's title line; 'choice-map' an association list of
choice name (string) and thunk, or a single thunk for the choice-less test;
'happy' a string or a list of strings, the info block's 'HAPPY:' patterns;
'same?' #t puts 'SAME;' into the info block."
  (let ((less? (procedure? choice-map)))
    (when (null? choice-map)
      (error "make-hwut-runner: an empty choice map"))
    (%make-hwut-runner argv title
                       (if less? (list (cons #f choice-map)) choice-map) less?
                       (if less? '(#f) (sort (map car choice-map) string<?))
                       (if (string? happy) (list happy) happy)
                       same? #f)))

;;  ------------------------------------------------------------- dispatching
(define (hwut-runner-run runner)
  "RETURN: unspecified, where a choice ran or an interactive session ended;
the process exits (status 0 after '--hwut-info', 1 after a refused choice)
else. Dispatches on the first argument after the script's name."
  (utf-8-ports!)
  (let* ((argv   (runner-argv runner))
         (word   (if (< (length argv) 2) #f (cadr argv))))
    (cond
     ((member word '("-h" "--hi" "--hwut-info" "--sos" "--wtf")) (mode-hwut-info runner))
     ((equal? word "--interactive")                              (mode-interactive runner))
     ((not word)
      (if (not (runner-choice-less? runner))
          (mode-choice-missing runner)
          (mode-run-test runner #f)))
     ((choice-of-word runner word)
      => (lambda (choice) (mode-run-test runner (car choice))))
     ((runner-choice-less? runner)
      ;;  A CHOICE-LESS APPLICATION has no word to offer (ND4).
      (display (string-append "error: '" word "': this application has no "
                              "choices -- call it without one.\n"))
      (exit 1))
     (else (mode-choice-does-not-exist runner word)))))

(define (utf-8-ports!)
  "RETURN: unspecified. stdout and stderr write UTF-8, whatever the locale
says -- the GOOD files are UTF-8."
  (set-port-encoding! (current-output-port) "UTF-8")
  (set-port-encoding! (current-error-port) "UTF-8"))

(define (choice-of-word runner word)
  "RETURN: (choice), a one-element list holding the choice 'word' names --
the name itself, or #f for '-' in a choice-less application (ND4);
#f, where 'word' names no choice."
  (let ((alist (runner-alist runner)))
    (cond ((and (string? word) (not (runner-choice-less? runner)) (assoc word alist))
           (list word))
          ((and (runner-choice-less? runner) (equal? word "-")) (list #f))
          (else #f))))

(define (printable-choice-list runner)
  "RETURN: list of strings, the sorted choices; the choice-less one as '-'."
  (map (lambda (c) (or c "-")) (runner-sorted-choice-list runner)))

(define (mode-choice-missing runner)
  "RETURN: never; exits with status 1. The application has choices and the
command line names none (the menu is 'hwut.play's, services E-189)."
  (display (string-append "error: a choice is required: "
                          (string-join (printable-choice-list runner) ", ")
                          " -- name one, or let 'hwut.play' ask.\n"))
  (exit 1))

(define (mode-choice-does-not-exist runner word)
  "RETURN: never; exits with status 1. Names the unavailable choice, the
available ones and the closest by Levenshtein distance."
  (display (string-append "error: choice '" word "' not available.\n"))
  (display (string-append "error: available: "
                          (string-join (printable-choice-list runner) ", ") ".\n"))
  (let ((suggestion (levenshtein-best-match word (runner-sorted-choice-list runner))))
    (when suggestion
      (display (string-append "error: did you mean '" suggestion "'?\n"))))
  (exit 1))

(define (mode-run-test runner choice)
  "RETURN: unspecified. Normal mode: the choice's thunk runs with the
process's own stdout and stderr, then '<hwut-end>' is printed (R-70)."
  (run-choice runner choice)
  (display "<hwut-end>\n"))

(define (mode-hwut-info runner)
  "RETURN: never; exits with status 0 after printing the info block."
  (for-each (lambda (line) (display line) (newline)) (info-block-lines runner))
  (force-output)
  (exit 0))

(define (info-block-lines runner)
  "RETURN: list of strings, the info block: title (with its ';'), CHOICES,
HAPPY patterns, 'SAME;' where asked, and 'INTERACTIVE;' always."
  (let ((title (runner-title runner)))
    (append
     (list (if (string-suffix? ";" title) title (string-append title ";")))
     (if (not (runner-choice-less? runner))
         (list (string-append "CHOICES: "
                              (string-join (runner-sorted-choice-list runner) ", ")
                              ";"))
         '())
     (map (lambda (h) (string-append "HAPPY: " h ";")) (runner-happy-list runner))
     (if (runner-same? runner) '("SAME;") '())
     '("INTERACTIVE;"))))

(define (run-choice runner choice)
  "RETURN: unspecified, once the thunk of 'choice' (#f: the choice-less
test) has returned."
  ((cdr (assoc choice (runner-alist runner)))))

;;  ------------------------------------------------------- interactive mode
(define (mode-interactive runner)
  "RETURN: unspecified, once the session ends ('quit' or the end of stdin).

On entry the original stdout is duplicated onto a private control
descriptor (the UP channel); fd 1 and fd 2 are then pointed at a stray
sink, so output outside a running choice never reaches the protocol."
  (force-output (current-output-port))
  (force-output (current-error-port))
  (let ((control (fdes->outport (dup->fdes 1))))
    (setvbuf control 'line)
    (set-port-encoding! control "UTF-8")
    (set-runner-control! runner control))
  (let* ((stray-port (mkstemp (string-append (or (getenv "TMPDIR") "/tmp") "/hwut_stray_XXXXXX")))
         (stray-fd   (port->fdes stray-port)))
    (dup2 stray-fd 1)
    (dup2 stray-fd 2)
    (close-port stray-port))
  (let loop ()
    (let ((line (next-line)))
      (when (and line (interprete runner line))
        (loop))))
  (up runner "bye"))

(define (next-line)
  "RETURN: string, the next non-empty line of stdin, stripped;
#f, at the end of stdin."
  (let ((line (read-line (current-input-port))))
    (cond ((eof-object? line) #f)
          ((string-null? (string-trim-both line)) (next-line))
          (else (string-trim-both line)))))

(define (up runner message)
  "RETURN: unspecified; 'message' and a newline are written and flushed on
the UP channel."
  (let ((control (runner-control runner)))
    (display message control)
    (newline control)
    (force-output control)))

(define (interprete runner line)
  "RETURN: #t, the session goes on; #f, it ends ('quit', 'q', 'exit').
Interpretes one DOWN command and answers on the UP channel; never raises."
  (let ((field-list (string-tokenize line)))
    (cond
     ((and (= (length field-list) 1) (member (car field-list) '("quit" "q" "exit")))
      #f)
     ((equal? field-list '("info"))
      (for-each (lambda (l) (up runner (string-append "info: " l)))
                (info-block-lines runner))
      (up runner "done - 0")
      #t)
     ((and (= (length field-list) 4) (equal? (car field-list) "run"))
      (let* ((token  (list-ref field-list 1))
             (choice (find-choice runner token)))
        (if (not choice)
            (up runner (string-append "fail " token " unknown-choice"))
            (let ((status (run-into-sinks runner (car choice)
                                          (list-ref field-list 2)
                                          (list-ref field-list 3))))
              (up runner (string-append "done " token " " (number->string status))))))
      #t)
     (else
      (up runner "fail - bad-command")
      #t))))

(define (find-choice runner token)
  "RETURN: (choice), a one-element list of the choice 'token' names -- a
choice name, a decimal index into the sorted choice list, or '-' for the
choice-less test (then the element is #f); #f, where it names none."
  (let ((less?  (runner-choice-less? runner))
        (sorted (runner-sorted-choice-list runner)))
    (cond ((equal? token "-")                (if less? (list #f) #f))
          ((and (not less?) (assoc token (runner-alist runner))) (list token))
          ((and (not (string-null? token)) (string-every char-numeric? token))
           (let ((i (string->number token)))
             (and i (< i (length sorted)) (list (list-ref sorted i)))))
          (else #f))))

(define (run-into-sinks runner choice sink-out sink-err)
  "RETURN: exact integer, the choice's status: 0 where its thunk returned,
n where it called '(exit n)' (0 for '(exit)' or '(exit #t)', 1 for
'(exit #f)'), 1 where it raised -- its backtrace in the error sink.

fd 1 and fd 2 point at the two sink files while the choice runs; before
the return the ports are flushed, both sinks closed and fd 1 and fd 2
restored -- the 'done' barrier."
  (let ((out-fd  (open-fdes sink-out (logior O_WRONLY O_CREAT O_TRUNC) #o644))
        (err-fd  (open-fdes sink-err (logior O_WRONLY O_CREAT O_TRUNC) #o644)))
    (force-output (current-output-port))
    (force-output (current-error-port))
    (let ((saved-1 (dup->fdes 1))
          (saved-2 (dup->fdes 2)))
      (dup2 out-fd 1) (close-fdes out-fd)
      (dup2 err-fd 2) (close-fdes err-fd)
      (let ((status
             (catch 'quit
               (lambda ()
                 (with-throw-handler #t
                   (lambda ()
                     (run-choice runner choice)
                     (unless (getenv "HWUT_NO_TERMINAL")
                       (display "<hwut-end>\n"))
                     0)
                   (lambda (key . args)
                     (unless (eq? key 'quit)
                       (backtrace-of key args)))))
               (lambda (key . args)
                 (exit-status-of args)))))
        (force-output (current-output-port))
        (force-output (current-error-port))
        (dup2 saved-1 1) (close-fdes saved-1)
        (dup2 saved-2 2) (close-fdes saved-2)
        status))))

(define (backtrace-of key args)
  "RETURN: never; the exception is described in the error sink, with the
stack where it was raised, and turned into '(exit 1)' -- status 1."
  (let ((port (current-error-port)))
    (display "Traceback (Guile):\n" port)
    (display-backtrace (make-stack #t) port)
    (print-exception port #f key args)
    (force-output port)
    (throw 'quit 1)))

(define (exit-status-of args)
  "RETURN: exact integer, the status '(exit . args)' asks for: 0 for no
argument or #t, 1 for #f, the integer itself masked to a byte."
  (cond ((null? args)            0)
        ((eq? (car args) #t)     0)
        ((eq? (car args) #f)     1)
        ((integer? (car args))   (logand (car args) #xFF))
        (else                    1)))

;;  ---------------------------------------------------------- the suggestion
(define (levenshtein-best-match needle haystack)
  "RETURN: string, the element of 'haystack' (#f elements skipped) of least
Levenshtein distance to 'needle', the first of equals; #f, where 'needle' is
#f or 'haystack' holds no string."
  (cond ((not needle) #f)
        ((member needle haystack) needle)
        (else
         (let loop ((rest haystack) (best #f) (best-d #f))
           (cond ((null? rest) best)
                 ((not (car rest)) (loop (cdr rest) best best-d))
                 (else
                  (let ((d (levenshtein-distance needle (car rest))))
                    (if (or (not best-d) (< d best-d))
                        (loop (cdr rest) (car rest) d)
                        (loop (cdr rest) best best-d)))))))))

(define (levenshtein-distance a b)
  "RETURN: exact integer >= 0, the Levenshtein distance between the strings
'a' and 'b'."
  (let* ((a (string->list a))
         (b (string->list b)))
    (let loop ((rest a) (i 1) (prev (iota (+ (length b) 1))))
      (if (null? rest)
          (car (last-pair prev))
          (let ((ca (car rest)))
            (let row ((bs b) (p prev) (cur (list i)))
              (if (null? bs)
                  (loop (cdr rest) (+ i 1) (reverse cur))
                  (let* ((ins  (+ (car cur) 1))
                         (dele (+ (cadr p) 1))
                         (sub  (+ (car p) (if (char=? ca (car bs)) 0 1))))
                    (row (cdr bs) (cdr p) (cons (min ins dele sub) cur))))))))))
