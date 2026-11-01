;; @hwut {
;;     title      = "HOCON parser: subset (A), annotated tree"
;;     choices {
;;         comments  { features = ["guile-hocon"] }
;;         faults    { features = ["guile-hocon"] }
;;         fuzz      { features = ["guile-hocon"] }
;;         numbers   { features = ["guile-hocon"] }
;;         oneline   { features = ["guile-hocon"] }
;;         positions { features = ["guile-hocon"] }
;;         quoting   { features = ["guile-hocon"] }
;;         refused   { features = ["guile-hocon"] }
;;         scalars   { features = ["guile-hocon"] }
;;         structure { features = ["guile-hocon"] }
;;         triple    { features = ["guile-hocon"] }
;;         unclosed  { features = ["guile-hocon"] }
;;     }
;;     interactive = true
;; }
;;
;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;; _____________________________________________________________________________
;;
;; PURPOSE: The Guile port of 'python/TEST/test-hwut_hocon.py', choice for
;;          choice, held against its GOOD files by '.link'. The tree is an
;;          s-expression; 'show' takes it apart with '(ice-9 match)'.
;; _____________________________________________________________________________
(add-to-load-path (string-append (dirname (canonicalize-path (current-filename))) "/.."))
(use-modules (hwut runner) (hwut pytext) (hwut hocon) (hwut deterministic-random)
             (ice-9 match))

(define (banner label)
  "RETURN: unspecified. Section heading."
  (display (string-append "\n--- " label " ---\n")))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline."
  (display (string-concatenate text-list))
  (newline))

(define* (lines text #:optional (line-offset 0) (column-offset 0))
  "RETURN: list of source lines, 'text' split at '\\n', offsets applied
uniformly."
  (let loop ((rest (string-split text #\newline)) (i 1) (result '()))
    (if (null? rest)
        (reverse result)
        (loop (cdr rest) (+ i 1)
              (cons (make-source-line (car rest) (+ i line-offset) column-offset) result)))))

(define (type-name value)
  "RETURN: string, the name of the Python type the scalar 'value' stands for."
  (cond ((string? value)  "str")
        ((boolean? value) "bool")
        ((eq? value 'null) "NoneType")
        ((exact? value)   "int")
        (else             "float")))

(define* (show node #:optional (indent 0))
  "RETURN: unspecified. Prints the annotated tree, positions included."
  (let ((pad (make-string (* 4 indent) #\space))
        (at  hocon-position->string))
    (match node
      (('object position entry ...)
       (say pad "{ at " (at position))
       (for-each (match-lambda
                   (('entry key key-position value)
                    (say pad "  key '" key "' at " (at key-position) " ->")
                    (show value (+ indent 1))))
                 entry)
       (say pad "}"))
      (('list position item ...)
       (say pad "[ at " (at position))
       (for-each (lambda (i) (show i (+ indent 1))) item)
       (say pad "]"))
      (('scalar position value)
       (say pad (py-repr value) " (" (type-name value) ") at " (at position))))))

(define* (run label text #:optional (line-offset 0) (column-offset 0))
  "RETURN: unspecified. Parses 'text' and prints tree and faults."
  (banner label)
  (call-with-values (lambda () (hocon-parse (lines text line-offset column-offset) "f.hocon"))
    (lambda (document fault-list)
      (show document)
      (for-each (lambda (f) (say "FAULT " (hocon-fault->string f))) fault-list))))

(define (test-scalars)
  "RETURN: unspecified. Every scalar shape."
  (run "scalars"
       (string-append "a = bare\n"
                      "b = \"quoted \\\"x\\\" and \\n\"\n"
                      "c = 42\n"
                      "d = -3.14\n"
                      "e = 1e-6\n"
                      "f = true\n"
                      "g = no\n"
                      "h = make %.exe\n"
                      "i: \"colon-bound\"\n"
                      "j = null\n"
                      "k = nihil\n"
                      "l =\n")))

(define (test-numbers)
  "RETURN: unspecified. Every radix, the helper, and the split sign."
  (run "decimal, with sign and exponent" "a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n")
  (run "the visual helper enters no value" "a = 1_000\nb = 7_000.5_5\n")
  (run "hexadecimal, binary, octal"
       "a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n")
  (run "roman" "a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n")
  (run "a sign standing apart from its digits" "a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n")
  (run "what spells no number is a string, and carries quotes"
       "a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n")
  (run "no arithmetic: this language computes nothing" "a = 5 - 1\n"))

(define (test-quoting)
  "RETURN: unspecified. The quoted string, and the unquoted word."
  (run "quoted: blanks, comment markers and binders are content"
       "a = \"make %.exe\"\nb = \"not # a comment\"\nc = \"x = y\"\nd = \"yes\"\n")
  (run "unquoted: refused, and shown in the quotes it wants"
       "a = make\nb = strip.pype\nc = [one, two]\nd = 1\n"))

(define (test-structure)
  "RETURN: unspecified. Objects, lists, nesting."
  (run "nesting and key-brace"
       "outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n")
  (run "lists"
       (string-append "commas   = [one, two, three]\n"
                      "newlines = [\n    1\n    2\n]\n"
                      "objects  = [ { a = 1 }, { a = 2 } ]\n"
                      "empty    = []\n")))

(define (test-oneline)
  "RETURN: unspecified. Entries sharing a line, without commas."
  (run "two entries, one line, no comma" "caps { timeout_sec = 30  network = false }\n")
  (run "a quoted value with blanks, beside a following key"
       "a { build = \"make %.exe\"  timeout_sec = 5 }\n")
  (run "three entries, one line" "x { a = 1  b = \"two\"  c = { d = 3 } }\n"))

(define (test-comments)
  "RETURN: unspecified. Both comment forms, whole-line and trailing."
  (run "comments"
       (string-append "# whole line\n"
                      "a = 1   # trailing\n"
                      "// slashes too\n"
                      "b = 2   // trailing slashes\n"
                      "c = bare value # comment cut\n")))

(define (test-refused)
  "RETURN: unspecified. The three constructs that do not exist here."
  (run "refused, each by name"
       "include \"other.conf\"\na = ${outside.value}\nb += appended\nd = survives\n"))

(define (test-triple)
  "RETURN: unspecified. The text of several lines."
  (let ((q "\"\"\""))
    (run "several lines: indentation and blank ends go"
         (string-append "doc = " q "\n"
                        "    First line.\n"
                        "\n"
                        "      indented more\n"
                        "    last line\n"
                        "    " q "\n"
                        "after = 1\n"))
    (run "on one line; beside another entry; in a list"
         (string-append "a = " q "one line" q "  b = 2\n"
                        "c = [" q "x" q ", \"y\"]\n"))
    (run "as written: a quote, a backslash-n, a comment marker"
         (string-append "a = " q "says \"no\" \\n # not a comment" q "\n"))
    (run "never closed: a fault, at its beginning"
         (string-append "a = 1\nb = " q "open\nc = 2\n"))))

(define (test-faults)
  "RETURN: unspecified. Faults accumulate; the parse completes."
  (run "faults accumulate" "a = 1\na = 2\nb = \"unterminated\n}\nc {\n    d = 3\n"))

(define (test-unclosed)
  "RETURN: unspecified. A list whose ']' was forgotten ENDS."
  (run "a list closed by the object's brace" "@hwut { title = \"B\" choices = [ }\nafter = 1\n")
  (run "a stray character in a list" "a = [1, ; 2]\n"))

(define FUZZ-SEED-VECTOR
  (vector
   (string-append "@hwut {\n"
                  "    title    = \"T\"\n"
                  "    choices  = [\"a\", \"b\"]\n"
                  "    tolerance { eq_pattern = [\"x.*\"] }\n"
                  "    n        = -1.5e3\n"
                  "    f        = true\n"
                  "}\n")
   (string-append "hwut {\n"
                  "    target     { clean = \"./c.sh\" }\n"
                  "    dependency { \"a.py\" = [\"b.py one\"] }\n"
                  "    ignore     = [\"x\"]   // comment\n"
                  "    # comment\n"
                  "}\n")))
;;  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few
;;  that it refuses by name, and some ordinary ones.
(define FUZZ-ALPHABET
  (list->vector (append (map string (string->list "{}[]\",=:#/\\$ \n\t-+.eE0a"))
                        '("\"\"\"" "${" "//" "+="))))
(define FUZZ-INPUT-N 3000)
(define FUZZ-BOUND-US 500000)            ; one parse takes well under a millisecond

(define (slice text i j)
  "RETURN: string, Python's 'text[i:j]' for 0 <= i, j: clamped to the text."
  (let ((n (string-length text)))
    (substring text (min i n) (max (min i n) (min j n)))))

(define (mutated stream text)
  "RETURN: string, 'text' edited by one to four random insertions,
deletions and duplications of a short stretch -- the stream consumed as the
Python test consumes it."
  (let loop ((k (stream-next-int stream 1 4)) (text text))
    (if (zero? k)
        text
        (let* ((n (string-length text))
               (i (stream-next-int stream 0 n)))
          (loop (- k 1)
                (case (stream-next-int stream 0 2)
                  ((0) (string-append (slice text 0 i) (stream-select stream FUZZ-ALPHABET)
                                      (slice text i n)))
                  ((1) (string-append (slice text 0 i) (slice text (+ i 1) n)))
                  (else
                   (let ((j (stream-next-int stream 0 n)))
                     (string-append (slice text 0 i) (slice text j (+ j 5))
                                    (slice text i n))))))))))

(define (test-fuzz)
  "RETURN: unspecified. Every mutated header ends and answers faults: a
parse past FUZZ-BOUND-US is cut by SIGALRM and counted a hang."
  (sigaction SIGALRM (lambda (signal) (throw 'hang)))
  (let ((stream (make-deterministic-stream 4711))
        (tally  (list (cons "clean" 0) (cons "with faults" 0) (cons "hang" 0) (cons "exception" 0)))
        (example '()))
    (define (count! key) "RETURN: unspecified; the tally of 'key' one higher." (let ((p (assoc key tally))) (set-cdr! p (+ (cdr p) 1))))
    (do ((k 0 (+ k 1))) ((= k FUZZ-INPUT-N))
      (let ((text (mutated stream (stream-select stream FUZZ-SEED-VECTOR))))
        (catch #t
          (lambda ()
            (setitimer ITIMER_REAL 0 0 0 FUZZ-BOUND-US)
            (call-with-values (lambda () (hocon-parse (lines text) "f.hocon"))
              (lambda (document fault-list)
                (setitimer ITIMER_REAL 0 0 0 0)
                (count! (if (null? fault-list) "clean" "with faults")))))
          (lambda (key . args)
            (setitimer ITIMER_REAL 0 0 0 0)
            (if (eq? key 'hang)
                (begin (count! "hang")
                       (unless (assoc "hang" example)
                         (set! example (append example (list (cons "hang" text))))))
                (begin (count! "exception")
                       (unless (assoc "exception" example)
                         (set! example (append example
                                               (list (cons "exception"
                                                           (string-append (symbol->string key)
                                                                          ": " (object->string args)
                                                                          "\n" text))))))))))))
    (sigaction SIGALRM SIG_DFL)
    (banner (string-append (number->string FUZZ-INPUT-N) " mutated headers"))
    (for-each (lambda (p) (say "    " (py-ljust (car p) 12) " " (number->string (cdr p)))) tally)
    (for-each (lambda (p) (say "FIRST " (string-upcase (car p)) ":\n" (cdr p))) example)))

(define (test-positions)
  "RETURN: unspecified. Offsets carried: the same text reported at its place
in a larger file, as an unwrapped header would be."
  (let ((text "@hwut {\n    title = \"T\"\n}"))
    (run "plain: as its own file" text)
    (run "offset: same text, region begins at line 40, 3 columns stripped" text 39 3)))

(hwut-runner-run
 (make-hwut-runner (command-line) "HOCON parser: subset (A), annotated tree;"
                   `(("scalars"   . ,test-scalars)
                     ("numbers"   . ,test-numbers)
                     ("quoting"   . ,test-quoting)
                     ("structure" . ,test-structure)
                     ("oneline"   . ,test-oneline)
                     ("comments"  . ,test-comments)
                     ("refused"   . ,test-refused)
                     ("triple"    . ,test-triple)
                     ("unclosed"  . ,test-unclosed)
                     ("fuzz"      . ,test-fuzz)
                     ("faults"    . ,test-faults)
                     ("positions" . ,test-positions))))
