==============================================================================
EXPLANATION -- concepts taught by checked example                     (R-35)
==============================================================================
The fourth documentation bin. README holds mechanics, RATIONALE the settled
why, DISCUSSIONS the open forks; EXPLANATION holds .vut files that TEACH one
concept each, narrated in comments. Two laws govern this directory:

  1. Every file is CHECKED by the suite (test-explanations.py): it must
     parse, declare, and elaborate clean -- an explanation that stops
     compiling fails the suite. Teaching text may not drift from the
     language.
  2. Narrative language is WELCOME here -- this is the one bin where
     "because" belongs in prose next to code. Where a mentioned law is not
     yet enforced by the checker, the text SAYS so.

One file, one concept. Current set: explain-construct.vut,
explain-destruct.vut, explain-lifecycle.vut, explain-take-give-know.vut,
explain-ephemerals.vut, explain-destruction-cannot-fail.vut.
