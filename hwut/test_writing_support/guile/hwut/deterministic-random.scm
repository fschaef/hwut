;;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;;;_____________________________________________________________________________
;;;
;;; PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
;;;          'python/deterministic_random.py'. The same seed gives the same
;;;          numbers as the Python module, draw for draw: Park-Miller MINSTD,
;;;          'state = 48271 * state mod (2^31 - 1)', exact integer arithmetic.
;;;
;;;     (define s (make-deterministic-stream #x42))
;;;     (stream-next-int s 0 9)    (stream-next-float s)    (stream-coin s 0.5)
;;;     (stream-select s pool)     (stream-choice s pool)   (stream-gauss s 0. 1.)
;;;     (stream-sample-indices s 10 3)                      (stream-sample s pool 3)
;;;
;;;     (define m (make-selection-marker))
;;;     (stream-select-unchosen s pool m)    ; prefers what 'm' has not seen
;;;
;;; A POOL is a list, a vector or a string (Python's list, tuple, str); what
;;; is drawn is the element itself.
;;;
;;; IDENTITY IS 'eq?': Python's marker remembers a candidate by 'id(object)';
;;; Scheme's identity is 'eq?', and the candidate that is the SAME wherever
;;; it is written is a SYMBOL -- '(a b c d) built afresh holds the same four
;;; objects, as Python's interned literals do. Two equal strings written in
;;; two places may be two objects; a test that wants them one draws symbols.
;;;
;;; 'stream-gauss' is the one path through libm (log, cos, sqrt -- Guile
;;; calls the C library's), as in Python.
;;;_____________________________________________________________________________
(define-module (hwut deterministic-random)
  #:use-module (srfi srfi-9)
  #:export (make-deterministic-stream deterministic-stream? stream-state
            stream-next-int stream-next-float stream-coin
            stream-select stream-select-unchosen stream-choice
            stream-gauss stream-gauss-int stream-sample-indices stream-sample
            make-selection-marker selection-marker? selection-marker-reset!))

;;  THE CLASSES ARE RECORDS: a stream is its one integer of state, a marker
;;  its one table -- data with procedures over it, nothing to inherit.
(define-record-type <deterministic-stream>
  (%make-deterministic-stream state)
  deterministic-stream?
  (state stream-state set-stream-state!))

(define-record-type <selection-marker>
  (%make-selection-marker chosen)
  selection-marker?
  (chosen marker-chosen))

(define* (make-deterministic-stream #:optional (seed #x42))
  "RETURN: deterministic-stream, its state 'seed' masked to 31 bits -- the
stream Python's 'DeterministicStream(seed)' is."
  (%make-deterministic-stream (logand seed #x7FFFFFFF)))

(define (make-selection-marker)
  "RETURN: selection-marker, with nothing chosen yet."
  (%make-selection-marker (make-hash-table)))

(define (selection-marker-reset! marker)
  "RETURN: unspecified. 'marker' forgets every chosen candidate; the next
cycle restarts."
  (hash-clear! (marker-chosen marker)))

(define (stream-next-int stream v-min v-max)
  "RETURN: exact integer in [v-min, v-max], the next draw of 'stream';
'v-min' itself where 'v-min' = 'v-max' -- a draw is consumed either way."
  (let ((state (modulo (* 48271 (stream-state stream)) 2147483647)))
    (set-stream-state! stream state)
    (if (= v-min v-max)
        v-min
        (+ v-min (modulo state (+ (- v-max v-min) 1))))))

(define (stream-next-float stream)
  "RETURN: inexact real in [0.0, 1.0), one of 1000001 values: the next
'stream-next-int' over [0, 1000000] divided by 1000001.0."
  (/ (stream-next-int stream 0 1000000) 1000001.0))

(define (stream-coin stream probability-of-true)
  "RETURN: #t with 'probability-of-true', #f else -- resolved in steps of
1/1000001 (THE FLOOR, TW-1: any 0 < p <= 1/1000001 comes out as 1/1000001)."
  (< (stream-next-float stream) probability-of-true))

(define (pool->vector pool)
  "RETURN: vector, the candidates of 'pool' (list, vector or string) in
order -- the string's characters for a string."
  (cond ((vector? pool) pool)
        ((string? pool) (list->vector (string->list pool)))
        (else           (list->vector pool))))

(define (stream-select stream pool)
  "RETURN: object, a uniformly drawn candidate of 'pool' (list, vector or
string). Stateless: the same stream state and the same pool always yield
the same element."
  (let ((v (pool->vector pool)))
    (vector-ref v (stream-next-int stream 0 (- (vector-length v) 1)))))

(define (stream-choice stream pool)
  "RETURN: object, a candidate of 'pool' drawn as 'stream-select' draws it."
  (stream-select stream pool))

(define (stream-select-unchosen stream pool marker)
  "RETURN: object, a candidate of 'pool' that 'marker' has not seen (by 'eq?'),
drawn uniformly among those and recorded in 'marker'; where every candidate
was seen, 'marker' is reset first and the draw is from the whole pool."
  (let* ((chosen   (marker-chosen marker))
         (all      (vector->list (pool->vector pool)))
         (unseen   (filter (lambda (c) (not (hashq-ref chosen c #f))) all))
         (unchosen (if (null? unseen)
                       (begin (hash-clear! chosen) all)
                       unseen))
         (choice   (list-ref unchosen
                             (stream-next-int stream 0 (- (length unchosen) 1)))))
    (hashq-set! chosen choice #t)
    choice))

;;  PYTHON'S 'math.pi', the double nearest to pi.
(define pi 3.141592653589793)

(define* (stream-gauss stream mu sigma #:optional (lower -inf.0) (upper +inf.0))
  "RETURN: inexact real, a draw of the normal distribution (mu, sigma) by
the Box-Muller transform, clipped to [lower, upper]. Two uniform draws are
consumed; log, cos and sqrt are the C library's."
  (let* ((u1     (+ (stream-next-float stream) 1e-9))
         (u2     (stream-next-float stream))
         (z0     (* (sqrt (* -2.0 (log u1))) (cos (* 2.0 pi u2))))
         (result (+ (* z0 sigma) mu)))
    (cond ((< result lower) lower)
          ((> result upper) upper)
          (else             result))))

(define* (stream-gauss-int stream mu sigma #:optional (lower -inf.0) (upper +inf.0))
  "RETURN: exact integer, 'stream-gauss' rounded to the nearest integer, a
half to the even one -- Python's 'int(round(x))'."
  (inexact->exact
   (round (stream-gauss stream mu sigma (exact->inexact lower) (exact->inexact upper)))))

(define (stream-sample-indices stream population-size k)
  "RETURN: list of 'k' distinct exact integers from [0, population-size), in
draw order -- a partial Fisher-Yates shuffle, one draw per index."
  (unless (>= population-size k)
    (error "stream-sample-indices: population smaller than k" population-size k))
  (let ((indices (list->vector (iota population-size))))
    (let loop ((i 0) (result '()))
      (if (= i k)
          (reverse result)
          (let* ((j    (stream-next-int stream i (- population-size 1)))
                 (keep (vector-ref indices i)))
            (vector-set! indices i (vector-ref indices j))
            (vector-set! indices j keep)
            (loop (+ i 1) (cons (vector-ref indices i) result)))))))

(define (stream-sample stream population n)
  "RETURN: list of 'n' distinct elements of 'population' (list, vector or
string), drawn at the indices 'stream-sample-indices' draws."
  (let ((v (pool->vector population)))
    (map (lambda (i) (vector-ref v i))
         (stream-sample-indices stream (vector-length v) n))))
