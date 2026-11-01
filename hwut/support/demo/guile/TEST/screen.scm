#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; @hwut {
;;     title     = "Demo: a terminal program's screen, as a person sees it"
;;     tolerance { regions    = false
;;                 comment    = false
;;                 whitespace = false }
;;     choices {
;;         open   { features = ["terminal-screen", "screen-as-seen"] }
;;         scroll { features = ["terminal-screen", "screen-as-seen"] }
;;     }
;; }
;;
;; _____________________________________________________________________________
;; SUBJECT  the screen of 'viewer.scm', a full-screen file viewer, run in a
;;          terminal of 9 rows and 40 columns and driven by its keys.
;; REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
;;              as they fit, and a status line -- the keys flush left, the
;;              lines shown flush right; 'j' and the down key go one line
;;              further, 'k' one back.
;;
;; '(hwut vterm)' runs the viewer on a pseudo-terminal: the viewer cannot tell
;; it from a real one. The test PRESSES KEYS and is told what CHANGED: three
;; regions are declared -- title, body, status -- and after every key, once
;; the viewer has gone quiet, each region whose text changed is printed.
;;
;; THE SCREEN IS COMPARED AS A PERSON SEES IT: 'regions', 'comment' and
;; 'whitespace' are off in the header -- the file shown is a GOOD file of
;; hwut, whose '##! potpourri' and '## ...' lines are characters on this
;; screen, and the status line's blanks count. '../../python/TEST/screen.py'
;; says each at length.
;;
;; libvterm must be installed ('apt install libvterm0'); where it is not, the
;; test prints why and probes nothing -- its output differs from GOOD and the
;; reason stands in the difference.
;;
;; CHOICES  open    the viewer opened, then quit.
;;          scroll  down, down, 'j', then 'k': three lines on, one back.
;; _____________________________________________________________________________
(load "support-path.scm")
(use-modules (hwut vterm) (ice-9 exceptions))

(define HERE (dirname (canonicalize-path (current-filename))))
(define SAMPLE (string-append
                "## demo.scm race -- three workers\n"
                "start\n"
                "##! potpourri\n"
                "worker B done: 5 jobs\n"
                "worker A done: 3 jobs\n"
                "worker C done: 2 jobs\n"
                "####\n"
                "all joined\n"
                "## the order between the markers is\n"
                "## free; the lines are not.\n"))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stdout."
  (display (string-concatenate text-list))
  (newline))

(define (show name line-list)
  "RETURN: unspecified. Prints one region that changed, its rows as they
stand on the screen, from the first column."
  (say "-- " name)
  (for-each say line-list))

(define (view key-list)
  "RETURN: unspecified. Runs the viewer on the sample, presses 'key-list',
quits, and prints what changed after each step."
  (let ((path (string-append HERE "/TMP/race.txt")))
    (unless (file-exists? (dirname path)) (mkdir (dirname path)))
    (call-with-output-file path (lambda (port) (display SAMPLE port)))
    (call-with-terminal 9 40
      (lambda (terminal)
        (terminal-region! terminal "title"  0)
        (terminal-region! terminal "body"   1 #:row-n 7)
        (terminal-region! terminal "status" -1)
        (terminal-on-change! terminal show)
        (say "> viewer.scm race.txt")
        (terminal-run! terminal (list "guile" "--no-auto-compile"
                                      (string-append HERE "/viewer.scm") path))
        (let ((text (cell-attribute-text (screen-cell terminal 0 1))))
          (say "title bar: " (if (string-null? text) "plain" text)))
        (for-each (lambda (key)
                    (say "> " key)
                    (if (= (string-length key) 1)
                        (terminal-send! terminal key)
                        (terminal-press! terminal key)))
                  key-list)
        (terminal-send! terminal "q")
        (say "> q -- exit status " (number->string (terminal-wait terminal)))))))

(define CHOICE-LIST '(("open") ("scroll" "down" "down" "j" "k")))

(let* ((argv   (command-line))
       (choice (if (> (length argv) 1) (cadr argv) ""))
       (entry  (assoc choice CHOICE-LIST)))
  (unless entry
    (say "choices: " (string-join (map car CHOICE-LIST) ", "))
    (exit 1))
  (guard (e ((library-missing? e) (say (exception-message e)) (exit 1)))
    (view (cdr entry)))
  (say "<hwut-end>"))
