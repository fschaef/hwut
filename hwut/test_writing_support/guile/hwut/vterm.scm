;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
;;;          'python/hwut_vterm.py' (read '../python/README-hwut_vterm.txt'):
;;;          'libvterm' through Guile's foreign function interface,
;;;          '(system foreign)' -- no binding, no header, no compiler.
;;;
;;;     (call-with-screen 24 80
;;;       (lambda (screen)
;;;         (screen-feed! screen "\x1b[1mbold\x1b[0m plain")
;;;         (screen-line screen 0)                    ; "bold plain"
;;;         (cell-bold? (screen-cell screen 0 0))      ; #t
;;;         (screen-cursor screen)))                  ; (0 . 10)
;;;
;;; THE LIBRARY IS FOUND, NOT SHIPPED: 'libvterm.so.0' as the system knows it
;;;     (Debian: 'libvterm0'), or the file HWUT_LIBVTERM names; where neither
;;;     loads, 'make-screen' raises '&library-missing', whose message says how
;;;     to install it. 'guile hwut/vterm.scm' asks the same by hand.
;;;
;;; THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED -- as the Python binding does:
;;;     a scratch terminal is fed one attribute at a time and the bit or the
;;;     bytes that changed are where that attribute stands.
;;;
;;; ONE RECORD, TWO ROLES: Python's 'Terminal(Screen)' is a screen that an
;;;     application runs in. Here a terminal IS a screen record whose
;;;     terminal part is filled: every 'screen-' procedure takes either, and
;;;     'screen-feed!' on a terminal also flushes the damage and hands the
;;;     terminal's answer to the application -- Python's override.
;;;
;;; THE PSEUDO-TERMINAL: 'openpty' from the C library by the FFI (the size
;;;     given there, Python's TIOCSWINSZ); the child by 'primitive-fork':
;;;     'setsid', then the slave OPENED by its name -- a session leader that
;;;     opens a terminal makes it its controlling one, Python's TIOCSCTTY --
;;;     dup'ed to 0, 1, 2, every other descriptor closed, the environment
;;;     set, 'execlp'. 'read' and 'write' on the master are libc's too.
;;;
;;; PYTHON'S VALUES: a tuple of two is a pair -- the cursor (row . column) --
;;;     a colour a vector #(red green blue), None is #f, bytes a bytevector.
;;;     Python's exceptions are exception types of the same names:
;;;     '&library-missing', '&index-error', '&key-error' (message: the key's
;;;     repr, "'nosuch'"), '&timeout-error', '&runtime-error'.
;;;_____________________________________________________________________________
(define-module (hwut vterm)
  #:use-module (srfi srfi-1)
  #:use-module (srfi srfi-9)
  #:use-module (rnrs bytevectors)
  #:use-module (system foreign)
  #:use-module (ice-9 exceptions)
  #:use-module (hwut pytext)
  #:export (LIBRARY-VARIABLE ATTRIBUTE-SGR-DB KEY-DB MODIFIER-DB
            &library-missing library-missing?
            &index-error index-error? &key-error key-error?
            &timeout-error timeout-error? &runtime-error runtime-error?
            vterm-detection-text vterm-library-forget!
            make-screen screen? screen-close! call-with-screen
            screen-rows screen-columns
            screen-feed! screen-cursor screen-cell screen-line screen-line-list
            cell? cell-text cell-width cell-bold? cell-italic? cell-underline?
            cell-blink? cell-reverse? cell-conceal? cell-strike?
            cell-foreground cell-background cell-attribute cell-attribute-text
            event? event-kind event-row event-column event-row-end event-column-end
            event-name event-value event->string
            make-terminal terminal? call-with-terminal terminal-close!
            terminal-on-event! terminal-on-change! terminal-region! terminal-region-text
            terminal-report! terminal-answer! terminal-send! terminal-press!
            terminal-run! terminal-pump! terminal-expect terminal-wait))

;;  ----------------------------------------------------------- the constants
(define LIBRARY-VARIABLE "HWUT_LIBVTERM")
(define LIBRARY-NAME-LIST '("libvterm.so.0" "libvterm.so" "libvterm.0.dylib" "libvterm.dylib"))

(define CHARS-PER-CELL-N 6)
(define CHARS-BYTE-N     (* 4 CHARS-PER-CELL-N))
(define CELL-BYTE-N      128)                 ; room beyond any version's cell

;;  THE ATTRIBUTES A CELL IS ASKED FOR, each with the SGR code that sets it.
(define ATTRIBUTE-SGR-DB
  '(("bold" . "1") ("italic" . "3") ("underline" . "4") ("blink" . "5")
    ("reverse" . "7") ("conceal" . "8") ("strike" . "9")))

(define INSTALL-HINT
  (string-join
   (list "HINT: install the library, or name its file:"
         "    Debian, Ubuntu   apt install libvterm0"
         "    Fedora           dnf install libvterm"
         "    Arch             pacman -S libvterm"
         "    macOS            brew install libvterm"
         (string-append "    elsewhere        export " LIBRARY-VARIABLE "=<path>/libvterm.so")
         "    or work inside   hwut.dev.podman.enter   (the image holds it)")
   "\n"))

(define DAMAGE-MERGE-ROW 1)

(define PROPERTY-DB
  '((1 "cursor-visible" . #t) (2 "cursor-blink" . #t) (3 "alternate-screen" . #t)
    (4 "title" . #f) (5 "icon-name" . #f) (6 "reverse-video" . #t)
    (7 "cursor-shape" . #t) (8 "mouse" . #t) (9 "focus-report" . #t)))

(define KEY-DB
  (append '(("enter" . 1) ("tab" . 2) ("backspace" . 3) ("escape" . 4)
            ("up" . 5) ("down" . 6) ("left" . 7) ("right" . 8)
            ("insert" . 9) ("delete" . 10) ("home" . 11) ("end" . 12)
            ("pageup" . 13) ("pagedown" . 14))
          (map (lambda (n) (cons (string-append "f" (number->string n)) (+ 256 n)))
               (iota 12 1))))
(define MODIFIER-DB '(("shift" . 1) ("alt" . 2) ("ctrl" . 4)))

;;  ---------------------------------------------------------- the exceptions
(define-exception-type &library-missing &error make-library-missing-condition library-missing?)
(define-exception-type &index-error     &error make-index-error-condition     index-error?)
(define-exception-type &key-error       &error make-key-error-condition       key-error?)
(define-exception-type &timeout-error   &error make-timeout-error-condition   timeout-error?)
(define-exception-type &runtime-error   &error make-runtime-error-condition   runtime-error?)

(define (raise-with make-condition message)
  "RETURN: never; raises the condition 'make-condition' makes, with 'message'."
  (raise-exception (make-exception (make-condition) (make-exception-with-message message))))

;;  ------------------------------------------------------------- the library
(define *library* #f)       ; ((name . handle) . procedure-alist), once
(define *layout*  #f)       ; the measured layout, once
(define *libc*    #f)       ; libc's procedures for the pseudo-terminal, once

(define (vterm-library-forget!)
  "RETURN: unspecified. The loaded library and its measured layout are
forgotten; the next screen loads it again -- under the name HWUT_LIBVTERM
gives NOW (the 'missing' choice's need)."
  (set! *library* #f)
  (set! *layout* #f))

(define FUNCTION-LIST
  ;;  name                               result  arguments
  `(("vterm_new"                         *       (,int ,int))
    ("vterm_free"                        ,void   (*))
    ("vterm_set_utf8"                    ,void   (* ,int))
    ("vterm_input_write"                 ,size_t (* * ,size_t))
    ("vterm_obtain_screen"               *       (*))
    ("vterm_obtain_state"                *       (*))
    ("vterm_screen_reset"                ,void   (* ,int))
    ("vterm_screen_enable_altscreen"     ,void   (* ,int))
    ("vterm_screen_get_cell"             ,int    (* (,int ,int) *))
    ("vterm_state_get_cursorpos"         ,void   (* *))
    ("vterm_output_set_callback"         ,void   (* * *))
    ("vterm_keyboard_unichar"            ,void   (* ,uint32 ,int))
    ("vterm_keyboard_key"                ,void   (* ,int ,int))
    ("vterm_screen_set_callbacks"        ,void   (* * *))
    ("vterm_screen_set_damage_merge"     ,void   (* ,int))
    ("vterm_screen_flush_damage"         ,void   (*))))

(define (library)
  "RETURN: alist, libvterm's procedures by C name -- the library loaded once
and every function declared; the key 'name is the file it was loaded as;
'vterm_screen_convert_color_to_rgb' only where the library has it (0.2 on).
Raises '&library-missing' where no such library loads."
  (or *library*
      (let* ((given  (getenv LIBRARY-VARIABLE))
             (loaded (if (and given (not (string-null? given)))
                         (catch #t
                           (lambda () (cons given (dynamic-link given)))
                           (lambda (key . args)
                             (raise-with make-library-missing-condition
                                         (string-append "libvterm cannot be loaded from '" given
                                                        "' -- " (error-text key args) "\n"
                                                        INSTALL-HINT))))
                         (or (any (lambda (name)
                                    (catch #t (lambda () (cons name (dynamic-link name)))
                                      (lambda _ #f)))
                                  LIBRARY-NAME-LIST)
                             (raise-with make-library-missing-condition
                                         (string-append "libvterm is not installed, and '"
                                                        LIBRARY-VARIABLE "' names no file\n"
                                                        INSTALL-HINT)))))
             (handle (cdr loaded))
             (alist  (map (lambda (entry)
                            (cons (car entry)
                                  (pointer->procedure (cadr entry)
                                                      (dynamic-func (car entry) handle)
                                                      (caddr entry))))
                          FUNCTION-LIST))
             (convert (catch #t
                        (lambda ()
                          (list (cons "vterm_screen_convert_color_to_rgb"
                                      (pointer->procedure
                                       void (dynamic-func "vterm_screen_convert_color_to_rgb" handle)
                                       '(* *)))))
                        (lambda _ '()))))
        (set! *library* (cons (cons 'name (car loaded)) (append alist convert)))
        *library*)))

(define (error-text key args)
  "RETURN: string, what the system said for the error 'key' with 'args'."
  (if (and (= (length args) 4) (string? (cadr args)))
      (apply format #f (cadr args) (or (caddr args) '()))
      (object->string (cons key args))))

(define (lib name)
  "RETURN: procedure, libvterm's function 'name'; #f where the library has
none of that name."
  (assoc-ref (library) name))

(define (vterm-detection-text)
  "RETURN: string, 'libvterm found: <name>', where the library loads; the
message of '&library-missing' -- what is wrong and how to install it -- else."
  (guard (e ((library-missing? e) (exception-message e)))
    (string-append "libvterm found: " (assq-ref (library) 'name))))

;;  ------------------------------------------------------------------ cells
(define-record-type <cell>
  (make-cell text width bold? italic? underline? blink? reverse? conceal? strike?
             foreground background)
  cell?
  (text       cell-text)
  (width      cell-width)
  (bold?      cell-bold?)
  (italic?    cell-italic?)
  (underline? cell-underline?)
  (blink?     cell-blink?)
  (reverse?   cell-reverse?)
  (conceal?   cell-conceal?)
  (strike?    cell-strike?)
  (foreground cell-foreground)                 ; #(red green blue), or #f: default
  (background cell-background))

(define (cell-attribute cell name)
  "RETURN: #t where the attribute 'name' (a key of ATTRIBUTE-SGR-DB) is set
on 'cell'; #f else."
  ((assoc-ref `(("bold" . ,cell-bold?) ("italic" . ,cell-italic?)
                ("underline" . ,cell-underline?) ("blink" . ,cell-blink?)
                ("reverse" . ,cell-reverse?) ("conceal" . ,cell-conceal?)
                ("strike" . ,cell-strike?))
              name)
   cell))

(define (cell-attribute-text cell)
  "RETURN: string, the attributes set on 'cell', by name, in the order of
ATTRIBUTE-SGR-DB, blank-separated ('bold reverse'); '' where none is set."
  (string-join (filter (lambda (name) (cell-attribute cell name)) (map car ATTRIBUTE-SGR-DB))
               " "))

;;  ------------------------------------------------------------------ events
(define-record-type <event>
  (make-event kind row column row-end column-end name value)
  event?
  (kind       event-kind)            ; "damage", "cursor", "property", "bell"
  (row        event-row)
  (column     event-column)
  (row-end    event-row-end)
  (column-end event-column-end)
  (name       event-name)
  (value      event-value))

(define (event->string event)
  "RETURN: string, 'event' on one line, as the Python test prints it."
  (let ((n number->string))
    (cond
     ((string=? (event-kind event) "damage")
      (string-append "damage    rows " (n (event-row event)) ".." (n (event-row-end event))
                     "  columns " (n (event-column event)) ".." (n (event-column-end event))))
     ((string=? (event-kind event) "cursor")
      (string-append "cursor    (" (n (event-row event)) ", " (n (event-column event)) ")"
                     (if (event-value event) "" "  hidden")))
     ((string=? (event-kind event) "property")
      (string-append "property  " (event-name event) " = "
                     (if (event-value event) (n (event-value event)) "None")))
     (else (event-kind event)))))

(define-record-type <layout>
  (make-layout mask-db foreground-i background-i convert? default-fg default-bg)
  layout?
  (mask-db      layout-mask-db)         ; name -> (byte offset . bit mask)
  (foreground-i layout-foreground-i)
  (background-i layout-background-i)
  (convert?     layout-convert?)
  (default-fg   layout-default-fg)
  (default-bg   layout-default-bg))

;;  ---------------------------------------------------------------- screens
;;  'part' is #f for a plain screen, the terminal part for a terminal.
(define-record-type <screen>
  (%make-screen rows columns terminal screen state part)
  screen?
  (rows     screen-rows)
  (columns  screen-columns)
  (terminal screen-vt     set-screen-vt!)
  (screen   screen-handle set-screen-handle!)
  (state    screen-state  set-screen-state!)
  (part     screen-part))

(define-record-type <part>
  (%make-part settle-s event-list change-list region-list told-list answer
              master pid status ended? keep)
  part?
  (settle-s    part-settle-s)
  (event-list  part-event-list  set-part-event-list!)
  (change-list part-change-list set-part-change-list!)
  (region-list part-region-list set-part-region-list!)  ; ((name row row-n col col-n) ...)
  (told-list   part-told-list   set-part-told-list!)    ; ((name . lines) ...)
  (answer      part-answer      set-part-answer!)       ; list of bytevectors, newest first
  (master      part-master      set-part-master!)
  (pid         part-pid         set-part-pid!)
  (status      part-status      set-part-status!)       ; exit status once reaped
  (ended?      part-ended?      set-part-ended!)
  (keep        part-keep        set-part-keep!))        ; what libvterm points at

(define (open-screen rows columns part)
  "RETURN: screen of 'rows' x 'columns', blank, the cursor at (0 . 0), its
alternate screen enabled; 'part' its terminal part or #f. Raises
'&library-missing' where libvterm is not found."
  (library)
  (let* ((vt     ((lib "vterm_new") rows columns))
         (screen ((lib "vterm_obtain_screen") vt))
         (state  ((lib "vterm_obtain_state") vt)))
    ((lib "vterm_set_utf8") vt 1)
    ;;  THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR.
    ((lib "vterm_screen_enable_altscreen") screen 1)
    ((lib "vterm_screen_reset") screen 1)
    (%make-screen rows columns vt screen state part)))

(define* (make-screen #:optional (rows 24) (columns 80))
  "RETURN: screen of 'rows' x 'columns' -- the grid alone, no process; raises
'&library-missing' where libvterm is not found. Give it back by
'screen-close!', or use 'call-with-screen'."
  (open-screen rows columns #f))

(define (free-screen! s)
  "RETURN: unspecified. The library's terminal is freed; a second call does
nothing."
  (when (screen-vt s)
    ((lib "vterm_free") (screen-vt s))
    (set-screen-vt! s #f)
    (set-screen-handle! s #f)
    (set-screen-state! s #f)))

(define (screen-close! s)
  "RETURN: unspecified. 's' is given back -- for a terminal, a still running
application killed and the pseudo-terminal closed first."
  (if (screen-part s) (terminal-close! s) (free-screen! s)))

(define (call-with-screen rows columns procedure)
  "RETURN: what '(procedure screen)' returns, for a fresh screen of 'rows' x
'columns' that is closed however 'procedure' is left -- Python's 'with'."
  (let ((s (make-screen rows columns)))
    (dynamic-wind (lambda () #f) (lambda () (procedure s)) (lambda () (screen-close! s)))))

(define (bytes-of data)
  "RETURN: bytevector, 'data' itself, or the string 'data' as UTF-8."
  (if (string? data) (string->utf8 data) data))

(define (plain-feed! s data)
  "RETURN: exact integer, the bytes of 'data' (bytevector or string, sent as
UTF-8) the terminal took."
  (let ((bv (bytes-of data)))
    (if (zero? (bytevector-length bv))
        0
        ((lib "vterm_input_write") (screen-vt s) (bytevector->pointer bv) (bytevector-length bv)))))

(define (screen-feed! s data)
  "RETURN: exact integer, the bytes of 'data' (what a program wrote: a
bytevector, or a string sent as UTF-8) the terminal took. On a terminal the
raw events fire before this returns, and what the terminal answered goes to
the application where one runs."
  (let ((taken (plain-feed! s data)))
    (when (screen-part s)
      ((lib "vterm_screen_flush_damage") (screen-handle s))
      (forward! s))
    taken))

(define (screen-cursor s)
  "RETURN: (row . column), the cursor's place, from 0."
  (let ((position (make-c-struct (list int int) (list 0 0))))
    ((lib "vterm_state_get_cursorpos") (screen-state s) position)
    (let ((p (parse-c-struct position (list int int))))
      (cons (car p) (cadr p)))))

(define (raw-cell s row column)
  "RETURN: bytevector, the library's own cell at that place, its colours
resolved to red, green, blue where the library keeps them otherwise."
  (let ((buffer (make-bytevector CELL-BYTE-N 0)))
    ((lib "vterm_screen_get_cell") (screen-handle s)
     (make-c-struct (list int int) (list row column)) (bytevector->pointer buffer))
    (when (and *layout* (layout-convert? *layout*))
      ;;  THE COLOUR'S STRUCTURE begins one byte before its red.
      (for-each (lambda (start)
                  ((lib "vterm_screen_convert_color_to_rgb") (screen-handle s)
                   (bytevector->pointer buffer (- start 1))))
                (list (layout-foreground-i *layout*) (layout-background-i *layout*))))
    buffer))

(define (screen-cell s row column)
  "RETURN: cell, what stands at that place; raises '&index-error' where the
place is not on the screen."
  (unless (and (<= 0 row) (< row (screen-rows s)) (<= 0 column) (< column (screen-columns s)))
    (raise-with make-index-error-condition
                (format #f "(~a, ~a) is not on a screen of ~a x ~a"
                        row column (screen-rows s) (screen-columns s))))
  (let* ((layout (measured))
         (raw    (raw-cell s row column))
         (text   (list->string
                  (filter-map (lambda (i)
                                (let ((code (bytevector-u32-ref raw (* 4 i) (endianness little))))
                                  (and (not (memv code '(0 #xFFFFFFFF)))
                                       (or (< code #xD800) (< #xDFFF code #x110000))
                                       (integer->char code))))
                              (iota CHARS-PER-CELL-N))))
         (colour (lambda (i default)
                   (let ((rgb (vector (bytevector-u8-ref raw i) (bytevector-u8-ref raw (+ i 1))
                                      (bytevector-u8-ref raw (+ i 2)))))
                     (if (equal? rgb default) #f rgb))))
         (flag   (lambda (name)
                   (let ((p (assoc-ref (layout-mask-db layout) name)))
                     (not (zero? (logand (bytevector-u8-ref raw (car p)) (cdr p))))))))
    (make-cell text
               (let ((w (bytevector-u8-ref raw CHARS-BYTE-N))) (if (zero? w) 1 w))
               (flag "bold") (flag "italic") (flag "underline") (flag "blink")
               (flag "reverse") (flag "conceal") (flag "strike")
               (colour (layout-foreground-i layout) (layout-default-fg layout))
               (colour (layout-background-i layout) (layout-default-bg layout)))))

(define (row-text s row column column-n)
  "RETURN: string, 'column-n' columns of row 'row' from 'column', a cell
nothing was written to read as a blank, blanks at the end dropped."
  (let loop ((at column) (pieces '()))
    (if (>= at (+ column column-n))
        (string-trim-right (string-concatenate (reverse pieces)) #\space)
        (let ((cell (screen-cell s row at)))
          (loop (+ at (max (cell-width cell) 1))
                (cons (if (string-null? (cell-text cell)) " " (cell-text cell)) pieces))))))

(define (screen-line s row)
  "RETURN: string, the row's characters, blanks at its end dropped; a cell
nothing was written to reads as a blank."
  (row-text s row 0 (screen-columns s)))

(define (screen-line-list s)
  "RETURN: list of strings, every row as 'screen-line' gives it, top first."
  (map (lambda (row) (screen-line s row)) (iota (screen-rows s))))

;;  ------------------------------------------------------------ the layout
(define (measured)
  "RETURN: layout, where this library's cell keeps each attribute and each
colour -- measured once on scratch terminals, then remembered."
  (or *layout*
      (let* ((cell-after
              (lambda (sequence)
                (let ((scratch (make-screen 2 4)))
                  (plain-feed! scratch (if (string-null? sequence) ""
                                           (string-append "\x1b[" sequence "m")))
                  (plain-feed! scratch "X")
                  (let ((raw (raw-cell scratch 0 0))) (free-screen! scratch) raw))))
             (plain   (cell-after ""))
             (changed (lambda (raw)
                        (filter-map (lambda (i)
                                      (let ((a (bytevector-u8-ref plain i))
                                            (b (bytevector-u8-ref raw i)))
                                        (and (not (= a b)) (cons i (logxor a b)))))
                                    (iota (- CELL-BYTE-N CHARS-BYTE-N 1) (+ CHARS-BYTE-N 1)))))
             (mask-db (map (lambda (entry)
                             (let ((found (changed (cell-after (cdr entry)))))
                               ;;  NOTHING MOVED: this library does not know it.
                               (cons (car entry)
                                     (if (pair? found) (car found) (cons (+ CHARS-BYTE-N 1) 0)))))
                           ATTRIBUTE-SGR-DB))
             ;;  UNDERLINE IS A NUMBER OF TWO BITS: the double's bit joins.
             (mask-db (map (lambda (entry)
                             (if (string=? (car entry) "underline")
                                 (cons (car entry)
                                       (fold (lambda (c mask)
                                               (if (= (car c) (car mask))
                                                   (cons (car mask) (logior (cdr mask) (cdr c)))
                                                   mask))
                                             (cdr entry) (changed (cell-after "21"))))
                                 entry))
                           mask-db))
             (colour-at (lambda (code)
                          (let ((raw (cell-after (string-append code ";2;1;2;3"))))
                            (find (lambda (i) (and (= (bytevector-u8-ref raw i) 1)
                                                   (= (bytevector-u8-ref raw (+ i 1)) 2)
                                                   (= (bytevector-u8-ref raw (+ i 2)) 3)))
                                  (iota (- CELL-BYTE-N CHARS-BYTE-N 3) (+ CHARS-BYTE-N 1))))))
             (foreground-i (colour-at "38"))
             (background-i (colour-at "48"))
             (convert?     (and (lib "vterm_screen_convert_color_to_rgb") #t)))
        ;;  THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell will be.
        (set! *layout* (make-layout mask-db foreground-i background-i convert? #f #f))
        (let* ((scratch (make-screen 2 4))
               (raw     (begin (plain-feed! scratch "X") (raw-cell scratch 0 0)))
               (rgb     (lambda (i) (vector (bytevector-u8-ref raw i) (bytevector-u8-ref raw (+ i 1))
                                            (bytevector-u8-ref raw (+ i 2))))))
          (free-screen! scratch)
          (set! *layout* (make-layout mask-db foreground-i background-i convert?
                                      (rgb foreground-i) (rgb background-i))))
        *layout*)))

;;  ------------------------------------------------------------ the C library
(define (libc)
  "RETURN: alist, the C library's 'openpty', 'read', 'write' and 'usleep' by
name, loaded once ('openpty' from libutil where libc lacks it)."
  (or *libc*
      (let* ((self    (dynamic-link))
             (openpty (catch #t (lambda () (dynamic-func "openpty" self))
                        (lambda _ (dynamic-func "openpty" (dynamic-link "libutil.so.1"))))))
        (set! *libc*
              `(("openpty" . ,(pointer->procedure int openpty '(* * * * *)))
                ("read"    . ,(pointer->procedure ssize_t (dynamic-func "read" self)
                                                  (list int '* size_t)))
                ("write"   . ,(pointer->procedure ssize_t (dynamic-func "write" self)
                                                  (list int '* size_t)))))
        *libc*)))

(define (c name)
  "RETURN: procedure, the C library's function 'name' (see 'libc')."
  (assoc-ref (libc) name))

;;  ---------------------------------------------------------------- terminal
(define* (make-terminal #:optional (rows 24) (columns 80) #:key (settle-s 0.1))
  "RETURN: terminal (a screen with a terminal part) of 'rows' x 'columns',
blank, nothing running in it; raises '&library-missing' where libvterm is
not found. 'settle-s' is how long the application must write nothing
before its screen is taken as drawn."
  (let* ((part (%make-part settle-s '() '() '() '() '() #f #f #f #f '()))
         (s    (open-screen rows columns part))
         (emit (lambda (event)
                 (for-each (lambda (f) (f event)) (part-event-list part))
                 1))
         (output (procedure->pointer
                  void (lambda (data length user)
                         (set-part-answer! part (cons (bytevector-copy
                                                       (pointer->bytevector data length))
                                                      (part-answer part))))
                  (list '* size_t '*)))
         (damage (procedure->pointer
                  int (lambda (rectangle user)
                        (let ((r (parse-c-struct rectangle (list int int int int))))
                          ;;  VTermRect: start_row, end_row, start_col, end_col
                          (emit (make-event "damage" (first r) (third r) (second r) (fourth r)
                                            #f #f))))
                  (list (list int int int int) '*)))
         (cursor (procedure->pointer
                  int (lambda (position old visible user)
                        (let ((p (parse-c-struct position (list int int))))
                          (emit (make-event "cursor" (first p) (second p) #f #f #f
                                            (not (zero? visible))))))
                  (list (list int int) (list int int) int '*)))
         (property (procedure->pointer
                    int (lambda (number value user)
                          (let ((entry (assv-ref PROPERTY-DB number)))
                            (emit (make-event "property" #f #f #f #f
                                              (if entry (car entry)
                                                  (string-append "property-" (number->string number)))
                                              (and entry (cdr entry)
                                                   (bytevector-s32-native-ref
                                                    (pointer->bytevector value 4) 0))))))
                    (list int '* '*)))
         (bell (procedure->pointer int (lambda (user) (emit (make-event "bell" #f #f #f #f #f #f)))
                                   '(*)))
         ;;  VTermScreenCallbacks: damage, moverect, movecursor, settermprop,
         ;;  bell, resize, sb_pushline, sb_popline -- and spare null slots.
         (callbacks (make-c-struct (make-list 16 '*)
                                   (append (list damage %null-pointer cursor property bell)
                                           (make-list 11 %null-pointer)))))
    ;;  WHAT libvterm POINTS AT LIVES AS LONG AS THE TERMINAL.
    (set-part-keep! part (list output damage cursor property bell callbacks))
    ((lib "vterm_output_set_callback") (screen-vt s) output %null-pointer)
    ((lib "vterm_screen_set_callbacks") (screen-handle s) callbacks %null-pointer)
    ((lib "vterm_screen_set_damage_merge") (screen-handle s) DAMAGE-MERGE-ROW)
    s))

(define (call-with-terminal rows columns procedure . settle)
  "RETURN: what '(procedure terminal)' returns, for a fresh terminal closed
however 'procedure' is left; 'settle' optional: '#:settle-s s'."
  (let ((t (apply make-terminal rows columns settle)))
    (dynamic-wind (lambda () #f) (lambda () (procedure t)) (lambda () (terminal-close! t)))))

(define (terminal-on-event! t procedure)
  "RETURN: unspecified. '(procedure event)' is called with every raw event
from now on."
  (let ((part (screen-part t)))
    (set-part-event-list! part (append (part-event-list part) (list procedure)))))

(define (terminal-on-change! t procedure)
  "RETURN: unspecified. '(procedure name line-list)' is called for every
region whose text changed, once the screen is quiet."
  (let ((part (screen-part t)))
    (set-part-change-list! part (append (part-change-list part) (list procedure)))))

(define* (terminal-region! t name row #:key (row-n 1) (column 0) (column-n #f))
  "RETURN: unspecified. The rectangle 'name' is observed from now on: 'row-n'
rows from 'row' (negative: from the bottom, -1 the last), 'column-n'
columns from 'column' (to the right edge where #f). What stands there now
is known, not news."
  (let* ((part     (screen-part t))
         (row      (if (< row 0) (+ row (screen-rows t)) row))
         (column-n (or column-n (- (screen-columns t) column)))
         (entry    (list name row row-n column column-n)))
    (set-part-region-list! part
                           (if (assoc name (part-region-list part))
                               (map (lambda (r) (if (equal? (car r) name) entry r))
                                    (part-region-list part))
                               (append (part-region-list part) (list entry))))
    (set-part-told-list! part (cons (cons name (terminal-region-text t name))
                                    (part-told-list part)))))

(define (terminal-region-text t name)
  "RETURN: list of strings, the region's rows as they stand now, blanks at
each row's end dropped; raises '&key-error' where no such region was
declared."
  (let ((entry (assoc name (part-region-list (screen-part t)))))
    (unless entry
      (raise-with make-key-error-condition (py-str-repr name)))
    (apply (lambda (row row-n column column-n)
             (map (lambda (r) (row-text t r column column-n)) (iota row-n row)))
           (cdr entry))))

(define (terminal-report! t)
  "RETURN: list of strings, the names of the regions whose text differs
from what was last told -- each told to every 'on-change' procedure, in the
order of declaration."
  (let ((part (screen-part t)))
    (filter-map
     (lambda (entry)
       (let* ((name (car entry)) (line-list (terminal-region-text t name))
              (told (assoc name (part-told-list part))))
         (and (not (and told (equal? (cdr told) line-list)))
              (begin
                (set-part-told-list! part (cons (cons name line-list) (part-told-list part)))
                (for-each (lambda (f) (f name line-list)) (part-change-list part))
                name))))
     (part-region-list part))))

(define (answer-bytes part)
  "RETURN: bytevector, what the terminal said and nobody took yet."
  (let* ((pieces (reverse (part-answer part)))
         (result (make-bytevector (apply + (map bytevector-length pieces)))))
    (fold (lambda (piece at)
            (bytevector-copy! piece 0 result at (bytevector-length piece))
            (+ at (bytevector-length piece)))
          0 pieces)
    result))

(define (terminal-answer! t)
  "RETURN: bytevector, what the terminal said since the last call that no
application took -- the reply to a question fed by hand, the sequence of a
key pressed with nothing running."
  (let* ((part (screen-part t)) (data (answer-bytes part)))
    (set-part-answer! part '())
    data))

(define (forward! t)
  "RETURN: unspecified. The terminal's words reach the application where
one runs; they wait for 'terminal-answer!' else."
  (let ((part (screen-part t)))
    (when (and part (part-master part) (pair? (part-answer part)))
      (let ((data (answer-bytes part)))
        (when (< ((c "write") (part-master part) (bytevector->pointer data)
                  (bytevector-length data))
                 0)
          (set-part-ended! part #t))
        (set-part-answer! part '())))))

(define* (terminal-send! t text #:key (react-s 1.0))
  "RETURN: #t where the application still runs after it. 'text' is typed
character by character as a keyboard sends it; the screen is given
'react-s' to begin answering and is read until quiet."
  (string-for-each (lambda (ch) ((lib "vterm_keyboard_unichar") (screen-vt t) (char->integer ch) 0))
                   text)
  (forward! t)
  (terminal-pump! t react-s))

(define* (terminal-press! t key #:key (modifiers '()) (react-s 1.0))
  "RETURN: #t where the application still runs after it; raises
'&key-error' where 'key' or a modifier has no name here. 'key' is a name of
KEY-DB ('enter', 'up', 'f5', ...) or one character; 'modifiers' a list of
'shift', 'alt', 'ctrl' -- '(terminal-press! t \"c\" #:modifiers '(\"ctrl\"))'
is Ctrl-C."
  (let ((modifier (fold (lambda (name m)
                          (logior m (or (assoc-ref MODIFIER-DB name)
                                        (raise-with make-key-error-condition (py-str-repr name)))))
                        0 modifiers)))
    (if (= (string-length key) 1)
        ((lib "vterm_keyboard_unichar") (screen-vt t) (char->integer (string-ref key 0)) modifier)
        ((lib "vterm_keyboard_key") (screen-vt t)
         (or (assoc-ref KEY-DB key) (raise-with make-key-error-condition (py-str-repr key)))
         modifier))
    (forward! t)
    (terminal-pump! t react-s)))

;;  -------------------------------------------------------- the application
(define (now-s)
  "RETURN: inexact real, the monotonic clock in seconds."
  (exact->inexact (/ (get-internal-real-time) internal-time-units-per-second)))

(define (running? part)
  "RETURN: #t where the application was started and has not been reaped;
reaps it (keeping its status) where it has ended."
  (and (part-pid part)
       (not (part-status part))
       (let ((result (waitpid (part-pid part) WNOHANG)))
         (if (zero? (car result))
             #t
             (begin (set-part-status! part (status-of (cdr result))) #f)))))

(define (status-of status)
  "RETURN: exact integer, Python's 'returncode' for the wait status
'status': the exit code, or minus the signal that ended it."
  (or (status:exit-val status) (- (status:term-sig status))))

(define (reap! part)
  "RETURN: exact integer, the application's exit status, waited for."
  (or (part-status part)
      (let ((status (status-of (cdr (waitpid (part-pid part))))))
        (set-part-status! part status)
        status)))

(define* (terminal-run! t argv #:key (env #f) (cwd #f) (start-s 10.0))
  "RETURN: #t where the application still runs once its first screen
stands; raises '&runtime-error' where one already runs here.

'argv' (a list of strings, searched on PATH) is started on a pseudo-terminal
of this terminal's size: stdin, stdout and stderr are that terminal, and it
is the application's controlling one. TERM is 'xterm-256color'; LINES and
COLUMNS are taken OUT of the environment ('env', a list of 'NAME=value',
or this process's), since they would overrule the size the terminal answers."
  (let ((part (screen-part t)))
    (when (part-pid part)
      (raise-with make-runtime-error-condition "an application already runs in this terminal"))
    (let ((master-box (make-bytevector 4 0))
          (slave-box  (make-bytevector 4 0))
          (name       (make-bytevector 4096 0))
          (size       (make-c-struct (list unsigned-short unsigned-short unsigned-short unsigned-short)
                                     (list (screen-rows t) (screen-columns t) 0 0))))
      (unless (zero? ((c "openpty") (bytevector->pointer master-box) (bytevector->pointer slave-box)
                      (bytevector->pointer name) %null-pointer size))
        (raise-with make-runtime-error-condition "openpty failed"))
      (let* ((master      (bytevector-s32-native-ref master-box 0))
             (slave       (bytevector-s32-native-ref slave-box 0))
             (slave-name  (pointer->string (bytevector->pointer name)))
             (environment (cons "TERM=xterm-256color"
                                (filter (lambda (e)
                                          (not (any (lambda (p) (string-prefix? p e))
                                                    '("TERM=" "LINES=" "COLUMNS="))))
                                        (or env (environ))))))
        (force-output (current-output-port))
        (force-output (current-error-port))
        (let ((pid (primitive-fork)))
          (when (zero? pid)
            (in-child slave-name argv environment cwd))
          (close-fdes slave)
          (set-part-master! part master)
          (set-part-pid! part pid)
          (set-part-status! part #f)
          (set-part-ended! part #f)
          (terminal-pump! t start-s))))))

(define (in-child slave-name argv environment cwd)
  "RETURN: never. The child leads its own session, the pseudo-terminal its
controlling one and its three streams; then it becomes 'argv'."
  (catch #t
    (lambda ()
      (setsid)
      (let ((fd (open-fdes slave-name O_RDWR)))
        (dup2 fd 0) (dup2 fd 1) (dup2 fd 2)
        (do ((i 3 (+ i 1))) ((= i 1024))
          (catch #t (lambda () (close-fdes i)) (lambda _ #f))))
      (when cwd (chdir cwd))
      (environ environment)
      (apply execlp (car argv) argv))
    (lambda _ (primitive-exit 127))))

(define* (terminal-pump! t #:optional (first-s 1.0))
  "RETURN: #t where the application still runs. READ UNTIL QUIET: wait up
to 'first-s' for the application to write at all, then go on reading until
it has written nothing for 'settle-s'; then the changed regions are
reported."
  (let ((part (screen-part t)) (buffer (make-bytevector 65536)))
    (let loop ((wait-s first-s))
      (when (and (part-master part) (not (part-ended? part)))
        (let* ((seconds (inexact->exact (floor wait-s)))
               (micro   (inexact->exact (round (* 1e6 (- wait-s seconds)))))
               (ready   (car (select (list (part-master part)) '() '() seconds micro))))
          (when (pair? ready)
            (let ((n ((c "read") (part-master part) (bytevector->pointer buffer) 65536)))
              (if (<= n 0)                  ; the last writer closed: it ended
                  (set-part-ended! part #t)
                  (let ((data (make-bytevector n)))
                    (bytevector-copy! buffer 0 data 0 n)
                    (screen-feed! t data)
                    (loop (part-settle-s part)))))))))
    (terminal-report! t)
    (and (running? part) (not (part-ended? part)))))

(define* (terminal-expect t text #:key (timeout-s 10.0))
  "RETURN: (row . column), where 'text' stands on the screen, once it does;
raises '&timeout-error', carrying the screen, where it does not within
'timeout-s'."
  (let ((deadline (+ (now-s) timeout-s)) (part (screen-part t)))
    (let loop ()
      (or (let search ((rows (screen-line-list t)) (row 0))
            (and (pair? rows)
                 (let ((i (string-contains (car rows) text)))
                   (if i (cons row i) (search (cdr rows) (+ row 1))))))
          (begin
            (when (or (>= (now-s) deadline) (part-ended? part) (not (part-master part)))
              (raise-with make-timeout-error-condition
                          (string-append "'" text "' did not appear; the screen:\n"
                                         (string-join (screen-line-list t) "\n"))))
            (terminal-pump! t (part-settle-s part))
            (loop))))))

(define (kill! part)
  "RETURN: unspecified. The application is killed and reaped."
  (catch #t (lambda () (kill (part-pid part) SIGKILL)) (lambda _ #f))
  (reap! part))

(define* (terminal-wait t #:key (timeout-s 10.0))
  "RETURN: exact integer, the application's exit status, once it has ended
and its last words are on the screen; #f where no application was run.
Raises '&timeout-error' where it still runs after 'timeout-s' -- it is
killed first."
  (let ((part (screen-part t)))
    (and (part-pid part)
         (let ((deadline (+ (now-s) timeout-s)))
           (let loop ()
             (when (terminal-pump! t (part-settle-s part))
               (when (>= (now-s) deadline)
                 (kill! part)
                 (raise-with make-timeout-error-condition
                             (format #f "the application still ran after ~,1f s" timeout-s)))
               (loop)))
           (let ((until (+ (now-s) (max (- deadline (now-s)) 0.1))))
             (let poll ()
               (cond ((not (running? part)) (part-status part))
                     ((>= (now-s) until)
                      (kill! part)
                      (raise-with make-timeout-error-condition
                                  "the application closed its terminal and did not end"))
                     (else (usleep 2000) (poll)))))))))

(define (terminal-close! t)
  "RETURN: unspecified. An application still running is killed, the
pseudo-terminal closed, the terminal's memory freed."
  (let ((part (screen-part t)))
    (when (running? part) (kill! part))
    (when (part-master part)
      (close-fdes (part-master part))
      (set-part-master! part #f))
    (free-screen! t)))

;;  THE DETECTION, asked by hand: 'guile hwut/vterm.scm' says whether the
;;  library is there -- its name and exit 0, or the message and exit 1.
(when (and (pair? (command-line)) (string=? (basename (car (command-line))) "vterm.scm"))
  (let ((text (vterm-detection-text)))
    (display text) (newline)
    (exit (if (string-prefix? "libvterm found: " text) 0 1))))
