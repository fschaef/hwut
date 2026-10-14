# Session hand-off -- features, the map, restructuring (2026-10-14)

Self-contained: a session that has only this file, the tree and the bundles
can continue. Read in this order: this file, `adm/WORK/spec/23-features.txt`
(VERSION 9, section 10 = open points, section 11 = the wish),
`adm/WORK/gathered/sanitizer-risks-2026-10-13.md`, `doc/HOWTO-FEATURES.txt`,
exploration `RATIONALE.txt` R-94 (model) and R-95 (wish).

## 1  State of the tree

Bundles 111 (rename `vut` -> `hwut`), 112 (feature model, map, sanitizer) and
113 (wish `-F/--feature`, `-k/--keys`) are BUILT and PROVEN: full census
1025 ok, 13 fail = the 11 standing fails (no libvterm: `test-screen.py` x3,
`test-hwut_vterm.py` x8) + 2 usage pages, re-recorded afterwards
(`test-cmdline.py faces`, `test-face-words.sh tiers`). The real tree's
`hwut.sanitize.propose --relations` says "nothing to sanitize".
This bundle (114) is CUMULATIVE over 112 and 113 plus the rulings below, so
it can be applied on a tree after 111 alone.

The model in one paragraph: ONE file kind `hwut-features.conf` (`features { }`
with title/doc/documents/keys/childs); the parent names the child; full id =
key chain from the directory holding `hwut-root.conf`; a test links by short
name; the required `hwut-feature-map.conf` binds PUBLISHED ids to full ids or
`none` (retired); keys travel downward; labels (`-l`, sets of runs) and keys
(`-k`, categories of features) are separate; implicit tree (feature files in
TEST directories only) versus explicit tree (any component file).

## 2  Rulings of 2026-10-13/14, NOT YET BUILT (spec section 10)

- o-14  STATES. Implementation axis: IMPLEMENTED / NOT IMPLEMENTED / RETIRED;
  verdict ok / fail beside it. Leaf: implemented = at least one linked run;
  retired = map binds it to `none`. Component: retired where all below are
  retired, else retired features are ignored and it is implemented only if
  every remaining one is. Verdict: not implemented = fail; implemented leaf
  ok if every run passes; implemented component ok if everything below is ok.
  Retired has NO verdict, no count, no exit status. Empty component (nothing
  below at all): treated as not implemented -- ASSUMED, ask once.
  Consequence: UNPROVEN / PROVEN / FAILING of the report, the feature
  document, spec, HOWTO and the book note change wording; keep the three
  names for the reader if wanted, with "not implemented" as the reason.
- o-10  IDENTIFIERS. Keys and published ids: Unicode UAX #31
  (XID_Start / XID_Continue), widened by DIGITS at the start and `-` in the
  continue part; NFC enforced (a word not in NFC is a fault, never silently
  changed); no case folding; a published id = such words joined by `.`.
  Python `str.isidentifier()` implements the classes. `key_of_name` follows
  the same rule (`Groesse` stays, characters outside it become `_`).
  Anything else (blank, `*`, `{`, `,`) in a published id is a map fault,
  named with its line, entry unread; the sanitizer never writes one.
- o-5   CLOSED. `hwut.run` prints NO feature report.
- o-12  The proposal NAMES the repointings and the refused pairings (text
  only): `repoint <published> <old full id> -> <new full id>` /
  `unpaired <published> <old full id> (candidates: ...)`.

## 3  Open, answer pending

- o-13  One explaining line above a `relate` proposal that the
  implicit -> explicit flip causes ("because <path> exists, every component
  must state a file"). The user did not understand the first explanation;
  the flip itself does NOT change ids (keys equal directory names in an
  implicit tree). Ask again, shortly, or drop.
- Wording of all sanity messages.
- `hwut.move` silent where `hwut-root.conf` is missing (o-11).
- `# vut-register` data markers still in the old name.
- Standing: `test-sanitize-books` flaky; recorded-failure GOOD in
  `engine/operations/interaction/TEST/test-tui.py [elements]`; 110 features
  UNPROVEN; 10 runs NONSENSE?.

## 4  THE SESSION TO BE HELD (o-15): restructuring and the map

Subject: what happens to ids when the tree is restructured -- moved
directory, inserted level, renamed key, merge, split -- and what a published
id means afterwards. The input is sanitizer-risks sections 2, 3, 4, 5, 11.
Facts as built (do not re-derive):

- Insertion of a level changes full ids, never published ids. The sanitizer
  sees GONE (map right side names no feature) and UNMAPPED (feature no entry
  binds) and pairs them by the longest common SUFFIX of the ids (at least
  the feature name); only a UNIQUE best pair is repointed (`map_pair_list`
  in `feature_adapt.py`).
- Not unique (same feature name twice, merge, split): nothing is guessed;
  old id stays GONE, the new feature UNMAPPED; the author runs
  `hwut.sanitize retire <dir> <id>` or edits the map by hand. No aliases
  (settled); history is configuration management's.
- A directory moved by hand is found when exactly one other lister still
  lists it and one component of that name stands unlisted; `relate` carries
  the entry WITH its key. With two candidates the key is lost.
- `hwut.move` does the same in one step (needs `hwut-root.conf` above both).
- Unique but WRONG pairs are the known hole; o-12 makes them visible, it does
  not prevent them.
Questions for that session: should a wrong pair be preventable (confirm
list)? merge/split: an explicit command? what does RETIRED promise a
customer? is the suffix rule the right one for key renames?

## 5  How to work (recap of the proven procedure)

- Intend/spec/plan ritual and rulings into RATIONALE: skill
  `vut-work-discipline`; session loop and bundles: skill `vut-session`.
- Proof: copy the tree (`cp -a`) to a scratch directory, strip `TMP`, `OUT`,
  `__pycache__`, `hwut-traces*`, `hwut.log`, `.coverage`, `htmlcov`; run
  `hwut.run` there, compare the fail set with the 11 standing fails.
- THE SANDBOX VM RESTARTS BETWEEN TURNS and kills background jobs: run the
  census INSIDE one turn (detached with `setsid nohup`, polled with
  `sleep` < 10 min per call), never rely on it surviving a turn end.
- `hwut.sanitize forget` touches mtimes of test files: not real changes. The
  real change set is a diff against the last bundle, not `find -newer`.
- Bundle: `bash hwut/adm/bundle.sh --self --from-list <list> [--delete PATHS]
  -S 0 -o <file>`. Frank-Rene applies, commits and pushes; no push rights here.
- Function comments start `"""` + `RETURN: xxx, a <clear description> if
  success` / `yyy, else`.
