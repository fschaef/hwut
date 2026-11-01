#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; _____________________________________________________________________________
;; A TERMINAL FILE VIEWER -- the program 'screen.scm' tests; no test itself.
;;
;;     guile --no-auto-compile viewer.scm <file>
;;
;; Full screen, on the terminal's alternate screen: a title bar (reverse
;; video), as many lines of the file as fit, and a status line: the keys
;; flush left, the lines shown flush right. Keys: 'j' or down one line
;; further, 'k' or up one line back, 'q' quits.
;;
;; Guile has no termios and no window size: both are libc's, through
;; '(system foreign)' -- 'tcgetattr', 'cfmakeraw', 'tcsetattr' (raw mode, as
;; Python's 'tty.setraw'), 'ioctl TIOCGWINSZ' (Python's
;; 'os.get_terminal_size') and 'read' (a key as the terminal sent it, as
;; Python's 'os.read').
;; _____________________________________________________________________________
(use-modules (system foreign) (rnrs bytevectors) (ice-9 rdelim))

(define (libc name return-type argument-types)
  "RETURN: procedure, the C library's function 'name'."
  (pointer->procedure return-type (dynamic-func name (dynamic-link)) argument-types))

(define %tcgetattr (libc "tcgetattr" int  (list int '*)))
(define %tcsetattr (libc "tcsetattr" int  (list int int '*)))
(define %cfmakeraw (libc "cfmakeraw" void (list '*)))
(define %ioctl     (libc "ioctl"     int  (list int unsigned-long '*)))
(define %read      (libc "read"      long (list int '* size_t)))

(define TCSAFLUSH   2)
(define TCSADRAIN   1)
(define TIOCGWINSZ  #x5413)
(define TERMIOS-N   128)                  ; room beyond any libc's 'struct termios'

(define (terminal-size fd)
  "RETURN: (columns . rows), the size of the terminal 'fd'."
  (let ((box (make-bytevector 8 0)))
    (%ioctl fd TIOCGWINSZ (bytevector->pointer box))
    (cons (bytevector-u16-native-ref box 2) (bytevector-u16-native-ref box 0))))

(define (read-key fd)
  "RETURN: bytevector, what one read of up to 8 bytes from 'fd' delivered."
  (let* ((box (make-bytevector 8 0))
         (n   (%read fd (bytevector->pointer box) 8)))
    (let ((key (make-bytevector (max n 0))))
      (bytevector-copy! box 0 key 0 (max n 0))
      key)))

(define (write-out text)
  "RETURN: unspecified. 'text' on stdout, as it stands."
  (display text))

(define (draw name line-list top row-n column-n)
  "RETURN: unspecified. Draws the whole screen with the file's line 'top'
first."
  (let* ((body-n (- row-n 2))
         (shown  (list-head (list-tail line-list top) (min body-n (- (length line-list) top))))
         (title  (string-pad-right (string-append " " name) column-n))
         (where  (string-append "lines " (number->string (+ top 1)) "-"
                                (number->string (+ top (length shown))) " of "
                                (number->string (length line-list))))
         (keys   "j k q"))
    (write-out "\x1b[H\x1b[2J")
    (write-out (string-append "\x1b[7m" title "\x1b[0m\r\n"))
    (for-each (lambda (line)
                (write-out (string-append (if (> (string-length line) column-n)
                                              (substring line 0 column-n)
                                              line)
                                          "\r\n")))
              shown)
    (do ((i (- body-n (length shown)) (- i 1))) ((<= i 0)) (write-out "\r\n"))
    (write-out (string-append "\x1b[" (number->string row-n) ";1H" keys
                              (string-pad where (max (string-length where)
                                                     (- column-n 1 (string-length keys))))))
    (force-output)))

(define (main path)
  "RETURN: exact integer, 0 once 'q' was pressed."
  (let* ((line-list (call-with-input-file path
                      (lambda (port)
                        (let loop ((result '()))
                          (let ((line (read-line port)))
                            (if (eof-object? line) (reverse result) (loop (cons line result))))))))
         (size      (terminal-size 1))
         (column-n  (car size))
         (row-n     (cdr size))
         (last-top  (max 0 (- (length line-list) (- row-n 2))))
         (saved     (make-bytevector TERMIOS-N 0))
         (raw       (make-bytevector TERMIOS-N 0)))
    (%tcgetattr 0 (bytevector->pointer saved))
    (bytevector-copy! saved 0 raw 0 TERMIOS-N)
    (%cfmakeraw (bytevector->pointer raw))
    (%tcsetattr 0 TCSAFLUSH (bytevector->pointer raw))
    (write-out "\x1b[?1049h")
    (dynamic-wind
      (lambda () #f)
      (lambda ()
        (let loop ((top 0))
          (draw (basename path) line-list top row-n column-n)
          (let ((key (read-key 0)))
            (cond ((or (equal? key #vu8(113)) (= 0 (bytevector-length key))) #t)          ; 'q'
                  ((member key (list #vu8(106) #vu8(27 91 66))) (loop (min (+ top 1) last-top)))  ; 'j', down
                  ((member key (list #vu8(107) #vu8(27 91 65))) (loop (max (- top 1) 0)))         ; 'k', up
                  (else (loop top))))))
      (lambda ()
        (write-out "\x1b[?1049l")
        (force-output)
        (%tcsetattr 0 TCSADRAIN (bytevector->pointer saved))))
    0))

(exit (main (cadr (command-line))))
