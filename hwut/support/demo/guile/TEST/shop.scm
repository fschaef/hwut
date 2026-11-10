#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; @hwut {
;;     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
;;     tolerance { stderr_ignored = true }
;;     choices {
;;         sell   { features = ["demo-guile+cover-unordered-table", "demo-guile+cover-stderr-ignored", "demo-guile+cover-collision"] }
;;         report { features = ["demo-guile+cover-output-file", "demo-guile+cover-keyed-table-separator", "demo-guile+cover-dependency",
;;                              "demo-guile+cover-frame-scripts", "demo-guile+cover-test-scripts", "demo-guile+cover-stderr-ignored"]
;;                  output   = ["<stdout>", "stock.csv"] }
;;     }
;; }
;;
;; _____________________________________________________________________________
;; SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
;;          comes in, three clerks sell at once, and the stock is reported.
;; REQUIREMENT  Every movement of the stock is journalled, so that the stock
;;              always ADDS UP: opening quantity plus the journal's movements.
;;
;; THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
;; this file, read it first: 'on_entry'/'on_exit' and 'on_before_test'/
;; 'on_after_test' call 'fixture.scm'; 'apps' makes 'delivery.json' a test
;; ('execute' calls 'shop.scm deliver delivery.json'); 'collision' keeps it
;; and 'shop.scm sell' apart; 'dependency' runs 'shop.scm report' after both.
;; '../../python/TEST/shop.py' says each at length.
;;
;; STDERR  Every SQL statement is logged on stderr, as a server would; the
;; header's 'stderr_ignored = true' says the words there are no error.
;;
;; SQLite is reached through 'shop-db.scm' (libsqlite3 by '(system foreign)');
;; the clerks of 'sell' are Guile threads, each with a connection of its own.
;;
;; CHOICES
;; sell     three clerks sell at once; the sales print as '##! table
;;          unordered sep={;}'.
;; report   the stock, as '##! table key=0 sep={;}', and the same rows written
;;          to 'stock.csv' ('output'); then the frame log of the shop's tests.
;; deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
;;          delivery note in one transaction.
;; _____________________________________________________________________________
(use-modules (ice-9 threads) (ice-9 rdelim) (srfi srfi-1))
(load "shop-db.scm")

(define HERE     (dirname (canonicalize-path (current-filename))))
(define DB-PATH  (string-append HERE "/TMP/shop.db"))
(define LOG-PATH (string-append HERE "/TMP/frame.log"))

;;  What each clerk sells, one item per sale.
(define CLERK-LIST '(("anna"  "apple" "apple" "pear")
                     ("ben"   "apple" "plum")
                     ("chloe" "apple")))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stdout."
  (display (string-concatenate text-list))
  (newline))

(define (complain . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stderr."
  (display (string-append (string-concatenate text-list) "\n") (current-error-port)))

(define (connect)
  "RETURN: connection to the shop's database, every statement it executes
logged on stderr. Exits 1 where the database does not stand: 'on_entry'
writes it."
  (unless (file-exists? DB-PATH)
    (complain "shop.scm: no " DB-PATH " -- 'on_entry' writes it; by hand: "
              "'hwut.execute fixture open'")
    (exit 1))
  (db-open DB-PATH #:trace? #t #:timeout-s 10))

;;  ------------------------------------------------------------------- JSON
(define (json-read port)
  "RETURN: the JSON value read from 'port': an object as an association list
of key and value, an array as a list, a string, a number, #t, #f or 'null."
  (define (skip) (let ((c (peek-char port)))
                   (when (and (char? c) (char-whitespace? c)) (read-char port) (skip))))
  (define (expect text) (string-for-each (lambda (c) (unless (eqv? c (read-char port))
                                                       (error "json: expected" text)))
                                         text))
  (define (members close item)       ; RETURN: list of items up to 'close'
    (skip)
    (if (eqv? (peek-char port) close)
        (begin (read-char port) '())
        (let loop ((result (list (item))))
          (skip)
          (let ((c (read-char port)))
            (cond ((eqv? c #\,)   (loop (cons (item) result)))
                  ((eqv? c close) (reverse result))
                  (else           (error "json: unexpected" c)))))))
  (define (string-value)
    (read-char port)
    (let loop ((chars '()))
      (let ((c (read-char port)))
        (cond ((eqv? c #\") (list->string (reverse chars)))
              ((eqv? c #\\) (let ((e (read-char port)))
                              (loop (cons (case e ((#\n) #\newline) ((#\t) #\tab) (else e)) chars))))
              (else         (loop (cons c chars)))))))
  (define (value)
    (skip)
    (let ((c (peek-char port)))
      (cond ((eqv? c #\{) (read-char port)
                          (members #\} (lambda ()
                                         (skip)
                                         (let ((key (string-value)))
                                           (skip) (expect ":")
                                           (cons key (value))))))
            ((eqv? c #\[) (read-char port) (members #\] value))
            ((eqv? c #\") (string-value))
            ((eqv? c #\t) (expect "true")  #t)
            ((eqv? c #\f) (expect "false") #f)
            ((eqv? c #\n) (expect "null")  'null)
            (else (let loop ((chars '()))
                    (let ((c (peek-char port)))
                      (if (and (char? c) (string-index "+-0123456789.eE" c))
                          (loop (cons (read-char port) chars))
                          (string->number (list->string (reverse chars))))))))))
  (value))

;;  ------------------------------------------------------------- the choices
(define (move db item delta source)
  "RETURN: unspecified. Changes the stock of 'item' by 'delta' and journals
it, in one transaction."
  (db-exec db "BEGIN IMMEDIATE")
  (db-exec db "UPDATE stock SET qty = qty + ? WHERE item = ?" delta item)
  (db-exec db "INSERT INTO journal VALUES (?, ?, ?)" item delta source)
  (db-exec db "COMMIT"))

(define (deliver path)
  "RETURN: unspecified. Books the delivery note in 'path' and prints it."
  (let* ((note      (call-with-input-file path json-read))
         (line-list (assoc-ref note "lines"))
         (db        (connect)))
    (db-exec db "BEGIN IMMEDIATE")
    (for-each (lambda (line)
                (db-exec db "UPDATE stock SET qty = qty + ? WHERE item = ?"
                         (assoc-ref line "qty") (assoc-ref line "item"))
                (db-exec db "INSERT INTO journal VALUES (?, ?, ?)"
                         (assoc-ref line "item") (assoc-ref line "qty") (assoc-ref note "note")))
              line-list)
    (db-exec db "COMMIT")
    (say "delivery note " (assoc-ref note "note") " from " (assoc-ref note "supplier") ":")
    (for-each (lambda (line)
                (say "    " (string-pad-right (assoc-ref line "item") 6)
                     " +" (number->string (assoc-ref line "qty"))))
              line-list)))

(define (sell)
  "RETURN: unspecified. Three clerks sell at once; prints every sale."
  (let* ((lock       (make-mutex))
         (sale-list  '())
         (error-list '())
         (clerk      (lambda (name item-list)
                       (catch #t
                         (lambda ()
                           (let ((db (connect)))
                             (for-each (lambda (item)
                                         (move db item -1 name)
                                         (with-mutex lock
                                           (set! sale-list (cons (string-append item ";1") sale-list))))
                                       item-list)
                             (db-close db)))
                         (lambda (key . args)
                           (with-mutex lock
                             (set! error-list (cons (string-append name ": " (format #f "~a ~s" key args))
                                                    error-list))))))))
    (db-close (connect))
    (for-each join-thread
              (map (lambda (entry) (call-with-new-thread (lambda () (clerk (car entry) (cdr entry)))))
                   CLERK-LIST))
    (unless (null? error-list)
      (complain "shop.scm: a sale failed -- " (string-join (reverse error-list) "; "))
      (exit 1))
    (say "sales, item;qty -- in the order the clerks booked them:")
    (say "##! table unordered sep={;}")
    (for-each say (reverse sale-list))
    (say "####")))

(define (read-lines path)
  "RETURN: list of strings, the lines of the file 'path', right-trimmed."
  (call-with-input-file path
    (lambda (port)
      (let loop ((result '()))
        (let ((line (read-line port)))
          (if (eof-object? line) (reverse result) (loop (cons (string-trim-right line) result))))))))

(define (report)
  "RETURN: unspecified. Prints the stock and the frame log; writes 'stock.csv'."
  (let* ((db       (connect))
         (row-list (db-exec db "SELECT item, qty FROM stock ORDER BY qty, item"))
         (row-text (lambda (row) (string-append (car row) ";" (number->string (cadr row))))))
    (call-with-output-file (string-append HERE "/stock.csv")
      (lambda (port)
        (display "item;qty\n" port)
        (for-each (lambda (row) (display (string-append (row-text row) "\n") port))
                  (sort row-list (lambda (a b) (string<? (car a) (car b)))))))
    (say "stock, item;qty (also written to stock.csv):")
    (say "##! table key=0 sep={;}")
    (for-each (lambda (row) (say (row-text row))) row-list)
    (say "####")
    (let* ((line-list (read-lines LOG-PATH))
           (own?      (lambda (line) (string-contains line "shop.scm report"))))
      (say "the frame, around the delivery and the sale:")
      (say "##! potpourri")
      (for-each say (remove own? line-list))
      (say "####")
      (for-each say (filter own? line-list)))))

(let* ((argv    (cdr (command-line)))
       (command (if (pair? argv) (car argv) "")))
  (cond ((and (string=? command "deliver") (= (length argv) 2)) (deliver (cadr argv)))
        ((string=? command "sell")    (sell))
        ((string=? command "report")  (report))
        (else (say "choices: sell, report")
              (exit 1)))
  (say "<hwut-end>"))
