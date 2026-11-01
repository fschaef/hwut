;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
;;;          port of 'python/hwut_fsm.py' (read '../python/README-hwut_fsm.txt').
;;;          Every event the model does not allow, every forbidden state
;;;          entered, is WRITTEN as a line, so it lands in the GOOD file.
;;;
;;;     (define m (fsm-from-string "
;;;         initial: idle
;;;         forbidden: crashed
;;;         idle    ---( request )---> waiting ---( grant )---> busy
;;;         busy    ---( release )---> idle
;;;         :       ---( fault )--->   crashed"))
;;;     (fsm-fire! m "request" #:where 1)   ; #t
;;;     (fsm-fire! m "release" #:where 2)   ; BREACH line 2: 'release' in 'waiting' -- allowed: grant
;;;     (fsm-report m)
;;;
;;; THE MODEL IS AN S-EXPRESSION. The text is read into a list of statements
;;; -- the language's own data -- and the machine is built from that list;
;;; 'fsm->sexp' gives it back, 'fsm->string' writes it as text:
;;;
;;;     ((#:initial idle) (#:forbidden crashed) (#:final idle)
;;;      (idle request waiting grant busy)       ; a chain: state event state ...
;;;      (busy release idle) (busy fault crashed)
;;;      (#:state limbo))                        ; a state, no transition yet
;;;
;;; so a Scheme test may write the model as quoted data ('fsm-from-sexp')
;;; instead of text; states and events are strings in every other call.
;;;
;;; WHERE PYTHON TAKES KEYWORDS, keywords: '#:where' (an integer names a line,
;;; 'line 3'; a string stands as written; #f names no place), '#:state',
;;; '#:masked?', '#:start' (#f the initial state, 'now where it stands).
;;; Python's 'with m.disallowed(...)' is '(fsm-disallowed m event thunk)': the
;;; mask stands while 'thunk' runs, by 'dynamic-wind' -- lifted whatever way
;;; the thunk is left, and set again where a continuation re-enters it.
;;; Python's None is #f: 'fsm-path-to' answers #f where no path exists.
;;; FsmError is the exception type '&fsm-error' ('exception-message': the text).
;;;_____________________________________________________________________________
(define-module (hwut fsm)
  #:use-module (srfi srfi-1)
  #:use-module (srfi srfi-9)
  #:use-module (ice-9 exceptions)
  #:use-module (ice-9 q)
  #:export (&fsm-error fsm-error?
            make-fsm fsm? fsm-from-string fsm-from-sexp fsm->sexp fsm->string
            fsm-name fsm-initial fsm-state-list fsm-event-list fsm-breach-n
            fsm-reset! fsm-fire! fsm-forbidden
            fsm-disallow! fsm-allow! fsm-forbid! fsm-permit!
            fsm-disallowed fsm-forbidding
            fsm-state fsm-current fsm-in-state? fsm-can? fsm-allowed fsm-trace
            fsm-path-to fsm-state-reachable? fsm-unreachable fsm-dead-ends
            fsm-forbidden-reachable fsm-check fsm-report))

(define-exception-type &fsm-error &error make-fsm-error-condition fsm-error?)

(define (fsm-error . text-list)
  "RETURN: never; raises '&fsm-error' with the joined texts as its message."
  (raise-exception
   (make-exception (make-fsm-error-condition)
                   (make-exception-with-message (string-concatenate text-list)))))

(define (n->s n) "RETURN: string, the integer 'n' in decimal." (number->string n))

(define (quoted s)
  "RETURN: string, \"'s'\" -- a name as the messages quote it."
  (string-append "'" s "'"))

(define (sorted-strings lst)
  "RETURN: list of strings, 'lst' without duplicates, in code point order."
  (sort (delete-duplicates lst) string<?))

(define (pair<? a b)
  "RETURN: #t where the pair of strings 'a' sorts before 'b' -- by 'car',
then by 'cdr' (Python's order of tuples)."
  (or (string<? (car a) (car b))
      (and (string=? (car a) (car b)) (string<? (cdr a) (cdr b)))))

(define (list<? a b)
  "RETURN: #t where the list of strings 'a' sorts before 'b' element-wise."
  (cond ((null? a) (not (null? b)))
        ((null? b) #f)
        ((string<? (car a) (car b)) #t)
        ((string<? (car b) (car a)) #f)
        (else (list<? (cdr a) (cdr b)))))

;;  ------------------------------------------------------------ the record
(define-record-type <fsm>
  (%make-fsm name dfa? write edge-db initial model-forbidden final
             state-list event-list
             mask-db forbid-db permit-db current visit-db taken-db trace breach-n)
  fsm?
  (name            fsm-name)
  (dfa?            fsm-dfa?)
  (write           fsm-write)
  (edge-db         fsm-edge-db)              ; (state . event) -> sorted targets
  (initial         fsm-initial)
  (model-forbidden fsm-model-forbidden)      ; sorted list
  (final           fsm-final)                ; sorted list
  (state-list      fsm-state-list)           ; sorted, every state
  (event-list      fsm-event-list)           ; sorted, every event
  (mask-db         fsm-mask-db   set-fsm-mask-db!)    ; (state|#f . event) -> since
  (forbid-db       fsm-forbid-db set-fsm-forbid-db!)  ; state -> since
  (permit-db       fsm-permit-db set-fsm-permit-db!)  ; model-forbidden state -> since
  (current         fsm-current   set-fsm-current!)    ; sorted list of states
  (visit-db        fsm-visit-db  set-fsm-visit-db!)   ; state -> count
  (taken-db        fsm-taken-db  set-fsm-taken-db!)   ; (s e t) -> count
  (trace           fsm-trace-rev set-fsm-trace-rev!)
  (breach-n        fsm-breach-n  set-fsm-breach-n!))

(define (print-line line)
  "RETURN: unspecified. 'line' and a newline on the current output port."
  (display line) (newline))

(define* (make-fsm transitions initial #:key (forbidden '()) (final '()) (dfa? #t)
                   (name "fsm") (write print-line) (states '()))
  "RETURN: fsm, standing in 'initial', if success; raises '&fsm-error', else
-- a DFA with two transitions for one (state, event); a forbidden or final
state no transition names.

'transitions' is a list of (state event state) lists; 'states' names states
no transition touches (yet); 'write' takes one line -- every breach and
report goes through it."
  (let ((edge-db   (make-hash-table))
        (state-set (cons initial states)))
    (for-each
     (lambda (t)
       (let* ((source (car t)) (event (cadr t)) (target (caddr t))
              (key    (cons source event))
              (have   (hash-ref edge-db key '())))
         (when (and dfa? (pair? have) (not (member target have)))
           (fsm-error (quoted source) " --(" event ")--> " (quoted (car have))
                      " and " (quoted target) ": a DFA moves one way per event -- "
                      "or 'DFA=False'"))
         (hash-set! edge-db key (sorted-strings (cons target have)))
         (set! state-set (cons* source target state-set))))
     transitions)
    (let ((model-forbidden (sorted-strings forbidden))
          (final           (sorted-strings final)))
      (for-each
       (lambda (label chosen)
         (let ((unknown (filter (lambda (s) (not (member s state-set))) chosen)))
           (unless (null? unknown)
             (fsm-error label " state(s) " (string-join (map quoted unknown) ", ")
                        ": named nowhere else in the model"))))
       '("forbidden" "final") (list model-forbidden final))
      (let ((m (%make-fsm name dfa? write edge-db initial model-forbidden final
                          (sorted-strings (append state-set model-forbidden))
                          (sorted-strings (hash-map->list (lambda (k v) (cdr k)) edge-db))
                          #f #f #f #f #f #f #f 0)))
        (fsm-reset! m)
        m))))

;;  ------------------------------------------------------- the model as data
(define (word x)
  "RETURN: string, the name 'x' stands for -- a symbol's name, or 'x'."
  (if (symbol? x) (symbol->string x) x))

(define* (fsm-from-sexp sexp #:key (dfa? #t) (name "fsm") (write print-line))
  "RETURN: fsm, the model the statements of 'sexp' state, if success;
raises '&fsm-error', else. A statement is (#:initial A), (#:forbidden X Y
...), (#:final A B ...), (#:state A), or a chain (A ev B ev2 C ...); names
are symbols or strings. Where no '#:initial' stands, the first state named
is the initial one."
  (let loop ((rest sexp) (triples '()) (states '()) (declared '()) (first #f))
    (if (pair? rest)
        (let ((statement (car rest)))
          (if (keyword? (car statement))
              (let ((key       (keyword->symbol (car statement)))
                    (name-list (map word (cdr statement))))
                (if (eq? key 'state)
                    (loop (cdr rest) triples (append states name-list) declared
                          (or first (car name-list)))
                    (loop (cdr rest) triples states
                          (assq-set declared key
                                    (append (or (assq-ref declared key) '()) name-list))
                          first)))
              (let chain ((source (word (car statement)))
                          (tail   (cdr statement))
                          (triples triples))
                (if (null? tail)
                    (loop (cdr rest) triples states declared
                          (or first (word (car statement))))
                    (let ((target (word (cadr tail))))
                      (chain target (cddr tail)
                             (cons (list source (word (car tail)) target) triples)))))))
        (begin
          (when (and (not first) (not (assq-ref declared 'initial)))
            (fsm-error "the model names no state"))
          (make-fsm (reverse triples)
                    (car (or (assq-ref declared 'initial) (list first)))
                    #:forbidden (or (assq-ref declared 'forbidden) '())
                    #:final     (or (assq-ref declared 'final) '())
                    #:dfa? dfa? #:name name #:write write #:states states)))))

(define (assq-set alist key value)
  "RETURN: alist, 'alist' with 'key' bound to 'value' (a fresh list)."
  (cons (cons key value) (filter (lambda (p) (not (eq? (car p) key))) alist)))

(define (fsm->sexp m)
  "RETURN: list, the model of 'm' as statements (see 'fsm-from-sexp'), names
as symbols: '#:initial', '#:forbidden' and '#:final' where they hold
states, every transition as (source event target) sorted, then '#:state'
for every state no transition names -- the order 'fsm->string' writes."
  (let* ((edge-list (all-edges m))
         (named     (cons (fsm-initial m)
                          (append-map (lambda (e) (list (car e) (caddr e))) edge-list))))
    (append
     `((#:initial ,(string->symbol (fsm-initial m))))
     (if (null? (fsm-model-forbidden m)) '()
         `((#:forbidden ,@(map string->symbol (fsm-model-forbidden m)))))
     (if (null? (fsm-final m)) '()
         `((#:final ,@(map string->symbol (fsm-final m)))))
     (map (lambda (e) (map string->symbol e)) edge-list)
     (filter-map (lambda (s)
                   (and (not (member s named)) (not (member s (fsm-model-forbidden m)))
                        `(#:state ,(string->symbol s))))
                 (fsm-state-list m)))))

(define (sexp->text sexp)
  "RETURN: string, the statements of 'sexp' in the text 'fsm-from-string'
reads, one per line."
  (string-join
   (map (lambda (statement)
          (if (keyword? (car statement))
              (let ((key (keyword->symbol (car statement))))
                (if (eq? key 'state)
                    (string-append "state " (word (cadr statement)))
                    (string-append (symbol->string key) ": "
                                   (string-join (map word (cdr statement)) ", "))))
              (let chain ((text (word (car statement))) (tail (cdr statement)))
                (if (null? tail)
                    text
                    (chain (string-append text " ---( " (word (car tail)) " )---> "
                                          (word (cadr tail)))
                           (cddr tail))))))
        sexp)
   "\n"))

(define (fsm->string m)
  "RETURN: string, the model of 'm' in the text 'fsm-from-string' reads, one
transition per line, sorted -- what a book page or a GOOD file can show."
  (sexp->text (fsm->sexp m)))

;;  -------------------------------------------------------- the model as text
(define (split-lines text)
  "RETURN: list of strings, 'text' cut at its line ends as Python's
'str.splitlines' cuts -- '\\n', '\\r\\n', '\\r' and the other separators
Python counts; no empty last line for a text that ends in one."
  (let ((n (string-length text)))
    (let loop ((i 0) (begin 0) (result '()))
      (cond
       ((= i n) (reverse (if (< begin n) (cons (substring text begin n) result) result)))
       ((and (char=? (string-ref text i) #\return) (< (+ i 1) n)
             (char=? (string-ref text (+ i 1)) #\newline))
        (loop (+ i 2) (+ i 2) (cons (substring text begin i) result)))
       ((memv (char->integer (string-ref text i))
              '(#x0a #x0b #x0c #x0d #x1c #x1d #x1e #x85 #x2028 #x2029))
        (loop (+ i 1) (+ i 1) (cons (substring text begin i) result)))
       (else (loop (+ i 1) begin result))))))

(define (strip s) "RETURN: string, 's' without white space at both ends." (string-trim-both s))

(define (name-char? c)
  "RETURN: #t where 'c' may stand in a name after its first character --
a letter, a digit, '_', '.' or '-'."
  (or (char-alphabetic? c) (char-numeric? c) (memv c '(#\_ #\. #\-))))

(define (name? s)
  "RETURN: #t where 's' is a name: a letter or '_', then name characters."
  (and (> (string-length s) 0)
       (let ((c (string-ref s 0)))
         (or (and (char-alphabetic? c) (< (char->integer c) 128)) (char=? c #\_)))
       (string-every name-char? s 1)))

(define (name-of text number)
  "RETURN: string, the state 'text' names -- 'A' or 'state A' -- if success;
raises '&fsm-error' naming line 'number', else."
  (let* ((s (strip text))
         (n (string-length s)))
    (cond
     ((and (> n 5) (string-prefix? "state" s) (char-whitespace? (string-ref s 5))
           (name? (string-trim (substring s 5))))
      (string-trim (substring s 5)))
     ((name? s) s)
     (else (fsm-error "line " (n->s number) ": '" s "' names no state -- a state is "
                      "a word ('A', 'state A')")))))

(define (key-statement line)
  "RETURN: (word . rest), where 'line' is 'initial:', 'forbidden:' or
'final:' and what follows; #f, else."
  (any (lambda (word)
         (and (string-prefix? word line)
              (let* ((after (string-trim (substring line (string-length word)))))
                (and (string-prefix? ":" after)
                     (cons word (string-trim (substring after 1)))))))
       '("initial" "forbidden" "final")))

(define (arrow-at line i)
  "RETURN: (end . event), where an arrow -- dashes, '(', the event, ')',
dashes, '>' -- begins at index 'i' of 'line': 'end' the index past its '>',
'event' its text stripped; #f, else."
  (let ((n (string-length line)))
    (define (skip-while ok? j) "RETURN: index of the first character at or after 'j' not 'ok?'." (if (and (< j n) (ok? (string-ref line j))) (skip-while ok? (+ j 1)) j))
    (and (< i n) (char=? (string-ref line i) #\-)
         (let ((j (skip-while char-whitespace? (skip-while (lambda (c) (char=? c #\-)) i))))
           (and (< j n) (char=? (string-ref line j) #\()
                (let ((k (skip-while (lambda (c) (not (memv c '(#\( #\))))) (+ j 1))))
                  (and (< k n) (char=? (string-ref line k) #\))
                       (let ((m (skip-while (lambda (c) (char=? c #\-))
                                            (skip-while char-whitespace? (+ k 1)))))
                         (and (< m n) (char=? (string-ref line m) #\>)
                              (cons (+ m 1) (strip (substring line (+ j 1) k))))))))))))

(define (arrow-split line)
  "RETURN: list of strings, 'line' split at its arrows, the events kept:
(state event state event state ...) -- Python's '_ARROW_RE.split'."
  (let ((n (string-length line)))
    (let loop ((i 0) (begin 0) (result '()))
      (if (>= i n)
          (reverse (cons (substring line begin n) result))
          (let ((found (arrow-at line i)))
            (if found
                (loop (car found) (car found)
                      (cons* (cdr found) (substring line begin i) result))
                (loop (+ i 1) begin result)))))))

(define (text->sexp text dfa?)
  "RETURN: list, the statements of the model 'text' (see 'fsm-from-sexp'),
names as strings, ':' resolved; raises '&fsm-error' naming the line where a
line names no state, an arrow no event, 'initial:' more than one state,
':' nothing, or a DFA's two transitions for one (state, event) stand."
  (let loop ((line-list (split-lines text)) (number 1) (result '())
             (previous-head #f) (line-of '()))
    (if (null? line-list)
        (reverse result)
        (let* ((raw  (car line-list))
               (line (strip (car (string-split raw #\#))))
               (next (lambda (statement head line-of)
                       (loop (cdr line-list) (+ number 1)
                             (if statement (cons statement result) result)
                             head line-of))))
          (cond
           ((string-null? line) (next #f previous-head line-of))
           ((key-statement line)
            => (lambda (key)
                 (let ((name-list (filter-map (lambda (part)
                                                (and (not (string-null? (strip part)))
                                                     (name-of part number)))
                                              (string-split (cdr key) #\,))))
                   (when (and (string=? (car key) "initial") (not (= (length name-list) 1)))
                     (fsm-error "line " (n->s number) ": 'initial:' names one state"))
                   (next (cons (symbol->keyword (string->symbol (car key))) name-list)
                         previous-head line-of))))
           (else
            (let ((part-list (arrow-split line)))
              (if (null? (cdr part-list))
                  (let ((head (name-of line number)))
                    (next (list #:state head) head line-of))
                  (begin
                    (let check ((p (cdr part-list)))
                      (when (pair? p)
                        (when (string-null? (strip (car p)))
                          (fsm-error "line " (n->s number) ": an arrow names no event -- "
                                     "'---( event )--->'"))
                        (check (cddr p))))
                    (let* ((head-text (strip (car part-list)))
                           (head (if (string=? head-text ":")
                                     (or previous-head
                                         (fsm-error "line " (n->s number) ": ':' stands for "
                                                    "the state of the line above, and none "
                                                    "stands there"))
                                     (name-of head-text number))))
                      (let chain ((source head) (p (cdr part-list))
                                  (statement (list head)) (line-of line-of))
                        (if (null? p)
                            (next (reverse statement) head line-of)
                            (let* ((target (name-of (cadr p) number))
                                   (event  (strip (car p)))
                                   (key    (cons source event))
                                   (seen   (assoc key line-of)))
                              ;;  THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines.
                              (when (and dfa? seen (not (string=? (cadr seen) target)))
                                (fsm-error "line " (n->s number) ": " (quoted source)
                                           " --(" event ")--> " (quoted target)
                                           ", and line " (n->s (cddr seen)) ": --> "
                                           (quoted (cadr seen)) " -- a DFA moves one way "
                                           "per event, or 'DFA=False'"))
                              (chain target (cddr p) (cons* target event statement)
                                     (if seen line-of
                                         (cons (cons key (cons target number)) line-of))))))))))))))))

(define* (fsm-from-string text #:key (dfa? #t) (name "fsm") (write print-line))
  "RETURN: fsm, the model the text states, if success; raises '&fsm-error'
naming the line, else.

One statement per line; '#' starts a comment:
    initial: A              where the machine starts; default: the first
                            state the text names
    forbidden: X, Y         states the system must never enter
    final: A, B             states it may end in
    state A                 a state, transitions or not
    A ---( ev )---> B ---( ev2 )---> C     transitions, chained
    :  ---( ev )---> D      ':' is the state that began the line above"
  (fsm-from-sexp (text->sexp text dfa?) #:dfa? dfa? #:name name #:write write))

;;  ----------------------------------------------------------------- running
(define (fsm-reset! m)
  "RETURN: unspecified. 'm' stands in its initial state again, under the
model as written: what was seen is forgotten, and so is every mask and
every state forbidden or permitted since."
  (set-fsm-mask-db!   m '())
  (set-fsm-forbid-db! m (map (lambda (s) (cons s #f)) (fsm-model-forbidden m)))
  (set-fsm-permit-db! m '())
  (set-fsm-current!   m (list (fsm-initial m)))
  (set-fsm-visit-db!  m (list (cons (fsm-initial m) 1)))
  (set-fsm-taken-db!  m '())
  (set-fsm-trace-rev! m '())
  (set-fsm-breach-n!  m 0))

(define (where-text where)
  "RETURN: string, ' line 3' for the integer 3, ' <text>' for a string, ''
for #f -- the place a breach line names."
  (cond ((not where) "")
        ((integer? where) (string-append " line " (n->s where)))
        (else (string-append " " where))))

(define (since-text where)
  "RETURN: string, ' since line 9' for 9, ' since <text>' for a text, ''
for #f -- when a mask or a forbidden state began."
  (if where (string-append " since" (where-text where)) ""))

(define (targets m state event)
  "RETURN: sorted list of strings, the states 'event' leads to from 'state'
in the model as written; '() where it leads nowhere."
  (hash-ref (fsm-edge-db m) (cons state event) '()))

(define (edge? m state event)
  "RETURN: #t where the model has a transition for 'event' in 'state'."
  (pair? (targets m state event)))

(define (masked? m state event)
  "RETURN: #t where 'event' is disallowed in 'state' now -- in every state,
or in that one."
  (or (assoc (cons #f event) (fsm-mask-db m))
      (assoc (cons state event) (fsm-mask-db m))))

(define (bump alist key)
  "RETURN: alist, 'alist' with the count of 'key' one higher (1 where new)."
  (let ((have (assoc key alist)))
    (if have
        (begin (set-cdr! have (+ (cdr have) 1)) alist)
        (cons (cons key 1) alist))))

(define (here m)
  "RETURN: string, where 'm' stands: \"'idle'\", or \"{'a', 'b'}\" for a set."
  (let ((current (fsm-current m)))
    (if (null? (cdr current))
        (quoted (car current))
        (string-append "{" (string-join (map quoted current) ", ") "}"))))

(define* (fsm-fire! m event #:key (where #f))
  "RETURN: #t, 'event' moved 'm' and entered no forbidden state;
#f, it was not allowed where 'm' stands -- a BREACH line is written and 'm'
stays -- or it entered a forbidden state, which is written too."
  (let loop ((state-list (fsm-current m)) (moved '()) (masked '()))
    (if (pair? state-list)
        (let ((state (car state-list)))
          (if (masked? m state event)
              (loop (cdr state-list) moved
                    (if (edge? m state event) (append masked (list state)) masked))
              (begin
                (for-each (lambda (target)
                            (set-fsm-taken-db! m (bump (fsm-taken-db m)
                                                       (list state event target)))
                            (set-fsm-trace-rev! m (cons (list where state event target)
                                                        (fsm-trace-rev m))))
                          (targets m state event))
                (loop (cdr state-list) (append moved (targets m state event)) masked))))
        (if (null? moved)
            (let* ((allowed (fsm-allowed m))
                   (hint (cond ((not (member event (fsm-event-list m)))
                                "an event the model never names")
                               ((pair? masked)
                                (string-append
                                 "disallowed"
                                 (since-text
                                  (let ((own (assoc (cons (car masked) event) (fsm-mask-db m))))
                                    (if own (cdr own)
                                        (let ((all (assoc (cons #f event) (fsm-mask-db m))))
                                          (and all (cdr all))))))))
                               ((pair? allowed)
                                (string-append "allowed: " (string-join allowed ", ")))
                               (else "no event leaves it"))))
              (set-fsm-breach-n! m (+ (fsm-breach-n m) 1))
              ((fsm-write m) (string-append "BREACH" (where-text where) ": '" event "' in "
                                            (here m) " -- " hint))
              #f)
            (let ((moved (sorted-strings moved)))
              (set-fsm-current! m moved)
              (for-each (lambda (s) (set-fsm-visit-db! m (bump (fsm-visit-db m) s))) moved)
              (let ((entered (filter (lambda (s) (member s (fsm-forbidden m))) moved)))
                (for-each
                 (lambda (state)
                   (let ((since (cdr (assoc state (fsm-forbid-db m)))))
                     (set-fsm-breach-n! m (+ (fsm-breach-n m) 1))
                     ((fsm-write m)
                      (string-append "BREACH" (where-text where) ": '" state "' entered by '"
                                     event "' -- "
                                     (if (and (member state (fsm-model-forbidden m)) (not since))
                                         "a forbidden state"
                                         (string-append "forbidden" (since-text since)))))))
                 entered)
                (null? entered)))))))

;;  ------------------------------------------------------ the law, changing
(define (fsm-forbidden m)
  "RETURN: sorted list of strings, the states forbidden NOW -- the model's,
less those permitted, with those forbidden since."
  (sorted-strings (map car (fsm-forbid-db m))))

(define* (known m #:key (event #f) (state #f))
  "RETURN: unspecified, where 'event' and 'state' are named by the model;
raises '&fsm-error' naming what is not, else."
  (when (and event (not (member event (fsm-event-list m))))
    (fsm-error (quoted event) ": an event the model never names -- events: "
               (string-join (fsm-event-list m) ", ")))
  (when (and state (not (member state (fsm-state-list m))))
    (fsm-error (quoted state) ": a state the model never names -- states: "
               (string-join (fsm-state-list m) ", "))))

(define* (fsm-disallow! m event #:key (state #f) (where #f))
  "RETURN: unspecified. From now on 'event' is a breach -- in 'state' alone,
or in every state where #f -- until 'fsm-allow!' lifts it; the breach line
says 'disallowed since <where>'. Raises '&fsm-error' where the model names
no such event or state."
  (known m #:event event #:state state)
  (unless (assoc (cons state event) (fsm-mask-db m))
    (set-fsm-mask-db! m (append (fsm-mask-db m) (list (cons (cons state event) where))))))

(define* (fsm-allow! m event #:key (state #f) (where #f))
  "RETURN: unspecified. The mask '(fsm-disallow! m event #:state state)' set
is lifted; a mask of another scope stays. Raises '&fsm-error' where the
model names no such event or state."
  (known m #:event event #:state state)
  (set-fsm-mask-db! m (filter (lambda (p) (not (equal? (car p) (cons state event))))
                              (fsm-mask-db m))))

(define* (fsm-forbid! m state #:key (where #f))
  "RETURN: unspecified. From now on entering 'state' is a breach, until
'fsm-permit!'. Where 'm' STANDS in it, one BREACH line is written at once.
Raises '&fsm-error' where the model names no such state."
  (known m #:state state)
  (unless (assoc state (fsm-forbid-db m))
    (set-fsm-forbid-db! m (append (fsm-forbid-db m) (list (cons state where))))
    (set-fsm-permit-db! m (filter (lambda (p) (not (string=? (car p) state)))
                                  (fsm-permit-db m)))
    (when (member state (fsm-current m))
      (set-fsm-breach-n! m (+ (fsm-breach-n m) 1))
      ((fsm-write m) (string-append "BREACH" (where-text where) ": stands in '" state
                                    "' -- forbidden" (since-text where))))))

(define* (fsm-permit! m state #:key (where #f))
  "RETURN: unspecified. 'state' is no longer forbidden -- a state of the
model's own 'forbidden:' too, until 'fsm-forbid!' again. Raises
'&fsm-error' where the model names no such state."
  (known m #:state state)
  (when (assoc state (fsm-forbid-db m))
    (set-fsm-forbid-db! m (filter (lambda (p) (not (string=? (car p) state)))
                                  (fsm-forbid-db m)))
    (when (member state (fsm-model-forbidden m))
      (set-fsm-permit-db! m (cons (cons state where)
                                  (filter (lambda (p) (not (string=? (car p) state)))
                                          (fsm-permit-db m)))))))

(define* (fsm-disallowed m event thunk #:key (state #f) (where #f))
  "RETURN: what 'thunk' returns; while it runs 'event' is disallowed (see
'fsm-disallow!'), allowed again whatever way it is left -- 'dynamic-wind'."
  (dynamic-wind (lambda () (fsm-disallow! m event #:state state #:where where))
                thunk
                (lambda () (fsm-allow! m event #:state state))))

(define* (fsm-forbidding m state thunk #:key (where #f))
  "RETURN: what 'thunk' returns; while it runs 'state' is forbidden (see
'fsm-forbid!'), permitted again whatever way it is left -- 'dynamic-wind'."
  (dynamic-wind (lambda () (fsm-forbid! m state #:where where))
                thunk
                (lambda () (fsm-permit! m state))))

;;  ---------------------------------------------------------------- questions
(define (fsm-state m)
  "RETURN: string, the one state 'm' stands in, if success; raises
'&fsm-error', else -- a set of states stands (DFA off): ask 'fsm-current'."
  (if (null? (cdr (fsm-current m)))
      (car (fsm-current m))
      (fsm-error "the machine stands in " (here m) ": ask 'current()'")))

(define (fsm-in-state? m state)
  "RETURN: #t where 'm' stands in 'state'."
  (and (member state (fsm-current m)) #t))

(define (fsm-can? m event)
  "RETURN: #t where 'event' would move 'm' now."
  (any (lambda (s) (and (edge? m s event) (not (masked? m s event)))) (fsm-current m)))

(define (fsm-allowed m)
  "RETURN: sorted list of strings, the events that would move 'm' now."
  (sorted-strings
   (filter-map (lambda (key)
                 (and (member (car key) (fsm-current m))
                      (not (masked? m (car key) (cdr key)))
                      (cdr key)))
               (hash-map->list (lambda (k v) k) (fsm-edge-db m)))))

(define (fsm-trace m)
  "RETURN: list of (where state event state), every transition fired, in
order."
  (reverse (fsm-trace-rev m)))

;;  ------------------------------------------------------- the model alone
(define (all-edges m)
  "RETURN: sorted list of (source event target), every transition of the
model as written."
  (sort (append-map (lambda (key) (map (lambda (t) (list (car key) (cdr key) t))
                                       (targets m (car key) (cdr key))))
                    (hash-map->list (lambda (k v) k) (fsm-edge-db m)))
        list<?))

(define (successors m state masked)
  "RETURN: sorted list of (event . state), the transitions leaving 'state'
-- under the masks where 'masked', as written else."
  (sort (filter-map (lambda (e)
                      (and (string=? (car e) state)
                           (not (and masked (masked? m (car e) (cadr e))))
                           (cons (cadr e) (caddr e))))
                    (all-edges m))
        pair<?))

(define* (fsm-path-to m state #:key (start #f) (masked? #t))
  "RETURN: list of strings, the shortest sequence of events from 'start' --
the initial state where #f, 'now for where 'm' stands -- into 'state' ('()
where 'start' is 'state'), the first in event order among equally short
ones; #f where 'state' cannot be reached. Under the masks standing now
unless '#:masked? #f'."
  (let ((start-list (cond ((eq? start 'now) (fsm-current m))
                          ((not start)      (list (fsm-initial m)))
                          (else             (list start)))))
    (if (member state start-list)
        '()
        (let ((queue (make-q)) (seen (list-copy start-list)))
          (for-each (lambda (s) (enq! queue (cons s '()))) (sorted-strings start-list))
          (let loop ()
            (if (q-empty? queue)
                #f
                (let* ((entry (deq! queue)) (path (cdr entry)))
                  (let next ((pairs (successors m (car entry) masked?)))
                    (cond
                     ((null? pairs) (loop))
                     ((member (cdar pairs) seen) (next (cdr pairs)))
                     ((string=? (cdar pairs) state)
                      (reverse (cons (caar pairs) path)))
                     (else
                      (set! seen (cons (cdar pairs) seen))
                      (enq! queue (cons (cdar pairs) (cons (caar pairs) path)))
                      (next (cdr pairs))))))))))))

(define* (fsm-state-reachable? m state #:key (start #f) (masked? #t))
  "RETURN: #t where 'state' can be reached from 'start' (see 'fsm-path-to')."
  (and (fsm-path-to m state #:start start #:masked? masked?) #t))

(define (forbidden-of m masked)
  "RETURN: list, the states forbidden now where 'masked', the model's else."
  (if masked (fsm-forbidden m) (fsm-model-forbidden m)))

(define* (fsm-unreachable m #:key (masked? #t))
  "RETURN: sorted list of strings, the states no path from the initial state
reaches, forbidden ones left out."
  (let ((forbidden (forbidden-of m masked?)))
    (filter (lambda (s) (and (not (member s forbidden))
                             (not (fsm-state-reachable? m s #:masked? masked?))))
            (fsm-state-list m))))

(define* (fsm-dead-ends m #:key (masked? #t))
  "RETURN: sorted list of strings, the states no event leaves that are
neither final nor forbidden -- where a system would hang."
  (let ((forbidden (forbidden-of m masked?)))
    (filter (lambda (s) (and (null? (successors m s masked?))
                             (not (member s (fsm-final m)))
                             (not (member s forbidden))))
            (fsm-state-list m))))

(define* (fsm-forbidden-reachable m #:key (masked? #t))
  "RETURN: sorted list of strings, the forbidden states the model lets the
system reach from the initial state."
  (filter (lambda (s) (fsm-state-reachable? m s #:masked? masked?))
          (forbidden-of m masked?)))

(define* (fsm-check m #:key (masked? #t))
  "RETURN: exact integer, how many findings the MODEL has, each written as
one line 'MODEL: ...' -- states no path reaches, dead ends, forbidden states
reachable (with the shortest way there); 0 where it has none."
  (let ((line-list
         (append
          (map (lambda (s) (string-append "MODEL: '" s "' cannot be reached"))
               (fsm-unreachable m #:masked? masked?))
          (map (lambda (s) (string-append "MODEL: '" s "' is a dead end -- no event leaves it"))
               (fsm-dead-ends m #:masked? masked?))
          (map (lambda (s) (string-append "MODEL: forbidden '" s "' is reachable: "
                                          (string-join (fsm-path-to m s #:masked? masked?) " ")))
               (fsm-forbidden-reachable m #:masked? masked?)))))
    (for-each (fsm-write m) line-list)
    (length line-list)))

;;  ------------------------------------------------------------------ the end
(define (fsm-report m)
  "RETURN: exact integer, the breaches seen, a non-final end counted; written
before it, sorted, what the events covered of the model -- states counted
without the forbidden ones -- every transition taken or not, the states
never entered, where 'm' ended, the masks and forbidden or permitted states
still standing, and a BREACH line for an end outside the final states."
  (let* ((write      (fsm-write m))
         (all-edge   (all-edges m))
         (end-ok?    (or (null? (fsm-final m))
                         (any (lambda (s) (member s (fsm-final m))) (fsm-current m))))
         (breach-n   (+ (fsm-breach-n m) (if end-ok? 0 1)))
         (goal       (filter (lambda (s) (not (member s (fsm-model-forbidden m))))
                             (fsm-state-list m)))
         (visited    (filter (lambda (s) (assoc s (fsm-visit-db m))) goal)))
    (write (string-append (fsm-name m) ": " (n->s (length visited)) " of "
                          (n->s (length goal)) " states visited, "
                          (n->s (length (fsm-taken-db m))) " of " (n->s (length all-edge))
                          " transitions taken, " (n->s breach-n) " breach"
                          (if (= breach-n 1) "" "es")))
    (for-each
     (lambda (edge)
       (let ((n (let ((p (assoc edge (fsm-taken-db m)))) (and p (cdr p)))))
         (write (string-append "  " (if n "taken    " "not taken") "  " (car edge)
                               " ---( " (cadr edge) " )---> " (caddr edge)
                               (if (and n (> n 1)) (string-append "   x" (n->s n)) "")))))
     all-edge)
    (for-each (lambda (s)
                (unless (or (assoc s (fsm-visit-db m)) (member s (fsm-model-forbidden m)))
                  (write (string-append "  never in   '" s "'"))))
              (fsm-state-list m))
    (write (string-append "  ended in   " (here m)))
    ;;  A PHASE NEVER LIFTED IS SAID: what still stands at the end.
    (for-each
     (lambda (p)
       (let ((state (caar p)) (event (cdar p)))
         (write (string-append "  disallowed '" event "' "
                               (if state (string-append "in '" state "'") "in every state")
                               (since-text (cdr p))))))
     (sort (fsm-mask-db m)
           (lambda (a b) (pair<? (cons (cdar a) (or (caar a) ""))
                                 (cons (cdar b) (or (caar b) ""))))))
    (for-each (lambda (s)
                (unless (member s (fsm-model-forbidden m))
                  (write (string-append "  forbidden  '" s "'"
                                        (since-text (cdr (assoc s (fsm-forbid-db m))))))))
              (fsm-forbidden m))
    (for-each (lambda (p) (write (string-append "  permitted  '" (car p) "'"
                                                (since-text (cdr p)))))
              (sort (fsm-permit-db m) (lambda (a b) (string<? (car a) (car b)))))
    (unless end-ok?
      (write (string-append "BREACH: ended in " (here m) " -- final: "
                            (string-join (fsm-final m) ", "))))
    breach-n))
