;; support-path.scm -- WHERE THE SCHEME TEST SUPPORT STANDS, said once; no test.
;;
;; RETURN: unspecified. '%load-path' ends with the directory of the support's
;;         modules '(hwut runner)', '(hwut vterm)', ... (the port's 'guile/'),
;;         so that '(use-modules (hwut ...))' finds them.
;; A test that wants the support says, before its 'use-modules':
;;
;;     (load "support-path.scm")       ; relative to the test's own file
;;
;; GUILE_LOAD_PATH is Guile's own mechanism and comes FIRST: Guile puts it on
;; '%load-path' before this file runs; the path below is only appended, a
;; fallback where GUILE_LOAD_PATH does not name the support. A relative path
;; is read from this file's directory.
(set! %load-path (append %load-path (list (let ((at "../../../test_writing/guile")) (if (absolute-file-name? at) at (string-append (dirname (canonicalize-path (current-filename))) "/" at))))))   ; HWUT-SUPPORT-PATH
