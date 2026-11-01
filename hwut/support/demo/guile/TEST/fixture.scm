#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; _____________________________________________________________________________
;; THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
;;
;;     fixture.scm open            a fresh 'TMP/shop.db', stocked as below, and
;;                                 an empty 'TMP/frame.log' ('on_entry', and
;;                                 'hwut.execute fixture open')
;;     fixture.scm close           both removed ('on_exit')
;;     fixture.scm check <when> <app> [<choice>]
;;                                 'when' is 'before' or 'after': whether the
;;                                 stock adds up around the test run '<app>
;;                                 <choice>', appended to 'TMP/frame.log'
;;                                 ('on_before_test', 'on_after_test')
;;
;; 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
;; which hwut sets for the run the check stands around; a test without
;; choices has none. 'check' concerns the shop's tests alone. The stock
;; ADDS UP where every item's quantity is its opening quantity plus every
;; movement of the journal.
;; _____________________________________________________________________________
(load "shop-db.scm")

(define HERE          (dirname (canonicalize-path (current-filename))))
(define DB-PATH       (string-append HERE "/TMP/shop.db"))
(define LOG-PATH      (string-append HERE "/TMP/frame.log"))
(define OPENING-LIST  '(("apple" . 10) ("pear" . 5) ("plum" . 5)))
(define SHOP-TEST-SET '("delivery.json" "shop.scm"))

(define (remove-if-there path)
  "RETURN: unspecified. 'path' is gone, whether it stood or not."
  (when (file-exists? path) (delete-file path)))

(define (open-shop)
  "RETURN: unspecified. Writes a fresh, stocked database and an empty log."
  (unless (file-exists? (dirname DB-PATH)) (mkdir (dirname DB-PATH)))
  (for-each remove-if-there (list DB-PATH LOG-PATH))
  (let ((db (db-open DB-PATH)))
    (db-exec db "BEGIN")
    (db-exec db "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)")
    (db-exec db "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)")
    (db-exec db "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)")
    (for-each (lambda (entry)
                (db-exec db "INSERT INTO opening VALUES (?, ?)" (car entry) (cdr entry))
                (db-exec db "INSERT INTO stock   VALUES (?, ?)" (car entry) (cdr entry)))
              OPENING-LIST)
    (db-exec db "COMMIT")
    (db-close db))
  (close-port (open-output-file LOG-PATH)))

(define (close-shop)
  "RETURN: unspecified. Removes the database and the log."
  (for-each remove-if-there (list DB-PATH LOG-PATH)))

(define (adds-up?)
  "RETURN: #t, if every item's stock is its opening quantity plus its
journal's movements; #f, else."
  (let* ((db       (db-open DB-PATH))
         (row-list (db-exec db (string-append
                                "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty"
                                "  FROM opening o JOIN stock s ON s.item = o.item"
                                "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item"))))
    (db-close db)
    (every (lambda (row) (equal? (cadr row) (caddr row))) row-list)))

(define* (check moment test #:optional (choice ""))
  "RETURN: unspecified. Appends one line to the log for a shop test run."
  (when (member test SHOP-TEST-SET)
    (let ((run  (string-trim-both (string-append test " " choice)))
          (port (open-file LOG-PATH "a")))
      (display (string-append (string-pad-right moment (max 6 (string-length moment))) " "
                              (string-pad-right run (max 15 (string-length run))) " "
                              (if (adds-up?) "stock adds up" "STOCK BROKEN") "\n")
               port)
      (close-port port))))

(let* ((argv    (cdr (command-line)))
       (command (if (pair? argv) (car argv) "")))
  (cond ((string=? command "open")  (open-shop))
        ((string=? command "close") (close-shop))
        ((and (string=? command "check") (<= 3 (length argv) 4))
         (apply check (cdr argv)))
        (else
         (display "usage: fixture.scm open | close | check before|after <app> <choice>\n"
                  (current-error-port))
         (exit 2))))
