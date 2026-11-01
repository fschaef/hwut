;; @hwut {
;;     title      = "A terminal's screen read by a test: libvterm through (system foreign)."
;;     choices {
;;         attributes { features = ["guile-vterm"] }
;;         colours    { features = ["guile-vterm"] }
;;         events     { features = ["guile-vterm"] }
;;         keys       { features = ["guile-vterm"] }
;;         missing    { features = ["guile-vterm"] }
;;         regions    { features = ["guile-vterm"] }
;;         screen     { features = ["guile-vterm"] }
;;         text       { features = ["guile-vterm"] }
;;         unnoticed  { features = ["guile-vterm"] }
;;     }
;;     interactive = true
;; }
;;
;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;; _____________________________________________________________________________
;;
;; PURPOSE: The Guile port of 'python/TEST/test-hwut_vterm.py', choice for
;;          choice, held against its GOOD files by '.link'. WANTS 'libvterm'
;;          (Debian: 'libvterm0'); where it is not found every choice but
;;          'missing' says so in one line. The two applications run on the
;;          pseudo-terminal are the Python test's own -- the system under
;;          test -- run by 'python3 -c'.
;;
;; 'missing' puts HWUT_LIBVTERM and the loaded library back on its way out:
;; an interactive session runs every choice in this one process, and the
;; choices after it want the library found.
;; _____________________________________________________________________________
(add-to-load-path (string-append (dirname (canonicalize-path (current-filename))) "/.."))
(use-modules (hwut runner) (hwut pytext) (hwut vterm) (ice-9 exceptions)
             (rnrs bytevectors))

(define ESC "\x1b")

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline."
  (display (string-concatenate text-list))
  (newline))

(define (cursor-text pair)
  "RETURN: string, the cursor pair as Python prints the tuple: '(1, 5)'."
  (py-repr pair))

(define (shown screen)
  "RETURN: unspecified. Every row that holds something, framed, then the
cursor."
  (let loop ((rows (screen-line-list screen)) (row 0))
    (when (pair? rows)
      (unless (string-null? (car rows))
        (say "    " (number->string row) " |" (car rows) "|"))
      (loop (cdr rows) (+ row 1))))
  (say "    cursor " (cursor-text (screen-cursor screen))))

(define (probe thunk)
  "RETURN: thunk, 'thunk' run on a library that is there; one line where it
is not."
  (lambda ()
    (guard (e ((library-missing? e) (say "NOT PROBED: " (exception-message e))))
      (thunk))))

(define (colour-text colour)
  "RETURN: string, a colour as Python prints it: '(255, 0, 0)' or 'None'."
  (if colour (py-repr colour) "None"))

(define (run-text)
  "RETURN: unspecified. plain bytes, UTF-8, a wide character, a wrapping line, a place off the screen."
  (call-with-screen 4 12
    (lambda (screen)
      (say "-- plain, then carriage return and line feed")
      (screen-feed! screen (string->utf8 "hello\r\nworld"))
      (shown screen)))
  (call-with-screen 4 12
    (lambda (screen)
      (say "-- UTF-8: two bytes, one cell; a wide character, two")
      (screen-feed! screen (string->utf8 "ä日x"))
      (shown screen)
      (do ((column 0 (+ column 1))) ((= column 4))
        (let ((cell (screen-cell screen 0 column)))
          (say "    column " (number->string column) ": "
               (py-ljust (py-str-repr (cell-text cell)) 6) " width "
               (number->string (cell-width cell)))))))
  (call-with-screen 3 5
    (lambda (screen)
      (say "-- seven characters on five columns: the line wraps")
      (screen-feed! screen (string->utf8 "abcdefg"))
      (shown screen)))
  (call-with-screen 2 4
    (lambda (screen)
      (say "-- a str is sent as UTF-8; the bytes taken are counted")
      (say "    taken: " (number->string (screen-feed! screen "aä")))
      (say "-- a place off the screen")
      (guard (e ((index-error? e) (say "    IndexError: " (exception-message e))))
        (screen-cell screen 2 0)))))

(define (run-screen)
  "RETURN: unspecified. the cursor addressed, a line erased, the screen cleared."
  (call-with-screen 5 20
    (lambda (screen)
      (say "-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'")
      (screen-feed! screen (string->utf8 "first line\r\nsecond line\r\nthird line"))
      (screen-feed! screen (string-append ESC "[2;4H" "X"))
      (shown screen)
      (say "-- erase to the end of that line")
      (screen-feed! screen (string-append ESC "[K"))
      (shown screen)
      (say "-- clear the screen, home, one word")
      (screen-feed! screen (string-append ESC "[2J" ESC "[H" "clean"))
      (shown screen))))

(define (run-attributes)
  "RETURN: unspecified. each attribute by its SGR code, then three at once, then the double underline."
  (call-with-screen 3 20
    (lambda (screen)
      (for-each (lambda (entry)
                  (screen-feed! screen (string-append ESC "[" (cdr entry) "m"
                                                      (substring (car entry) 0 1) ESC "[0m")))
                ATTRIBUTE-SGR-DB)
      (say "-- one cell per attribute, set by its own code")
      (let loop ((names (map car ATTRIBUTE-SGR-DB)) (column 0))
        (when (pair? names)
          (let* ((cell (screen-cell screen 0 column))
                 (said (if (string=? (car names) "conceal")
                           "conceal, or (none) on libvterm 0.1"
                           (let ((t (cell-attribute-text cell)))
                             (if (string-null? t) "(none)" t)))))
            (say "    " (py-str-repr (cell-text cell)) "  " said))
          (loop (cdr names) (+ column 1))))
      (say "-- bold, underline and reverse at once; then reset")
      (screen-feed! screen (string-append "\r\n" ESC "[1;4;7mA" ESC "[0mB"))
      (for-each (lambda (column)
                  (let* ((cell (screen-cell screen 1 column)) (t (cell-attribute-text cell)))
                    (say "    " (py-str-repr (cell-text cell)) "  " (if (string-null? t) "(none)" t))))
                '(0 1))
      (say "-- double underline (SGR 21) is underlined")
      (screen-feed! screen (string-append ESC "[21mD"))
      (say "    " (py-str-repr "D") "  " (cell-attribute-text (screen-cell screen 1 2))))))

(define (run-colours)
  "RETURN: unspecified. the default, an indexed, a palette and a direct colour."
  (call-with-screen 2 20
    (lambda (screen)
      (screen-feed! screen (string-append "d" ESC "[31mr" ESC "[0m" ESC "[38;5;196mp" ESC "[0m"
                                          ESC "[38;2;10;20;30mt" ESC "[0m"))
      (screen-feed! screen (string-append ESC "[48;2;1;2;3mb" ESC "[0m"))
      (let loop ((what-list '("default" "indexed 31" "palette 196" "direct 10;20;30"
                              "background 1;2;3"))
                 (column 0))
        (when (pair? what-list)
          (let* ((cell (screen-cell screen 0 column))
                 (what (car what-list))
                 ;;  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE:
                 ;;  that one is a colour and mostly red is the claim.
                 (said (if (string=? what "indexed 31")
                           (let ((rgb (cell-foreground cell)))
                             (string-append "fg mostly red: "
                                            (py-bool (> (vector-ref rgb 0)
                                                        (* 2 (max (vector-ref rgb 1)
                                                                  (vector-ref rgb 2)))))))
                           (string-append "fg " (colour-text (cell-foreground cell))
                                          "  bg " (colour-text (cell-background cell))))))
            (say "    " (py-ljust what 18) " " (py-str-repr (cell-text cell)) "  " said))
          (loop (cdr what-list) (+ column 1)))))))

;;  THE APPLICATION UNDER OBSERVATION -- the Python test's own: it says what
;;  it sees, asks the terminal where the cursor is, then names every key
;;  until 'q'.
(define SEEING-APP "
import os, sys, tty, termios
print(\"streams are terminals: %s %s %s\"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open(\"/dev/tty\", os.O_RDWR)); print(\"controlling terminal: yes\")
except OSError: print(\"controlling terminal: no\")
print(\"size: %d columns, %d rows\" % tuple(os.get_terminal_size()))
print(\"TERM=%s COLUMNS=%s\" % (os.environ.get(\"TERM\"), os.environ.get(\"COLUMNS\")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write(\"\\x1b[6;9H\\x1b[6n\"); sys.stdout.flush()
reply = b\"\"
while not reply.endswith(b\"R\"): reply += os.read(0, 1)
sys.stdout.write(\"\\r\\x1b[7;1Hthe terminal answered: %r\" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write(\"\\x1b[9;1H\\x1b[Kread: %r\" % key); sys.stdout.flush()
    if key == b\"q\": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print(\"\\r\\nleaving\"); sys.exit(3)
")

;;  AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body,
;;  'f' rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
(define DRAWING-APP "
import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, \"q=quit\"
def draw():
    out = \"\\x1b[2J\\x1b[1;1H\\x1b[7m the head \\x1b[0m\"
    out += \"\\x1b[3;1Hcount: %d\\x1b[4;1H(press n)\" % count
    out += \"\\x1b[8;1H%s\" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b\"n\": count += 1
    elif key == b\"f\": foot = \"q=quit  f=pressed\"
    elif key == b\"q\": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
")

(define (run-unnoticed)
  "RETURN: unspecified. what the application sees of its terminal, and its exit status."
  (setenv "COLUMNS" "300")
  (call-with-terminal 10 44
    (lambda (terminal)
      (say "-- still running after its first screen: "
           (py-bool (terminal-run! terminal (list "python3" "-c" SEEING-APP))))
      (shown terminal)
      (terminal-send! terminal "q")
      (say "-- after 'q': exit status " (py-str (terminal-wait terminal)))
      (shown terminal))))

(define (run-keys)
  "RETURN: unspecified. what the application reads for each key pressed."
  (call-with-terminal 10 44
    (lambda (terminal)
      (let ((pressed "(start)"))
        (terminal-region! terminal "read" 8)
        (terminal-on-change! terminal (lambda (name line-list)
                                        (say "    " (py-ljust pressed 22) " " (car line-list))))
        (terminal-run! terminal (list "python3" "-c" SEEING-APP))
        (for-each (lambda (entry)
                    (set! pressed (string-join (append (cdr entry) (list (car entry))) " "))
                    (terminal-press! terminal (car entry) #:modifiers (cdr entry)))
                  '(("up") ("enter") ("tab") ("escape") ("f5") ("delete")
                    ("c" "ctrl") ("x" "alt") ("up" "shift")))
        (set! pressed "send 'ä'")
        (terminal-send! terminal "ä")
        (set! pressed "send 'q'")
        (terminal-send! terminal "q")
        (terminal-wait terminal)))))

(define (run-regions)
  "RETURN: unspecified. only the region whose text changed is told, once per pause."
  ;;  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
  ;;  ONE report on a loaded machine too.
  (call-with-terminal 8 30
    (lambda (terminal)
      (terminal-region! terminal "head" 0)
      (terminal-region! terminal "body" 2 #:row-n 2)
      (terminal-region! terminal "foot" -1)
      (terminal-on-change! terminal (lambda (name line-list)
                                      (say "    changed  " (py-ljust name 5) " "
                                           (py-list-repr line-list))))
      (for-each (lambda (entry)
                  (say "-- " (car entry))
                  ((cdr entry)))
                `(("run"                        . ,(lambda () (terminal-run! terminal
                                                                             (list "python3" "-c" DRAWING-APP))))
                  ("'n'"                        . ,(lambda () (terminal-send! terminal "n")))
                  ("'n'"                        . ,(lambda () (terminal-send! terminal "n")))
                  ("'r': a redraw, nothing new" . ,(lambda () (terminal-send! terminal "r")))
                  ("'f'"                        . ,(lambda () (terminal-send! terminal "f")))
                  ("'nnn', typed at once"       . ,(lambda () (terminal-send! terminal "nnn")))
                  ("'q'"                        . ,(lambda () (terminal-send! terminal "q")))))
      (let ((status (terminal-wait terminal)))
        (say "-- exit status " (py-str status) "; a region asked by name: "
             (py-list-repr (terminal-region-text terminal "body"))))
      (guard (e ((key-error? e) (say "-- no such region: KeyError " (exception-message e))))
        (terminal-region-text terminal "nosuch")))
    #:settle-s 0.3))

(define (run-events)
  "RETURN: unspecified. the raw events of bytes fed by the test, and the answers waiting."
  (call-with-terminal 4 20
    (lambda (terminal)
      (terminal-on-event! terminal (lambda (event) (say "    " (event->string event))))
      (for-each (lambda (entry)
                  (say "-- fed: " (car entry))
                  (screen-feed! terminal (cdr entry)))
                `(("'ab'"                                      . "ab")
                  ("a line feed and 'c'"                       . "\r\nc")
                  ("the cursor to row 4, hidden"               . ,(string-append ESC "[4;1H" ESC "[?25l"))
                  ("the alternate screen"                      . ,(string-append ESC "[?1049h"))
                  ("the bell"                                  . "\a")
                  ("nothing that draws: a reset of attributes" . ,(string-append ESC "[0m"))))
      (say "-- asked where the cursor is, nobody running: the answer waits")
      (screen-feed! terminal (string-append ESC "[2;5H" ESC "[6n"))
      (say "    answer() = " (py-bytes-repr (terminal-answer! terminal)))
      (say "-- a key pressed with nobody running")
      (terminal-press! terminal "f1" #:react-s 0)
      (say "    answer() = " (py-bytes-repr (terminal-answer! terminal))))))

(define (run-missing)
  "RETURN: unspecified. '&library-missing', by name, with the hint how to install."
  (let ((before (getenv LIBRARY-VARIABLE)))
    (dynamic-wind
      (lambda ()
        (setenv LIBRARY-VARIABLE "/nowhere/libvterm.so")
        (vterm-library-forget!))
      (lambda ()
        (guard (e ((library-missing? e)
                   ;;  THE SYSTEM'S OWN WORDS for the failed load are left
                   ;;  out; what this module says -- the line, and the way
                   ;;  to install -- stands.
                   (let* ((line-list (string-split (exception-message e) #\newline))
                          (first     (car line-list))
                          (cut       (string-contains first " -- ")))
                     (say "LibraryMissing: " (if cut (substring first 0 cut) first))
                     (for-each say (cdr line-list)))))
          (make-screen)
          (say "a Screen stands on a library that is not there")))
      (lambda ()
        (if before (setenv LIBRARY-VARIABLE before) (unsetenv LIBRARY-VARIABLE))
        (vterm-library-forget!)))))

(hwut-runner-run
 (make-hwut-runner (command-line)
                   "A terminal's screen read by a test: libvterm through (system foreign)."
                   `(("text"       . ,(probe run-text))
                     ("screen"     . ,(probe run-screen))
                     ("attributes" . ,(probe run-attributes))
                     ("colours"    . ,(probe run-colours))
                     ("unnoticed"  . ,(probe run-unnoticed))
                     ("keys"       . ,(probe run-keys))
                     ("regions"    . ,(probe run-regions))
                     ("events"     . ,(probe run-events))
                     ("missing"    . ,run-missing))))
