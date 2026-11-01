;; shop-db.scm -- SQLITE FROM SCHEME, as much as the shop needs; no test.
;;
;; Loaded by 'shop.scm' and 'fixture.scm' ('(load "shop-db.scm")'). Guile has
;; no SQLite binding of its own, and the demonstration installs nothing: the
;; C library 'libsqlite3.so.0' is called through '(system foreign)'.
;;
;;     (db-open path)                      a connection; #:trace? logs on stderr
;;     (db-exec db sql arg ...)            one statement; its rows, as lists
;;     (db-close db)
;;
;; Arguments bind to '?' in order: an exact integer as INTEGER, a string as
;; TEXT. A column reads back as an exact integer, a string, or #f for NULL.
;; A failing statement raises 'sqlite-error' with SQLite's own message.
(use-modules (system foreign) (system foreign-library) (rnrs bytevectors) (srfi srfi-1))

(define sqlite-library
  (or (false-if-exception (load-foreign-library "libsqlite3.so.0"))
      (load-foreign-library "libsqlite3")))

(define (sqlite-function name return-type argument-types)
  "RETURN: procedure, the C function 'name' of libsqlite3."
  (pointer->procedure return-type (foreign-library-pointer sqlite-library name) argument-types))

(define %open        (sqlite-function "sqlite3_open_v2"      int   (list '* '* int '*)))
(define %close       (sqlite-function "sqlite3_close_v2"     int   (list '*)))
(define %busy        (sqlite-function "sqlite3_busy_timeout" int   (list '* int)))
(define %errmsg      (sqlite-function "sqlite3_errmsg"       '*    (list '*)))
(define %prepare     (sqlite-function "sqlite3_prepare_v2"   int   (list '* '* int '* '*)))
(define %bind-int    (sqlite-function "sqlite3_bind_int64"   int   (list '* int int64)))
(define %bind-text   (sqlite-function "sqlite3_bind_text"    int   (list '* int '* int '*)))
(define %step        (sqlite-function "sqlite3_step"         int   (list '*)))
(define %column-n    (sqlite-function "sqlite3_column_count" int   (list '*)))
(define %column-type (sqlite-function "sqlite3_column_type"  int   (list '* int)))
(define %column-int  (sqlite-function "sqlite3_column_int64" int64 (list '* int)))
(define %column-text (sqlite-function "sqlite3_column_text"  '*    (list '* int)))
(define %finalize    (sqlite-function "sqlite3_finalize"     int   (list '*)))

(define SQLITE-ROW       100)
(define SQLITE-DONE      101)
(define SQLITE-INTEGER   1)
(define SQLITE-NULL      5)
(define OPEN-READ-WRITE  #x2)
(define OPEN-CREATE      #x4)
(define SQLITE-TRANSIENT (make-pointer (- (expt 2 64) 1)))   ; (void *) -1: copy the text

;;  A connection: the C handle, and whether its statements are logged.
(define (db-handle db) (car db))
(define (db-trace? db) (cdr db))

(define (sqlite-fail db what)
  "RETURN: never; raises 'sqlite-error' with 'what' and SQLite's message."
  (throw 'sqlite-error (string-append what ": " (pointer->string (%errmsg (db-handle db))))))

(define* (db-open path #:key (trace? #f) (timeout-s 10))
  "RETURN: connection to the SQLite database 'path' (created where it does
not stand), waiting up to 'timeout-s' for a lock another writer holds;
'trace?' logs every statement on stderr as 'sql: <statement>'."
  (let* ((box (make-bytevector (sizeof '*) 0))
         (rc  (%open (string->pointer path) (bytevector->pointer box)
                     (logior OPEN-READ-WRITE OPEN-CREATE) %null-pointer))
         (db  (cons (dereference-pointer (bytevector->pointer box)) trace?)))
    (unless (= rc 0) (sqlite-fail db (string-append "open " path)))
    (%busy (db-handle db) (* 1000 timeout-s))
    db))

(define (db-close db)
  "RETURN: unspecified. The connection is closed."
  (%close (db-handle db)))

(define (column-value statement i)
  "RETURN: the value of column 'i' of the current row: exact integer,
string, or #f for NULL."
  (let ((type (%column-type statement i)))
    (cond ((= type SQLITE-NULL)    #f)
          ((= type SQLITE-INTEGER) (%column-int statement i))
          (else                    (pointer->string (%column-text statement i) -1 "UTF-8")))))

(define (db-exec db sql . argument-list)
  "RETURN: list of rows (each a list of column values), every row the one
statement 'sql' yields with 'argument-list' bound to its '?' in order; '()
for a statement that yields none. Raises 'sqlite-error' where it fails."
  (when (db-trace? db)
    (let ((err (current-error-port)))
      (display (string-append "sql: " sql "\n") err)
      (force-output err)))
  (let* ((box (make-bytevector (sizeof '*) 0))
         (rc  (%prepare (db-handle db) (string->pointer sql "UTF-8") -1
                        (bytevector->pointer box) %null-pointer)))
    (unless (= rc 0) (sqlite-fail db sql))
    (let ((statement (dereference-pointer (bytevector->pointer box))))
      (dynamic-wind
        (lambda () #f)
        (lambda ()
          (fold (lambda (value i)
                  (if (string? value)
                      (%bind-text statement i (string->pointer value "UTF-8") -1 SQLITE-TRANSIENT)
                      (%bind-int statement i value))
                  (+ i 1))
                1 argument-list)
          (let loop ((row-list '()))
            (let ((rc (%step statement)))
              (cond ((= rc SQLITE-ROW)
                     (loop (cons (map (lambda (i) (column-value statement i))
                                      (iota (%column-n statement)))
                                 row-list)))
                    ((= rc SQLITE-DONE) (reverse row-list))
                    (else               (sqlite-fail db sql))))))
        (lambda () (%finalize statement))))))
