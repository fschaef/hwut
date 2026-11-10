#!/usr/bin/env -S guile --no-auto-compile -s
!#
;; @hwut {
;;     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
;;     tolerance { constraints = ["overshoot <= 0.5 K",
;;                                "settle <= 4 min",
;;                                "verdict == 'settled'"] }
;;     choices {
;;         heat { features = ["demo-guile+cover-region-verbatim", "demo-guile+cover-region-table", "demo-guile+cover-region-point-cloud",
;;                            "demo-guile+cover-region-ignore", "demo-guile+cover-laws-in-units", "demo-guile+cover-string-binding",
;;                            "demo-guile+cover-test-level-tolerance", "demo-guile+cover-annotation-lines"] }
;;         cool { features = ["demo-guile+cover-region-verbatim", "demo-guile+cover-region-table", "demo-guile+cover-region-point-cloud",
;;                            "demo-guile+cover-region-ignore", "demo-guile+cover-laws-in-units", "demo-guile+cover-string-binding",
;;                            "demo-guile+cover-test-level-tolerance", "demo-guile+cover-annotation-lines"] }
;;     }
;; }
;;
;; _____________________________________________________________________________
;; SUBJECT  a climate chamber driven from one temperature to another by a PI
;;          controller: its configuration, its sensors at the end, its step
;;          response, and the three numbers its requirement names.
;; REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
;;              it by no more than 0.5 K, and reports itself 'settled'.
;;
;; Every run is seeded by the clock: the sensors are noisy, the four sensor
;; rows come out in a different order, the calibration stamps are today's.
;; Both choices pass on every run anyway. What each part of the output shows
;; -- '##' notes, '##! verbatim', '##! table', '##! point-cloud', '##! ignore',
;; units, a string law, the test-level tolerance -- is said in
;; '../../python/TEST/chamber.py'; this file prints the same text.
;;
;; CHOICES  heat  20 degC -> 40 degC.
;;          cool  40 degC -> 20 degC.
;; _____________________________________________________________________________
(use-modules (srfi srfi-1))

(define DT-S         1.0)                ; simulation step
(define DURATION-S   400)                ; simulated time
(define SAMPLE-S     20)                 ; one point of the cloud every 20 s
(define BAND-K       0.3)                ; 'settled' = within 0.3 K of the setpoint
(define NOISE-K      0.02)               ; sensor noise, one sigma
(define TAU-S        300.0)              ; the plant
(define RATE-K-PER-S 0.15)
(define KP           0.6)                ; the controller
(define KI           0.01)

(define (say . text-list)
  "RETURN: unspecified. The texts, joined, and a newline, on stdout."
  (display (string-concatenate text-list))
  (newline))

(define (fixed x digit-n)
  "RETURN: string, 'x' with 'digit-n' digits after the point, rounded as
Python's '%.<n>f' rounds: the exact binary value, half to even."
  (let* ((scale (expt 10 digit-n))
         (n     (round (* (inexact->exact x) scale)))
         (body  (number->string (abs n)))
         (body  (if (<= (string-length body) digit-n)
                    (string-append (make-string (- (+ digit-n 1) (string-length body)) #\0) body)
                    body))
         (cut   (- (string-length body) digit-n)))
    (string-append (if (< n 0) "-" "")
                   (substring body 0 cut)
                   (if (> digit-n 0) (string-append "." (substring body cut)) ""))))

(define (right text width)
  "RETURN: string, 'text' padded with blanks on the left to 'width'."
  (string-pad text (max width (string-length text))))

(define (left text width)
  "RETURN: string, 'text' padded with blanks on the right to 'width'."
  (string-pad-right text (max width (string-length text))))

(define CONFIG-TEXT
  (string-append
   "chamber:\n"
   "  plant:\n"
   "    time_constant_s: " (fixed TAU-S 0) "\n"
   "    heater_rate_K_per_s: " (number->string RATE-K-PER-S) "\n"
   "  controller:\n"
   "    kind: PI\n"
   "    kp: " (number->string KP) "\n"
   "    ki: " (number->string KI) "\n"
   "    output: [-1.0, 1.0]\n"
   "  sensors: [top, middle, bottom, door]"))

;;  Offset of each sensor against the air in the middle of the chamber.
(define SENSOR-OFFSET-LIST '(("top" . 0.10) ("middle" . 0.00) ("bottom" . -0.10) ("door" . -0.40)))

(define (gauss sigma rng)
  "RETURN: inexact real, drawn from the normal distribution of mean 0 and
standard deviation 'sigma' by the random state 'rng'."
  (* sigma (random:normal rng)))

(define (step-response start-C setpoint-C rng)
  "RETURN: list of (t-s . measured-C), one sample per simulation step, of the
chamber driven from 'start-C' to 'setpoint-C' by the PI controller of
CONFIG-TEXT, with sensor noise drawn from 'rng'."
  (let loop ((t 0.0) (temp start-C) (integral 0.0) (sample-list '()))
    (if (> t DURATION-S)
        (reverse sample-list)
        (let* ((measured (+ temp (gauss NOISE-K rng)))
               (error    (- setpoint-C measured))
               (output   (+ (* KP error) (* KI integral)))
               ;;  anti-windup: integrate only while unsaturated
               (integral (if (< -1.0 output 1.0) (+ integral (* error DT-S)) integral))
               (output   (max -1.0 (min 1.0 output))))
          (loop (+ t DT-S)
                (+ temp (* DT-S (+ (/ (- 20.0 temp) TAU-S) (* RATE-K-PER-S output))))
                integral
                (cons (cons t measured) sample-list))))))

(define (overshoot-K sample-list start-C setpoint-C)
  "RETURN: inexact real, how far in K the chamber went past 'setpoint-C' in
the direction of travel from 'start-C'; 0.0 where it never did."
  (let ((sign (if (> setpoint-C start-C) 1.0 -1.0)))
    (max 0.0 (apply max (map (lambda (s) (* sign (- (cdr s) setpoint-C))) sample-list)))))

(define (settle-s sample-list setpoint-C)
  "RETURN: inexact real, the time in s after which every sample stays within
BAND-K of 'setpoint-C' (the step after the last one outside)."
  (let ((outside (filter (lambda (s) (> (abs (- (cdr s) setpoint-C)) BAND-K)) sample-list)))
    (if (null? outside) 0.0 (+ (car (last outside)) DT-S))))

(define (print-config)
  "RETURN: unspecified. Prints the configuration as loaded, byte for byte."
  (say "configuration, as loaded (YAML: whitespace is meaning):")
  (say "##! verbatim")
  (say CONFIG-TEXT)
  (say "####"))

(define (shuffled item-list rng)
  "RETURN: list, 'item-list' in an order drawn by 'rng' (Fisher-Yates)."
  (let ((v (list->vector item-list)))
    (do ((i (- (vector-length v) 1) (- i 1))) ((< i 1) (vector->list v))
      (let* ((j (random (+ i 1) rng)) (t (vector-ref v i)))
        (vector-set! v i (vector-ref v j))
        (vector-set! v j t)))))

(define (print-sensors setpoint-C rng)
  "RETURN: unspecified. Prints one row per sensor, in a random order, with
today's calibration stamp and the reading at the end in K."
  (say "sensors at the end, in K (the order is the bus's):")
  (say "    sensor  calibrated           reading_K")
  (say "##! table key=0 ignore=1 numeric={2:0.0005}")
  (let ((stamp (strftime "%Y-%m-%dT%H:%M:%S" (localtime (current-time)))))
    (for-each (lambda (entry)
                (let ((reading (+ setpoint-C (cdr entry) (gauss NOISE-K rng) 273.15)))
                  (say "    " (left (car entry) 6) "  " stamp "  " (right (fixed reading 2) 9))))
              (shuffled SENSOR-OFFSET-LIST rng)))
  (say "####"))

(define (print-cloud sample-list start-C setpoint-C)
  "RETURN: unspecified. Prints the step response, one point (t-s, T-degC)
every SAMPLE-S, framed with the envelope the requirement allows."
  (let* ((low  (min start-C setpoint-C))
         (high (max start-C setpoint-C))
         (high (if (> setpoint-C start-C) (+ high 0.5) high))
         (low  (if (> setpoint-C start-C) low (- low 0.5))))
    ;;  0.1 K beyond the envelope on either side: the sensor's noise.
    (say "step response, t in s against T in degC; envelope " (fixed low 1) " .. " (fixed high 1) ":")
    (say "##! point-cloud limit=0.5 constraint={y >= " (fixed (- low 0.1) 1)
         " and y <= " (fixed (+ high 0.1) 1) "}")
    (for-each (lambda (s)
                (when (= 0.0 (floor-remainder (car s) SAMPLE-S))
                  (say "    " (right (fixed (car s) 0) 5) "  " (right (fixed (cdr s) 2) 6))))
              sample-list)
    (say "####")))

(define (print-picture sample-list start-C setpoint-C)
  "RETURN: unspecified. Prints the step response as stars, for the human eye
only: one row per 40 s, one column per 0.5 K."
  (let ((low (- (min start-C setpoint-C) 1.0)))
    (say "the same, as a picture ('|' the setpoint):")
    (say "##! ignore")
    (for-each (lambda (s)
                (when (= 0.0 (floor-remainder (car s) 40))
                  (let ((row (make-string 46 #\space)))
                    (string-set! row (inexact->exact (round (/ (- setpoint-C low) 0.5))) #\|)
                    (string-set! row (max 0 (min 45 (inexact->exact (round (/ (- (cdr s) low) 0.5))))) #\*)
                    (say "    " (right (fixed (car s) 0) 4) " s  " (string-trim-right row)))))
              sample-list)
    (say "####")))

(define (run start-C setpoint-C)
  "RETURN: unspecified. Drives the chamber and prints every part of the report."
  (let* ((now         (gettimeofday))
         (rng         (seed->random-state (+ (* (car now) 1000000) (cdr now))))
         (sample-list (step-response start-C setpoint-C rng)))
    (say "## climate chamber, " (fixed start-C 0) " degC -> " (fixed setpoint-C 0)
         " degC, one sample per second")
    (say "## '##' lines are for the reader: the comparison skips them.")
    (print-config)
    (print-sensors setpoint-C rng)
    (print-cloud sample-list start-C setpoint-C)
    (print-picture sample-list start-C setpoint-C)
    (let ((over    (overshoot-K sample-list start-C setpoint-C))
          (settle  (settle-s sample-list setpoint-C))
          (verdict (if (<= (abs (- (cdr (last sample-list)) setpoint-C)) BAND-K) "settled" "drifting")))
      (say "overshoot  ((overshoot: " (fixed over 2) " K))          law <= 0.5 K")
      (say "settled    ((settle: " (fixed settle 0) " s))             law <= 4 min")
      (say "chamber    ((verdict: \"" verdict "\"))"))))

(define CHOICE-LIST '(("heat" 20.0 40.0) ("cool" 40.0 20.0)))

(let* ((argv   (command-line))
       (choice (if (> (length argv) 1) (cadr argv) ""))
       (entry  (assoc choice CHOICE-LIST)))
  (unless entry
    (say "choices: " (string-join (map car CHOICE-LIST) ", "))
    (exit 1))
  (apply run (cdr entry))
  (say "<hwut-end>"))
