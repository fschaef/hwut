;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: THE HOCON SUBSET, PARSED INTO THE ANNOTATED TREE -- the port of
;;;          'python/hwut_hocon.py' (read '../python/README-hwut_hocon.txt'):
;;;          every key, value and block carries its file-relative position;
;;;          the parser collects faults, recovers, and never raises.
;;;
;;;     (call-with-values
;;;         (lambda () (hocon-parse (list (make-source-line "a = 1" 1 0)) "f.hocon"))
;;;       (lambda (document fault-list) ...))
;;;
;;; THE TREE IS AN S-EXPRESSION -- HOCON is a tree of data, and so is a list:
;;;
;;;     (object (1 . 1)                         ; position: (line . column)
;;;       (entry "a" (1 . 1) (scalar (1 . 5) 1))
;;;       (entry "b" (2 . 1) (list (2 . 5) (scalar (2 . 6) "x") ...)))
;;;
;;; A scalar's value is a string, an exact integer (Python's int), an inexact
;;; real (Python's float), #t or #f, or the symbol 'null' -- HOCON's word for
;;; nothing, Python's None. A fault is (fault SYNTAX|REFUSED file position
;;; message); 'hocon-fault->string' writes it as Python's 'str(ParseFault)'.
;;; The accessors below name the parts; '(ice-9 match)' takes the tree apart
;;; as well.
;;;
;;; WHERE THE PYTHON USES A REGULAR EXPRESSION, a scanner stands here (the
;;; token, the decimal number, the strict roman numeral): Guile's 'regexp' is
;;; the C library's and reads the text in the locale's encoding.
;;;_____________________________________________________________________________
(define-module (hwut hocon)
  #:use-module (srfi srfi-1)
  #:use-module (srfi srfi-9)
  #:export (make-source-line source-line? source-line-text source-line-line
            source-line-column-offset
            hocon-parse
            hocon-object? hocon-list? hocon-scalar? hocon-node-position
            hocon-object-entries hocon-object-get hocon-object-keys
            hocon-entry-key hocon-entry-key-position hocon-entry-node
            hocon-list-items hocon-scalar-value
            hocon-fault-kind hocon-fault-file hocon-fault-position hocon-fault-message
            hocon-position->string hocon-fault->string
            hocon-cleandoc))

;;  --------------------------------------------------------------- the tree
(define-record-type <source-line>
  (make-source-line text line column-offset)
  source-line?
  (text          source-line-text)
  (line          source-line-line)
  (column-offset source-line-column-offset))

(define (hocon-object? node)     "RETURN: #t where 'node' is an object."  (eq? (car node) 'object))
(define (hocon-list? node)       "RETURN: #t where 'node' is a list."     (eq? (car node) 'list))
(define (hocon-scalar? node)     "RETURN: #t where 'node' is a scalar."   (eq? (car node) 'scalar))
(define (hocon-node-position node) "RETURN: (line . column), where 'node' begins." (cadr node))
(define (hocon-object-entries node) "RETURN: list, the object's entries in written order." (cddr node))
(define (hocon-list-items node)  "RETURN: list, the list's item nodes in order." (cddr node))
(define (hocon-scalar-value node) "RETURN: the scalar's value (string, number, boolean, 'null)." (caddr node))
(define (hocon-entry-key entry)  "RETURN: string, the entry's key."       (cadr entry))
(define (hocon-entry-key-position entry) "RETURN: (line . column) of the entry's key." (caddr entry))
(define (hocon-entry-node entry) "RETURN: node, the entry's value."      (cadddr entry))
(define (hocon-fault-kind f)     "RETURN: symbol, SYNTAX or REFUSED."      (cadr f))
(define (hocon-fault-file f)     "RETURN: string, the file the fault names." (caddr f))
(define (hocon-fault-position f) "RETURN: (line . column) of the fault."   (cadddr f))
(define (hocon-fault-message f)  "RETURN: string, what the fault is."     (list-ref f 4))

(define (hocon-object-get node key)
  "RETURN: entry, the entry of the object 'node' named 'key';
#f, where no such entry stands."
  (find (lambda (e) (string=? (hocon-entry-key e) key)) (hocon-object-entries node)))

(define (hocon-object-keys node)
  "RETURN: list of strings, the keys of the object 'node' in written order."
  (map hocon-entry-key (hocon-object-entries node)))

(define (hocon-position->string position)
  "RETURN: string, 'line:column'."
  (string-append (number->string (car position)) ":" (number->string (cdr position))))

(define (hocon-fault->string fault)
  "RETURN: string, 'file:line:column: KIND: message'."
  (string-append (hocon-fault-file fault) ":" (hocon-position->string (hocon-fault-position fault))
                 ": " (symbol->string (hocon-fault-kind fault)) ": " (hocon-fault-message fault)))

;;  ------------------------------------------------------------- the cursor
(define-record-type <cursor>
  (%make-cursor line-vector line-n i-line i-col text)
  cursor?
  (line-vector cursor-line-vector)
  (line-n      cursor-line-n)
  (i-line      cursor-i-line set-cursor-i-line!)
  (i-col       cursor-i-col  set-cursor-i-col!)
  (text        cursor-text   set-cursor-text!))

(define (make-cursor line-list)
  "RETURN: cursor at the first character of the source lines 'line-list'."
  (let ((v (list->vector line-list)))
    (%make-cursor v (vector-length v) 0 0
                  (if (null? line-list) "" (source-line-text (car line-list))))))

(define (at-end? c)
  "RETURN: #t where no character remains."
  (>= (cursor-i-line c) (cursor-line-n c)))

(define* (peek c #:optional (ahead 0))
  "RETURN: char, the character 'ahead' places from here on this line;
#\\newline at the line's end; #f beyond the last line."
  (if (at-end? c)
      #f
      (let ((i (+ (cursor-i-col c) ahead)) (text (cursor-text c)))
        (if (< i (string-length text)) (string-ref text i) #\newline))))

(define (skip! c n)
  "RETURN: unspecified. Steps 'n' characters within the current line."
  (set-cursor-i-col! c (+ (cursor-i-col c) n)))

(define (skip-line! c)
  "RETURN: unspecified. Steps to the beginning of the next line."
  (set-cursor-i-line! c (+ (cursor-i-line c) 1))
  (set-cursor-i-col! c 0)
  (set-cursor-text! c (if (at-end? c)
                          ""
                          (source-line-text (vector-ref (cursor-line-vector c)
                                                        (cursor-i-line c))))))

(define (position c)
  "RETURN: (line . column), file-relative, of the character at the cursor;
past the end, the place after the last line's last character."
  (let ((v (cursor-line-vector c)))
    (cond ((not (at-end? c))
           (let ((line (vector-ref v (cursor-i-line c))))
             (cons (source-line-line line)
                   (+ (source-line-column-offset line) (cursor-i-col c) 1))))
          ((zero? (vector-length v)) (cons 1 1))
          (else
           (let ((last (vector-ref v (- (vector-length v) 1))))
             (cons (source-line-line last)
                   (+ (source-line-column-offset last)
                      (string-length (source-line-text last)) 1)))))))

;;  ------------------------------------------------------ characters, tokens
;;  Python's '\s' is 'str.isspace': Unicode's white space and 0x1c..0x1f.
(define space-set
  (char-set-union char-set:whitespace (ucs-range->char-set #x1c #x20)))

(define token-stop-set
  (char-set-union space-set (string->char-set "{}[]=,:\"#")))

(define (token-at text i)
  "RETURN: string, the TOKEN at index 'i' of 'text' -- the run up to the
first blank or character that binds, opens, closes or separates; '' where
none stands there."
  (let ((n (string-length text)))
    (let loop ((j i))
      (if (and (< j n) (not (char-set-contains? token-stop-set (string-ref text j))))
          (loop (+ j 1))
          (substring text (min i n) (max (min i n) j))))))

(define (blank-end text i)
  "RETURN: exact integer, the index of the first character at or after 'i'
that is no blank (' ' or tab)."
  (if (and (< i (string-length text)) (memv (string-ref text i) '(#\space #\tab)))
      (blank-end text (+ i 1))
      i))

(define (fault! fault-box kind file position message)
  "RETURN: unspecified. One fault appended to the faults in 'fault-box'."
  (set-car! fault-box (cons (list 'fault kind file position message) (car fault-box))))

;;  ---------------------------------------------------------------- parsing
(define (hocon-parse line-list file)
  "RETURN: (values document fault-list): 'document' the object node of every
entry of the outermost level, possibly empty; 'fault-list' every fault in
the order found, '() for a clean parse. 'line-list' are source lines,
'file' names the file for the faults. Never raises on any text."
  (let* ((cursor    (make-cursor line-list))
         (fault-box (list '()))
         (document  (parse-body cursor #f file fault-box)))
    (values document (reverse (car fault-box)))))

(define (parse-body cursor terminator file fault-box)
  "RETURN: object node, the entries up to 'terminator' (#\\} or #f for the
end of the text)."
  (let ((start (position cursor)))
    (let loop ((entries '()))
      (skip-blank! cursor)
      (cond
       ((at-end? cursor)
        (when terminator
          (fault! fault-box 'SYNTAX file (position cursor)
                  (string-append "unterminated object: '" (string terminator) "' missing")))
        `(object ,start ,@(reverse entries)))
       ((and terminator (eqv? (peek cursor) terminator))
        (skip! cursor 1)
        `(object ,start ,@(reverse entries)))
       ((eqv? (peek cursor) #\})
        (fault! fault-box 'SYNTAX file (position cursor) "unmatched '}'")
        (skip! cursor 1)
        (loop entries))
       (else (loop (parse-entry cursor entries file fault-box)))))))

(define (parse-entry cursor entries file fault-box)
  "RETURN: list, 'entries' (newest first) with the one 'key = value' pair
read here, where it was read and its key is new; 'entries' as it was else
-- faults recover at the next line."
  (let* ((key-position (position cursor))
         (key          (parse-key cursor file fault-box)))
    (cond
     ((not key) (skip-line! cursor) entries)
     ((string=? key "include")
      (fault! fault-box 'REFUSED file key-position
              (string-append "'include' does not exist here: a specification refers to "
                             "nothing outside its file"))
      (skip-line! cursor)
      entries)
     (else
      (skip-space! cursor)
      (let ((c (peek cursor)))
        (cond
         ((memv c '(#\= #\:)) (skip! cursor 1) (skip-space! cursor) (value-of cursor key key-position entries file fault-box))
         ((eqv? c #\{)        (value-of cursor key key-position entries file fault-box))
         ((and (eqv? c #\+) (eqv? (peek cursor 1) #\=))
          (fault! fault-box 'REFUSED file (position cursor) "'+=' does not exist here")
          (skip-line! cursor)
          entries)
         (else
          (fault! fault-box 'SYNTAX file (position cursor)
                  (string-append "expected '=', ':' or '{' after key '" key "'"))
          (skip-line! cursor)
          entries)))))))

(define (value-of cursor key key-position entries file fault-box)
  "RETURN: list, 'entries' with (entry key key-position value) where a value
is read here and 'key' is new; 'entries' else (a duplicate is a fault)."
  (let ((node (parse-value cursor file fault-box #f)))
    (cond
     ;;  The value parser has recovered already; a second skip would eat
     ;;  the NEXT line.
     ((not node) entries)
     ((find (lambda (e) (string=? (hocon-entry-key e) key)) entries)
      (fault! fault-box 'SYNTAX file key-position
              (string-append "duplicate key '" key "'; the first stands, this one is refused"))
      entries)
     (else (cons (list 'entry key key-position node) entries)))))

(define (parse-key cursor file fault-box)
  "RETURN: string, the key here; #f, where no key stands (fault recorded)."
  (if (eqv? (peek cursor) #\")
      (parse-quoted cursor file fault-box)
      (let ((text (token-at (cursor-text cursor) (cursor-i-col cursor))))
        (if (string-null? text)
            (begin
              (fault! fault-box 'SYNTAX file (position cursor)
                      (string-append "expected a key, found '"
                                     (string-trim-both (char->text (peek cursor)) space-set)
                                     "'"))
              #f)
            (begin (skip! cursor (string-length text)) text)))))

(define (char->text c)
  "RETURN: string, the character 'c' as a text; '' for #f."
  (if c (string c) ""))

(define (parse-value cursor file fault-box in-list?)
  "RETURN: node, the value here; #f, where nothing usable stands (fault
recorded). 'in-list?' makes an empty value a fault rather than null."
  (skip-space! cursor)
  (let ((start (position cursor)) (c (peek cursor)))
    (cond
     ((eqv? c #\{) (skip! cursor 1) (parse-body cursor #\} file fault-box))
     ((eqv? c #\[) (skip! cursor 1) (parse-list cursor start file fault-box))
     ((and (eqv? c #\") (eqv? (peek cursor 1) #\") (eqv? (peek cursor 2) #\"))
      (let ((value (parse-triple-quoted cursor file fault-box)))
        (and value `(scalar ,start ,value))))
     ((eqv? c #\")
      (let ((value (parse-quoted cursor file fault-box)))
        (and value `(scalar ,start ,value))))
     ((and (eqv? c #\$) (eqv? (peek cursor 1) #\{))
      (fault! fault-box 'REFUSED file start
              (string-append "substitutions '${...}' do not exist here: a specification "
                             "refers to nothing outside its file"))
      (skip-line! cursor)
      #f)
     (else (parse-bare cursor start file fault-box in-list?)))))

(define (parse-list cursor start file fault-box)
  "RETURN: list node, the items up to ']'."
  (let loop ((items '()))
    (skip-blank! cursor)
    (cond
     ((at-end? cursor)
      (fault! fault-box 'SYNTAX file (position cursor) "unterminated list: ']' missing")
      `(list ,start ,@(reverse items)))
     ((eqv? (peek cursor) #\]) (skip! cursor 1) `(list ,start ,@(reverse items)))
     ((eqv? (peek cursor) #\,) (skip! cursor 1) (loop items))
     ((eqv? (peek cursor) #\})
      ;;  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' was forgotten.
      ;;  Said once, the brace left to its owner.
      (fault! fault-box 'SYNTAX file (position cursor)
              "unterminated list: ']' missing before '}'")
      `(list ,start ,@(reverse items)))
     (else
      (let* ((before (cons (cursor-i-line cursor) (cursor-i-col cursor)))
             (item   (parse-value cursor file fault-box #t)))
        ;;  NO VALUE READ AND NOTHING CONSUMED: step over the refused
        ;;  character, or the loop never ends.
        (when (and (not item)
                   (equal? before (cons (cursor-i-line cursor) (cursor-i-col cursor))))
          (skip! cursor 1))
        (loop (if item (cons item items) items)))))))

(define (string-find text pattern start)
  "RETURN: exact integer, the index of the first 'pattern' in 'text' at or
after 'start'; #f where there is none."
  (string-contains text pattern (min start (string-length text))))

(define (parse-triple-quoted cursor file fault-box)
  "RETURN: string, the text between three double quotes and the next three,
over as many lines as it takes, AS WRITTEN (no escape resolved), laid out
as Python's 'inspect.cleandoc' lays out a docstring; #f, where no closing
three quotes stand before the text's end (fault recorded)."
  (let ((start (position cursor)))
    (skip! cursor 3)
    (let loop ((pieces '()))
      (if (at-end? cursor)
          (begin
            (fault! fault-box 'SYNTAX file start
                    "unterminated triple-quoted string: closing '\"\"\"' missing")
            #f)
          (let* ((text (cursor-text cursor))
                 (end  (string-find text "\"\"\"" (cursor-i-col cursor))))
            (if end
                (let ((piece (substring text (cursor-i-col cursor) end)))
                  (set-cursor-i-col! cursor (+ end 3))
                  (hocon-cleandoc (string-join (reverse (cons piece pieces)) "\n")))
                (let ((piece (substring text (min (cursor-i-col cursor) (string-length text)))))
                  (skip-line! cursor)
                  (loop (cons piece pieces)))))))))

(define (parse-quoted cursor file fault-box)
  "RETURN: string, the quoted string's content, escapes ('\\n', '\\t', '\\\"',
'\\\\'; any other character stands for itself) resolved; #f, where it is
unterminated at its line's end (fault recorded)."
  (let* ((start (position cursor))
         (text  (cursor-text cursor))
         (n     (string-length text)))
    (let loop ((i (+ (cursor-i-col cursor) 1)) (pieces '()))
      (cond
       ((>= i n)
        (fault! fault-box 'SYNTAX file start "unterminated string")
        (set-cursor-i-col! cursor i)
        #f)
       ((char=? (string-ref text i) #\")
        (set-cursor-i-col! cursor (+ i 1))
        (list->string (reverse pieces)))
       ((char=? (string-ref text i) #\\)
        (if (< (+ i 1) n)
            (let ((e (string-ref text (+ i 1))))
              (loop (+ i 2) (cons (case e ((#\n) #\newline) ((#\t) #\tab) (else e)) pieces)))
            (loop (+ i 2) pieces)))
       (else (loop (+ i 1) (cons (string-ref text i) pieces)))))))

(define (parse-bare cursor start file fault-box in-list?)
  "RETURN: scalar node, the bare token here: a boolean, a number or a
spelling of nothing; #f, where it is none of those (fault recorded) -- a
string value is written in double quotes."
  (let* ((text (cursor-text cursor))
         (raw  (token-at text (cursor-i-col cursor))))
    (or
     ;;  A SIGN STANDING APART from its digits ('- 0.12'): joined to the
     ;;  next token where the two make ONE number ('- -1.5e3' does not).
     (and (member raw '("+" "-"))
          (let* ((at    (blank-end text (+ (cursor-i-col cursor) 1)))
                 (after (token-at text at)))
            (and (not (string-null? after)) (number-of after)
                 (let ((joined (number-of (string-append raw after))))
                   (and joined
                        (begin (set-cursor-i-col! cursor (+ at (string-length after)))
                               `(scalar ,start ,(car joined))))))))
     (cond
      ((string-prefix? "${" raw)
       (fault! fault-box 'REFUSED file (position cursor) "substitutions '${...}' do not exist here")
       (skip-line! cursor)
       #f)
      (else
       (let ((raw (let ((i (string-contains raw "//"))) (if i (substring raw 0 i) raw))))
         (skip! cursor (string-length raw))
         (cond
          ((string-null? raw)
           (if in-list?
               (begin
                 (fault! fault-box 'SYNTAX file start
                         (string-append "expected a value, found '"
                                        (string-trim-both (char->text (peek cursor)) space-set)
                                        "'"))
                 #f)
               `(scalar ,start null)))            ; an empty value is null
          ((interpret raw) => (lambda (value) `(scalar ,start ,(car value))))
          (else
           (fault! fault-box 'SYNTAX file start
                   (string-append "a string is written in double quotes: \"" raw "\""))
           #f))))))))

;;  -------------------------------------------------------------- the values
(define (interpret raw)
  "RETURN: (value), a one-element list of what the bare text says: 'null for
the spellings of nothing, #t/#f, a number; #f, where the text is no bare
token -- an unquoted string, which this language has not."
  (cond ((member raw '("null" "nil" "none" "nihil")) (list 'null))
        ((member raw '("true" "yes"))               (list #t))
        ((member raw '("false" "no"))               (list #f))
        (else (number-of raw))))

(define (number-of raw)
  "RETURN: (number), a one-element list of the number 'raw' spells --
decimal, '0x' hexadecimal, '0b' binary, '0o' octal or '0r' strict roman,
'_' between digits entering no value; #f, where it spells none."
  (let* ((signed? (and (> (string-length raw) 0) (memv (string-ref raw 0) '(#\+ #\-))))
         (body    (if signed? (substring raw 1) raw))
         (sign    (if (and signed? (char=? (string-ref raw 0) #\-)) -1 1))
         (prefix  (if (>= (string-length body) 2) (substring body 0 2) "")))
    (cond
     ((member prefix '("0r" "0R"))
      (let ((value (roman (substring body 2))))
        (and value (list (* sign value)))))
     ((assoc prefix '(("0x" . 16) ("0X" . 16) ("0b" . 2) ("0B" . 2) ("0o" . 8) ("0O" . 8)))
      => (lambda (p)
           (let ((digits (without-helper (substring body 2) (cdr p))))
             (and digits (list (* sign (string->number digits (cdr p))))))))
     ((decimal? raw)
      (let ((text (string-delete #\_ raw)))
        (if (string-any (lambda (c) (memv c '(#\. #\e #\E))) text)
            (list (decimal->float text))
            (list (string->number (if (string-prefix? "+" text) (substring text 1) text))))))
     (else #f))))

(define (without-helper text radix)
  "RETURN: string, 'text' with every '_' removed; #f, where it carries no
digit, a character that is no digit of 'radix', or an '_' that separates
nothing (leading, trailing, doubled)."
  (let ((digit-set (case radix ((16) "0123456789abcdefABCDEF") ((2) "01") (else "01234567"))))
    (and (not (string-null? text))
         (not (char=? (string-ref text 0) #\_))
         (not (char=? (string-ref text (- (string-length text) 1)) #\_))
         (not (string-contains text "__"))
         (let ((stripped (string-delete #\_ text)))
           (and (not (string-null? stripped))
                (string-every (lambda (c) (string-index digit-set c)) stripped)
                stripped)))))

(define (digits-end text i)
  "RETURN: exact integer, the index past a run 'D(_?D)*' of decimal digits
beginning at 'i' (an '_' only between two digits); #f where no digit
stands at 'i'."
  (let ((n (string-length text)))
    (define (digit? j) "RETURN: #t where a decimal digit stands at 'j'." (and (< j n) (char<=? #\0 (string-ref text j) #\9)))
    (and (digit? i)
         (let loop ((j (+ i 1)))
           (cond ((digit? j) (loop (+ j 1)))
                 ((and (< j n) (char=? (string-ref text j) #\_) (digit? (+ j 1))) (loop (+ j 2)))
                 (else j))))))

(define (decimal? raw)
  "RETURN: #t where the whole of 'raw' is a decimal number: a sign, digits
with an optional fraction or a fraction alone, an optional exponent --
Python's '_DECIMAL_RE'."
  (let* ((n (string-length raw))
         (i (if (and (> n 0) (memv (string-ref raw 0) '(#\+ #\-))) 1 0))
         (at (lambda (j c) (and (< j n) (char=? (string-ref raw j) c))))
         (mantissa-end
          (cond ((digits-end raw i)
                 => (lambda (j) (if (at j #\.) (or (digits-end raw (+ j 1)) (+ j 1)) j)))
                ((at i #\.) (digits-end raw (+ i 1)))
                (else #f))))
    (and mantissa-end
         (or (= mantissa-end n)
             (and (or (at mantissa-end #\e) (at mantissa-end #\E))
                  (let* ((k (+ mantissa-end 1))
                         (k (if (and (< k n) (memv (string-ref raw k) '(#\+ #\-))) (+ k 1) k)))
                    (eqv? (digits-end raw k) n)))))))

(define (decimal->float text)
  "RETURN: inexact real, the double nearest the decimal 'text' (no '_') --
Python's 'float(text)': 'inf' beyond the largest double, a signed zero
below the smallest; exact arithmetic, so the rounding is correct."
  (let* ((negative? (string-prefix? "-" text))
         (body      (if (memv (string-ref text 0) '(#\+ #\-)) (substring text 1) text))
         (e-index   (string-index body (char-set #\e #\E)))
         (mantissa  (if e-index (substring body 0 e-index) body))
         (exponent  (if e-index
                        (let ((e (substring body (+ e-index 1))))
                          (string->number (if (string-prefix? "+" e) (substring e 1) e)))
                        0))
         (dot       (string-index mantissa #\.))
         (fraction  (if dot (substring mantissa (+ dot 1)) ""))
         (digits    (string-append (if dot (substring mantissa 0 dot) mantissa) fraction))
         (integer   (if (string-null? digits) 0 (string->number digits 10)))
         (e10       (- exponent (string-length fraction)))
         (magnitude (if (zero? integer) 0
                        (+ (string-length (number->string integer)) e10)))
         (value     (cond ((zero? integer) 0.0)
                          ((> magnitude 400) +inf.0)
                          ((< magnitude -400) 0.0)
                          (else (exact->inexact (* integer (expt 10 e10)))))))
    (if negative? (- value) value)))

(define (roman-group text i one five ten)
  "RETURN: list of exact integers, every index where one roman digit group
-- 'one ten', 'one five', or 'five' optional then up to three 'one' --
beginning at 'i' of 'text' can end."
  (let* ((n (string-length text))
         (at (lambda (j c) (and c (< j n) (char=? (string-ref text j) c))))
         (pairs (append (if (and (at i one) (at (+ i 1) ten)) (list (+ i 2)) '())
                        (if (and (at i one) (at (+ i 1) five)) (list (+ i 2)) '())))
         (start (if (at i five) (list i (+ i 1)) (list i))))
    (append pairs
            (append-map (lambda (j)
                          (let loop ((k 0) (result (list j)))
                            (if (and (< k 3) (at (+ j k) one))
                                (loop (+ k 1) (cons (+ j k 1) result))
                                result)))
                        start))))

(define (roman text)
  "RETURN: exact integer, the number the roman numeral 'text' spells; #f,
where it is none in the strict form -- 'IIII' and 'VX' among them."
  (let ((n (string-length text)))
    (and (> n 0)
         (any (lambda (a)
                (any (lambda (b)
                       (any (lambda (c)
                              (any (lambda (d) (= d n))
                                   (roman-group text c #\I #\V #\X)))
                            (roman-group text b #\X #\L #\C)))
                     (roman-group text a #\C #\D #\M)))
              (roman-group text 0 #\M #f #f))
         (let loop ((rest (reverse (string->list text))) (total 0) (previous 0))
           (if (null? rest)
               total
               (let ((value (assv-ref '((#\I . 1) (#\V . 5) (#\X . 10) (#\L . 50)
                                        (#\C . 100) (#\D . 500) (#\M . 1000))
                                      (car rest))))
                 (loop (cdr rest)
                       (if (< value previous) (- total value) (+ total value))
                       (max previous value))))))))

;;  ---------------------------------------------------------- skipping blanks
(define (skip-space! cursor)
  "RETURN: unspecified. Skips blanks and tabs on the current line; a comment
('#', '//') skips the rest of the line."
  (let* ((text (cursor-text cursor))
         (i    (blank-end text (cursor-i-col cursor))))
    (set-cursor-i-col! cursor i)
    (when (and (< i (string-length text))
               (or (char=? (string-ref text i) #\#) (string-prefix? "//" text 0 2 i)))
      (skip-line! cursor))))

(define (skip-blank! cursor)
  "RETURN: unspecified. Skips blanks, tabs, commas, line ends and comments."
  (let loop ()
    (unless (at-end? cursor)
      (let* ((text (cursor-text cursor))
             (n    (string-length text))
             (i    (let skip ((i (cursor-i-col cursor)))
                     (if (and (< i n) (memv (string-ref text i) '(#\space #\tab #\,)))
                         (skip (+ i 1))
                         i))))
        (cond ((>= i n) (skip-line! cursor) (loop))
              (else
               (set-cursor-i-col! cursor i)
               (when (or (char=? (string-ref text i) #\#)
                         (and (char=? (string-ref text i) #\/) (string-prefix? "//" text 0 2 i)))
                 (skip-line! cursor)
                 (loop))))))))

;;  ---------------------------------------------------------------- cleandoc
(define (expand-tabs text)
  "RETURN: string, 'text' with every tab replaced by blanks to the next
column that is a multiple of 8, the column counted from the last line end
-- Python's 'str.expandtabs()'."
  (let loop ((chars (string->list text)) (column 0) (result '()))
    (cond ((null? chars) (list->string (reverse result)))
          ((char=? (car chars) #\tab)
           (let ((k (- 8 (modulo column 8))))
             (loop (cdr chars) (+ column k) (append (make-list k #\space) result))))
          ((memv (car chars) '(#\newline #\return))
           (loop (cdr chars) 0 (cons (car chars) result)))
          (else (loop (cdr chars) (+ column 1) (cons (car chars) result))))))

(define (hocon-cleandoc doc)
  "RETURN: string, 'doc' as Python's 'inspect.cleandoc' lays it out: tabs
expanded, the first line's leading blanks removed, the indentation common
to the other non-blank lines removed from them, blank lines at both ends
dropped."
  (let* ((lines  (string-split (expand-tabs doc) #\newline))
         (indent (lambda (l) (- (string-length l) (string-length (string-trim l #\space)))))
         (margin (fold (lambda (l m)
                         (if (string-null? (string-trim l #\space)) m
                             (if m (min m (indent l)) (indent l))))
                       #f (cdr lines)))
         (lines  (cons (string-trim (car lines) #\space)
                       (map (lambda (l) (if margin (substring l (min margin (string-length l))) l))
                            (cdr lines))))
         (lines  (drop-while string-null? (reverse (drop-while string-null? (reverse lines))))))
    (string-join lines "\n")))
