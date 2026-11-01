;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: TEXT AS PYTHON PRINTS IT -- so a Guile test and a Python test of
;;;          the same module print the same bytes, and share one GOOD file by
;;;          a '.link' (bookkeeper B-32). The twin of '../../c/hwut_pytext.c'.
;;;
;;;     (py-float-repr 0.1)          "0.1"        the shortest text that reads
;;;     (py-float-repr 1e-5)         "1e-05"      back; exponential below 1e-4
;;;     (py-float-repr 1e16)         "1e+16"      and from 1e16 on
;;;     (py-str-repr "it's")         "\"it's\""   Python's choice of quotes
;;;     (py-bytes-repr #vu8(27 91 65)) "b'\\x1b[A'"
;;;     (py-repr '#("a"))            "('a',)"     a VECTOR prints as a tuple
;;;     (py-repr '(1 2))             "[1, 2]"     a LIST as a list
;;;     (py-repr #t)                 "True"
;;;     (py-repr 'null)              "None"       HOCON's nothing (hwut hocon)
;;;
;;; SCHEME TELLS AN INTEGER FROM A FLOAT AS PYTHON DOES: an exact integer is
;;; Python's 'int', an inexact real its 'float' -- so 'py-repr' needs no hint
;;; from the caller (the Perl port needs one, having one scalar for both).
;;;_____________________________________________________________________________
(define-module (hwut pytext)
  #:use-module (rnrs bytevectors)
  #:use-module (srfi srfi-1)
  #:export (py-float-repr py-str-repr py-bytes-repr py-bool py-repr
            py-str py-list-repr py-tuple-repr py-ljust py-rjust py-join))

(define (py-bool value)
  "RETURN: string, \"True\" where 'value' is true, \"False\" where it is #f."
  (if value "True" "False"))

(define (shortest-digits x)
  "RETURN: (values digits point), for the finite, non-zero, positive double
'x': 'digits' the shortest decimal digit string that reads back to 'x' (no
leading or trailing zero), 'point' such that x = 0.<digits> * 10^point.
Guile's 'number->string' already writes the shortest round-trip text; only
its layout ('1.0e-6', '123.0') is taken apart here."
  (let* ((text      (number->string x))
         (e-index   (string-index text #\e))
         (mantissa  (if e-index (substring text 0 e-index) text))
         (exponent  (if e-index (string->number (substring text (+ e-index 1))) 0))
         (dot       (or (string-index mantissa #\.) (string-length mantissa)))
         (all       (string-delete #\. mantissa))
         (lead      (or (string-skip all #\0) (string-length all)))
         (stripped  (string-trim-right (substring all lead) #\0)))
    ;; value = 0.<all> * 10^(dot + exponent); leading zeros move the point.
    (values stripped (- (+ dot exponent) lead))))

(define (py-float-repr x)
  "RETURN: string, the inexact real 'x' as Python's 'repr(float)' writes it --
the shortest decimal that reads back to the same double; fixed notation
where the decimal point falls in (-4, 16], exponential ('1e-05', '7e+212')
else; 'inf', '-inf', 'nan', '-0.0' as Python spells them."
  (cond
   ((nan? x)                             "nan")
   ((and (inf? x) (> x 0))               "inf")
   ((inf? x)                             "-inf")
   ((zero? x)                            (if (eqv? x -0.0) "-0.0" "0.0"))
   (else
    (let ((sign (if (< x 0) "-" "")))
      (call-with-values (lambda () (shortest-digits (abs x)))
        (lambda (digits point)
          (let ((n (string-length digits)))
            (cond
             ((and (> point -4) (<= point 16))
              (cond
               ((<= point 0)
                (string-append sign "0." (make-string (- point) #\0) digits))
               ((>= point n)
                (string-append sign digits (make-string (- point n) #\0) ".0"))
               (else
                (string-append sign (substring digits 0 point) "."
                               (substring digits point)))))
             (else
              (let ((e (- point 1)))
                (string-append sign
                               (if (> n 1)
                                   (string-append (substring digits 0 1) "."
                                                  (substring digits 1))
                                   digits)
                               (if (< e 0) "e-" "e+")
                               (if (< (abs e) 10) "0" "")
                               (number->string (abs e)))))))))))))

(define (hex2 n)
  "RETURN: string, 'n' (0..255) as two lower-case hexadecimal digits."
  (let ((text (number->string n 16)))
    (if (< n 16) (string-append "0" text) text)))

(define (printable? c)
  "RETURN: #t, where Python's 'str.isprintable' holds for the character 'c'
-- every character but the categories Other (Cc, Cf, Cs, Co, Cn) and
Separator (Zl, Zp, Zs), the blank excepted; #f else."
  (or (char=? c #\space)
      (not (memq (char-general-category c) '(Cc Cf Cs Co Cn Zl Zp Zs)))))

(define (quote-of has-single? has-double?)
  "RETURN: char, the quote Python's repr chooses: the double quote where the
text holds a single quote and no double one, the single quote else."
  (if (and has-single? (not has-double?)) #\" #\'))

(define (py-str-repr text)
  "RETURN: string, the string 'text' as Python's 'repr(str)' writes it --
in Python's choice of quotes, the backslash, that quote, '\\n', '\\t', '\\r'
escaped, what does not print as '\\xNN', '\\uNNNN' or '\\UNNNNNNNN', every
printable character, ASCII or not, as it stands."
  (let ((quote (quote-of (string-index text #\') (string-index text #\"))))
    (string-append
     (string quote)
     (string-concatenate
      (map (lambda (c)
             (let ((n (char->integer c)))
               (cond ((char=? c #\\)     "\\\\")
                     ((char=? c quote)   (string #\\ quote))
                     ((char=? c #\newline) "\\n")
                     ((char=? c #\tab)   "\\t")
                     ((char=? c #\return) "\\r")
                     ((printable? c)     (string c))
                     ((< n #x100)        (string-append "\\x" (hex2 n)))
                     ((< n #x10000)
                      (string-append "\\u" (string-pad (number->string n 16) 4 #\0)))
                     (else
                      (string-append "\\U" (string-pad (number->string n 16) 8 #\0))))))
           (string->list text)))
     (string quote))))

(define (py-bytes-repr data)
  "RETURN: string, the bytevector 'data' as Python's 'repr(bytes)' writes it
-- \"b'\\x1b[A'\": printable ASCII as it stands, '\\t', '\\n', '\\r', the
backslash and the chosen quote escaped, every other byte as '\\xNN'."
  (let* ((byte-list (bytevector->u8-list data))
         (quote     (quote-of (memv 39 byte-list) (memv 34 byte-list))))
    (string-append
     "b" (string quote)
     (string-concatenate
      (map (lambda (n)
             (cond ((= n 92)                     "\\\\")
                   ((= n (char->integer quote))  (string #\\ quote))
                   ((= n 10)                     "\\n")
                   ((= n 9)                      "\\t")
                   ((= n 13)                     "\\r")
                   ((or (< n 32) (>= n 127))     (string-append "\\x" (hex2 n)))
                   (else                         (string (integer->char n)))))
           byte-list))
     (string quote))))

(define (py-repr value)
  "RETURN: string, 'value' as Python's 'repr' writes the value it stands for:
a string as 'str', a bytevector as 'bytes', #t/#f as True/False, the symbol
'null' as None, an exact integer as 'int', an inexact real as 'float', a
vector as a tuple, a list as a list, a pair (a . b) as the tuple (a, b);
anything else as Guile writes it."
  (cond ((string? value)               (py-str-repr value))
        ((bytevector? value)           (py-bytes-repr value))
        ((boolean? value)              (py-bool value))
        ((eq? value 'null)             "None")
        ((and (integer? value) (exact? value)) (number->string value))
        ((and (real? value) (inexact? value))  (py-float-repr value))
        ((vector? value)               (py-tuple-repr (vector->list value)))
        ((list? value)                 (py-list-repr value))
        ((pair? value)                 (py-tuple-repr (list (car value) (cdr value))))
        (else                          (object->string value))))

(define (py-str value)
  "RETURN: string, 'value' as Python's 'str' writes it: a string as it
stands, everything else as 'py-repr' writes it."
  (if (string? value) value (py-repr value)))

(define (py-join separator item-list)
  "RETURN: string, the strings of 'item-list' joined by 'separator' --
Python's 'separator.join(item_list)'."
  (string-join item-list separator))

(define (py-list-repr item-list)
  "RETURN: string, 'item-list' as Python prints a list: '[a, b]', every item
by 'py-repr'."
  (string-append "[" (py-join ", " (map py-repr item-list)) "]"))

(define (py-tuple-repr item-list)
  "RETURN: string, 'item-list' as Python prints a tuple: '()', \"('a',)\" for
one item (the comma Python writes), \"('a', 'b')\"; every item by 'py-repr'."
  (cond ((null? item-list)       "()")
        ((null? (cdr item-list)) (string-append "(" (py-repr (car item-list)) ",)"))
        (else (string-append "(" (py-join ", " (map py-repr item-list)) ")"))))

(define (py-ljust text width)
  "RETURN: string, 'text' padded with blanks on the right to 'width'
characters -- Python's '%-<width>s'; 'text' itself where it is as long."
  (if (>= (string-length text) width)
      text
      (string-append text (make-string (- width (string-length text)) #\space))))

(define (py-rjust text width)
  "RETURN: string, 'text' padded with blanks on the left to 'width'
characters -- Python's '%<width>s'; 'text' itself where it is as long."
  (if (>= (string-length text) width)
      text
      (string-append (make-string (- width (string-length text)) #\space) text)))
