;; @hwut {
;;     title      = "DeterministicStream RNG and SelectionMarker spread"
;;     choices {
;;         gauss      { features = ["guile-random"] }
;;         primitives { features = ["guile-random"] }
;;         ranges     { features = ["guile-random"] }
;;         sample     { features = ["guile-random"] }
;;         seed_sweep { features = ["guile-random"] }
;;         select     { features = ["guile-random"] }
;;         unchosen   { features = ["guile-random"] }
;;     }
;;     interactive = true
;; }
;;
;; SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
;; _____________________________________________________________________________
;;
;; PURPOSE: The Guile port of 'python/TEST/test-deterministic-random.py',
;;          choice for choice, held against its GOOD files by '.link'.
;;
;; THE CANDIDATES ARE SYMBOLS where the Python test draws string literals:
;; Python's interned literals are one object wherever they are written, and
;; so is a symbol -- the 'FRESH container' and 'sub-pool' claims of
;; 'unchosen' rest on exactly that identity.
;; _____________________________________________________________________________
(add-to-load-path (string-append (dirname (canonicalize-path (current-filename))) "/.."))
(use-modules (hwut runner) (hwut pytext) (hwut deterministic-random))

(define SEED #x42)
(define TOLERANCE-REGION-BEGIN "##! table numeric={1:1e-12}")
(define REGION-END             "####")

(define (banner label)
  "RETURN: unspecified. Section heading."
  (display (string-append "\n--- " label " ---\n")))

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline."
  (display (string-concatenate text-list))
  (newline))


(define (two-digits i)
  "RETURN: string, 'i' as '%02d'."
  (string-pad (number->string i) 2 #\0))

(define (draws n draw)
  "RETURN: list, 'draw' called 'n' times, the results in order."
  (let loop ((i 0) (result '()))
    (if (= i n) (reverse result) (loop (+ i 1) (cons (draw) result)))))

(define (words lst)
  "RETURN: string, the elements of 'lst' as 'str' prints them, blank-joined."
  (py-join " " (map (lambda (x) (if (symbol? x) (symbol->string x) (py-str x))) lst)))

(define (run-primitives)
  "RETURN: unspecified. The bare generator: next-int, next-float, coin."
  (banner "next_int(0, 1000000) -- first 20")
  (let ((s (make-deterministic-stream SEED)))
    (do ((i 0 (+ i 1))) ((= i 20))
      (say "[" (two-digits i) "] " (number->string (stream-next-int s 0 1000000)))))
  (banner "next_float -- first 10 (full precision)")
  (let ((s (make-deterministic-stream SEED)))
    (do ((i 0 (+ i 1))) ((= i 10))
      (say "[" (two-digits i) "] " (py-float-repr (stream-next-float s)))))
  (banner "coin(0.5) -- 40 draws")
  (let ((s (make-deterministic-stream SEED)))
    (say (py-join " " (draws 40 (lambda () (if (stream-coin s 0.5) "T" "F")))))))

(define (run-ranges)
  "RETURN: unspecified. next-int over small and degenerate ranges."
  (banner "next_int(0, 9) -- 30 draws")
  (let ((s (make-deterministic-stream SEED)))
    (say (words (draws 30 (lambda () (stream-next-int s 0 9))))))
  (banner "next_int(5, 5) -- degenerate range returns the bound")
  (let ((s (make-deterministic-stream SEED)))
    (say (words (draws 5 (lambda () (stream-next-int s 5 5))))))
  (banner "next_int(-3, 3) -- spanning zero")
  (let ((s (make-deterministic-stream SEED)))
    (say (py-join " " (draws 20 (lambda ()
                                  (let ((n (stream-next-int s -3 3)))
                                    (string-append (if (< n 0) "" "+")
                                                   (number->string n)))))))))

(define (run-gauss)
  "RETURN: unspecified. The libm path: gauss, clamped gauss, gauss-int --
the two full-precision blocks framed as a tolerated 'table' region."
  (banner "gauss(0, 1) -- 10 draws (full precision)")
  (let ((s (make-deterministic-stream SEED)))
    (say TOLERANCE-REGION-BEGIN)
    (do ((i 0 (+ i 1))) ((= i 10))
      (say "[" (two-digits i) "] " (py-float-repr (stream-gauss s 0.0 1.0))))
    (say REGION-END))
  (banner "gauss(0, 1) clamped to [-1, 1]")
  (let ((s (make-deterministic-stream SEED)))
    (say TOLERANCE-REGION-BEGIN)
    (do ((i 0 (+ i 1))) ((= i 10))
      (say "[" (two-digits i) "] " (py-float-repr (stream-gauss s 0.0 1.0 -1.0 1.0))))
    (say REGION-END))
  (banner "gauss_int(100, 15) -- 20 draws")
  (let ((s (make-deterministic-stream SEED)))
    (say (words (draws 20 (lambda () (stream-gauss-int s 100.0 15.0)))))))

(define (run-sample)
  "RETURN: unspecified. sample-indices (Fisher-Yates) and sample over a list."
  (banner "sample_indices(10, 10) -- full permutation")
  (say (py-list-repr (stream-sample-indices (make-deterministic-stream SEED) 10 10)))
  (banner "sample_indices(20, 5) -- partial draw")
  (say (py-list-repr (stream-sample-indices (make-deterministic-stream SEED) 20 5)))
  (banner "choice from a list -- 20 draws")
  (let ((s    (make-deterministic-stream SEED))
        (pool '("alpha" "beta" "gamma" "delta" "epsilon")))
    (say (words (draws 20 (lambda () (stream-choice s pool))))))
  (banner "sample(list, 4) -- unique elements")
  (say (py-list-repr (map string (stream-sample (make-deterministic-stream SEED)
                                                "ABCDEFGH" 4)))))

(define (run-select)
  "RETURN: unspecified. Stateless select: same state + same pool -> same element."
  (banner "select over a list -- 20 draws")
  (let ((s (make-deterministic-stream SEED)))
    (say (words (draws 20 (lambda () (stream-select s '(a b c d)))))))
  (banner "select over a tuple -- 12 draws")
  (let ((s (make-deterministic-stream SEED)))
    (say (words (draws 12 (lambda () (stream-select s #(p q r))))))))

(define (run-unchosen)
  "RETURN: unspecified. select-unchosen spread is identity-keyed: a clean
cycle over a stable pool, the SAME cycle over a pool built afresh every
call, and coherence across differing sub-pools."
  (banner "stable pool -- three full cycles of 4 elements")
  (let ((s (make-deterministic-stream SEED)) (pool '(a b c d)) (m (make-selection-marker)))
    (say (words (draws 12 (lambda () (stream-select-unchosen s pool m))))))
  (banner "FRESH container each call -- identical to the stable pool above")
  (let ((s (make-deterministic-stream SEED)) (m (make-selection-marker)))
    (say (words (draws 12 (lambda ()
                            ;;  a new list every call; its symbols are the same
                            (stream-select-unchosen s (list 'a 'b 'c 'd) m))))))
  (banner "sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]")
  (let* ((s     (make-deterministic-stream SEED))
         (m     (make-selection-marker))
         (first (stream-select-unchosen s '(a b) m))
         (rest  (draws 3 (lambda () (stream-select-unchosen s '(a b c d) m)))))
    (say "first(from sub): " (symbol->string first) "  then(from full): " (words rest)))
  (banner "reset() restarts the cycle")
  (let* ((s      (make-deterministic-stream SEED))
         (pool   '(a b c d))
         (m      (make-selection-marker))
         (before (draws 4 (lambda () (stream-select-unchosen s pool m))))
         (after  (begin (selection-marker-reset! m)
                        (draws 4 (lambda () (stream-select-unchosen s pool m))))))
    (say "before reset: " (words before))
    (say "after  reset: " (words after))))

(define (run-seed-sweep)
  "RETURN: unspecified. The first next-int per seed -- pins seed handling."
  (banner "first next_int(0, 1000000) per seed 0..15")
  (do ((seed 0 (+ seed 1))) ((= seed 16))
    (say "seed=" (py-rjust (number->string seed) 2) " -> "
         (number->string (stream-next-int (make-deterministic-stream seed) 0 1000000)))))

(hwut-runner-run
 (make-hwut-runner (command-line)
                   "DeterministicStream RNG and SelectionMarker spread"
                   `(("primitives" . ,run-primitives)
                     ("ranges"     . ,run-ranges)
                     ("gauss"      . ,run-gauss)
                     ("sample"     . ,run-sample)
                     ("select"     . ,run-select)
                     ("unchosen"   . ,run-unchosen)
                     ("seed_sweep" . ,run-seed-sweep))))
