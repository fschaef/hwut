# Features of hwut from its documents — analysis, 2026-10-11

What hwut's documents CLAIM, held against what its tests PROVE. Made on
Frank-René's instruction ("All you find, but analyze"), on the tree of
bundle 109. The feature files (`<component>/TEST/hwut-features.conf`) are
the result; this file says what the analysis found on the way.

**Method.** Per component: README, RATIONALE, MANUAL, DISCUSSIONS and the
other documents listed below it, plus what `adm/WORK` (intend, spec,
gathered), `doc/` and the top `README.md` say of it. Claims were extracted
— behaviour a user or a caller relies on — merged where several entries
refine one behaviour, and mapped to test runs through PINNED lines, test
headers and GOOD files. Where two documents disagree the later one was
taken and the disagreement listed.

**What the words mean here.**

| Word | Means |
|---|---|
| UNPROVEN | a document claims it; no test run of that TEST directory proves it |
| NONSENSE? | a test run that proves nothing any document claims |
| documents silent | a test run proves real behaviour that no document states; the feature was written and linked, and the document owes the sentence |
| proven elsewhere | the claim stands in this component's documents, its test in another TEST directory; not stated as a feature here |

**Limits.** The analysis was made by reading, not by running: no test was
executed to check a claim. Large RATIONALE files were read through their
headlines and PINNED lines, entry bodies selectively. The features are an
analyst's reading of the documents, not Frank-René's statement; every
title is his to correct. Per-directory "Doubtful" sections name the weak
spots.

## Result

| TEST directory | features | proven | failing | unproven | NONSENSE? runs | test runs |
|---|---|---|---|---|---|---|
| `adm/TEST` | 25 | 15 | 0 | 10 | 0 | 11 |
| `auxiliary/TEST` | 11 | 8 | 0 | 3 | 0 | 8 |
| `bin/TEST` | 5 | 4 | 0 | 1 | 0 | 2 |
| `demo/python/TEST` | 10 | 9 | 0 | 1 | 0 | 6 |
| `engine/bookkeeper/TEST` | 31 | 27 | 0 | 4 | 1 | 38 |
| `engine/bookkeeper/test_run_info/TEST` | 8 | 7 | 0 | 1 | 0 | 4 |
| `engine/compare/TEST` | 55 | 50 | 0 | 5 | 2 | 77 |
| `engine/compare/core/edit_operations/TEST` | 9 | 7 | 0 | 2 | 0 | 16 |
| `engine/compare/engine/TEST` | 12 | 11 | 0 | 1 | 0 | 15 |
| `engine/compare/feeder/TEST` | 6 | 4 | 0 | 2 | 0 | 4 |
| `engine/compare/reading/TEST` | 13 | 12 | 0 | 1 | 0 | 13 |
| `engine/compare/region/potpourri/TEST` | 8 | 7 | 0 | 1 | 0 | 15 |
| `engine/compare/region/potpourri/solver/TEST` | 5 | 3 | 0 | 2 | 0 | 7 |
| `engine/coverage/TEST` | 11 | 11 | 0 | 0 | 0 | 9 |
| `engine/coverage/database/TEST` | 31 | 30 | 0 | 1 | 0 | 32 |
| `engine/coverage/readers/TEST` | 22 | 22 | 0 | 0 | 0 | 24 |
| `engine/display/TEST` | 29 | 27 | 0 | 2 | 0 | 29 |
| `engine/operations/TEST` | 31 | 29 | 0 | 2 | 4 | 51 |
| `engine/operations/consume/TEST` | 24 | 23 | 0 | 1 | 0 | 24 |
| `engine/operations/interaction/TEST` | 18 | 18 | 0 | 0 | 1 | 20 |
| `engine/operations/run/TEST` | 22 | 19 | 0 | 3 | 0 | 22 |
| `engine/orchestrator/exploration/TEST` | 56 | 54 | 0 | 2 | 0 | 79 |
| `engine/orchestrator/plan/TEST` | 23 | 21 | 0 | 2 | 0 | 25 |
| `engine/orchestrator/run/TEST` | 30 | 24 | 0 | 6 | 0 | 24 |
| `engine/orchestrator/scheduler/TEST` | 13 | 11 | 0 | 2 | 0 | 13 |
| `engine/procsitter/TEST` | 21 | 16 | 0 | 5 | 0 | 27 |
| `engine/protocol/TEST` | 3 | 3 | 0 | 0 | 0 | 3 |
| `services/TEST` | 232 | 210 | 0 | 22 | 2 | 302 |
| `services/lib/config/TEST` | 10 | 9 | 0 | 1 | 0 | 9 |
| `services/lib/labels/TEST` | 22 | 20 | 0 | 2 | 0 | 18 |
| `services/lib/viewers/keyed/TEST` | 38 | 35 | 0 | 3 | 0 | 46 |
| `test_writing_support/hwut_pype/TEST` | 38 | 32 | 0 | 6 | 0 | 20 |
| `test_writing_support/python/TEST` | 45 | 29 | 0 | 16 | 0 | 37 |
| **all** | **917** | **807** | **0** | **110** | **10** | **1030** |

`hwut.report.features --html=<file>` gives the same as a document; its
Tree tab, filtered to UNPROVEN, is the list of gaps.

## What stands out

Each is detailed in the component's section below.

- **GOOD files that record a failure.** A test page that ends in
  `FAILURE:` and is recorded as nominal passes for ever. Searched over
  every GOOD directory: one stands (below). A second was MADE during this
  work -- `services/TEST/test-cov.py [html]`, blessed unread after the
  coverage pages gained line anchors (bundle 108) -- and is repaired in
  bundle 109.
- **A recorded failure counted as a pass.**
  `engine/operations/interaction/TEST/test-tui.py [elements]`: its GOOD
  file records `FAILURE: every element kind renders ...` with five FAIL
  lines; the book says ok because the output equals that GOOD.
- **Documents behind the code.** `engine/compare/MANUAL.txt` still claims
  a slash switch, "regions always work" and constraints over earlier
  variables only (removed or changed by C-18, C-4, C-19) and does not know
  the `unaccepted` and `constraint-violation` regions.
  `engine/orchestrator/run/README` names 'linear' as the default strategy
  (O-29/O-31: successor). `engine/bookkeeper/README` names
  `GOOD/test_ids.dat`; the register lives in `book.csv`.
  `engine/display/README`'s line format, nicknames and FAILURES block are
  stale against D-9/D-15/D-35. `engine/orchestrator/exploration/README`
  sections 2, 3, 8, 10 are stale against R-69, R-77, R-80.
  `engine/orchestrator/README.txt` describes the bookkeeper.
- **A document against a test.** pype MANUAL 8 calls `"abc"` and
  `"abc" "def"` disjoint and dispatch order-free; `test-pype.py [patterns]`
  shows both matching, the earlier handler winning.
- **Claimed, and nowhere in the tree.** `wave-build` / `MultiBuild`
  (operations/run README-provider 4): no `multi_build.py` exists.
  `HWUT_NO_TERMINAL`: no test names the word. Block-scoped realignment
  (operations README 11.7) is presented as in force; DISCUSSIONS todo-16
  says it is owed.
- **Whole modules documented and untested here.** `hwut_runner` (11
  claims, all UNPROVEN); ten `adm` tools; `engine/protocol` has no
  document at all.
- **Tests of nothing claimed.** The four `test-hygiene.py` runs
  (operations), `regression-2.py [csp]`, `[edit-merge]` (compare),
  `test-bookkeeper.py [setup_delta]`, `test-cmdline.py [phantom]`,
  `test-header-words.sh [values]`.
- **Headers out of step with blocks.** Several tests describe choices
  their block does not declare, or the reverse (`test-test_id_db.py`,
  `test-pype.py`, `test-ignore.sh`, `test-remove.sh`,
  `test-endtoend.py`).

## The documents

```
   152 ./adm/LAYERING.txt
   393 ./adm/PHILOSOPHY.txt
   390 ./adm/WORK/RATIONALE-INDEX.txt
   446 ./adm/WORK/RATIONALE-LOGIC.txt
   289 ./adm/WORK/README-INDEX.txt
    92 ./adm/WORK/skill/way-of-working.md
    86 ./auxiliary/RATIONALE-directory_mutex.txt
    64 ./auxiliary/README-directory_mutex.txt
    60 ./bin/README.txt
   415 ./doc/HOWTO-FEATURES.txt
   777 ./doc/HOWTO-HWUT-BRAINSTORM.txt
   825 ./engine/bookkeeper/RATIONALE.txt
   167 ./engine/bookkeeper/README.txt
   139 ./engine/bookkeeper/test_run_info/RATIONALE.txt
   105 ./engine/bookkeeper/test_run_info/README.txt
   178 ./engine/compare/FEATURE-happy-constraints.md
   528 ./engine/compare/MANUAL.txt
   776 ./engine/compare/RATIONALE.txt
   113 ./engine/compare/README.txt
     2 ./engine/compare/TEST/FIXTURE/README.txt
   113 ./engine/compare/engine/README-constraint_namespace.txt
   154 ./engine/compare/region/potpourri/solver/README.txt
   302 ./engine/coverage/DISCUSSIONS.txt
   270 ./engine/coverage/HOW-TO-INTEGRATE-A-COVERAGE.txt
   194 ./engine/coverage/OVERVIEW-coverage-roads.txt
  1856 ./engine/coverage/RATIONALE.txt
   693 ./engine/coverage/README.txt
  1168 ./engine/display/RATIONALE.txt
   111 ./engine/display/README.txt
   382 ./engine/operations/DISCUSSIONS.txt
   140 ./engine/operations/RATIONALE.txt
  1278 ./engine/operations/README.txt
   172 ./engine/operations/run/README-provider.txt
   311 ./engine/orchestrator/RATIONALE.txt
   135 ./engine/orchestrator/README.txt
  2380 ./engine/orchestrator/exploration/RATIONALE.txt
   994 ./engine/orchestrator/exploration/README.txt
   284 ./engine/orchestrator/plan/RATIONALE.txt
   221 ./engine/orchestrator/plan/README.txt
  1262 ./engine/orchestrator/run/RATIONALE.txt
   199 ./engine/orchestrator/run/README.txt
    75 ./engine/orchestrator/scheduler/RATIONALE.txt
    71 ./engine/orchestrator/scheduler/README.txt
   677 ./engine/procsitter/MANUAL.txt
    14 ./services/DISCUSSIONS.txt
  6001 ./services/RATIONALE.txt
   663 ./services/README.txt
   604 ./test_writing_support/hwut_pype/MANUAL.txt
   178 ./test_writing_support/hwut_pype/README.txt
    88 ./test_writing_support/python/RATIONALE-hwut_runner.txt
   185 ./test_writing_support/python/README-hwut_hocon.txt
   140 ./test_writing_support/python/README-hwut_runner.txt
   216 ./test_writing_support/python/README-hwut_vterm.txt
 27528 total
   390 adm/WORK/RATIONALE-INDEX.txt
   446 adm/WORK/RATIONALE-LOGIC.txt
   289 adm/WORK/README-INDEX.txt
  1190 adm/WORK/TODO.txt
    45 adm/WORK/gathered/02-disc-1-document-consistency.txt
    74 adm/WORK/gathered/04-todo-1-judgement-timing.txt
    60 adm/WORK/gathered/05-todo-1-tree-model.txt
    19 adm/WORK/gathered/07-disc-1-provisional-choices.txt
    33 adm/WORK/gathered/09-disc-1-provisional-choices.txt
    12 adm/WORK/gathered/0b-todo-1-run-face.txt
    24 adm/WORK/gathered/0c-todo-2-placement-backend.txt
    10 adm/WORK/gathered/0d-disc-1-scenario-kinds.txt
    13 adm/WORK/gathered/0e-disc-2-multi-directory.txt
    44 adm/WORK/gathered/0f-disc-3-provisional-choices.txt
    15 adm/WORK/gathered/0g-todo-4-special-key.txt
    16 adm/WORK/gathered/0h-todo-7-collision-groups.txt
    35 adm/WORK/gathered/0k-disc-3-compare-confs.txt
    46 adm/WORK/gathered/0n-disc-6-hwut-2-residue.txt
   160 adm/WORK/gathered/0o-disc-7-cadence-theory.txt
    91 adm/WORK/gathered/0q-disc-9-face-inventory.txt
   108 adm/WORK/gathered/0r-todo-1-hwut-renovate.txt
   118 adm/WORK/gathered/0s-todo-2-command-line-completion.txt
    54 adm/WORK/gathered/0t-disc-1-test-sequence-form.txt
    19 adm/WORK/gathered/0u-disc-2-tree-walk-laws.txt
    40 adm/WORK/gathered/0v-disc-4-formal-configuration-spec.txt
    76 adm/WORK/gathered/0x-todo-1-owner-defaults-relocation.txt
    34 adm/WORK/gathered/0y-todo-2-instantiation-blessing.txt
    40 adm/WORK/gathered/10-todo-4-caps-vocabulary.txt
    52 adm/WORK/gathered/13-todo-7-hwut-parse-service.txt
    31 adm/WORK/gathered/14-todo-7-variant-restates-language-entry.txt
   186 adm/WORK/intend/00-configuration.txt
   128 adm/WORK/intend/01-work-structure.txt
    47 adm/WORK/intend/19-matching-separated.txt
    83 adm/WORK/intend/20-bundled-strategy.txt
    77 adm/WORK/intend/22-moving-and-renaming.txt
    38 adm/WORK/intend/23-features.txt
   452 adm/WORK/plan/01-work-structure.txt
   276 adm/WORK/review-r1.txt
  1980 adm/WORK/review-r10.txt
   263 adm/WORK/review-r5.txt
   186 adm/WORK/review-r6.txt
   143 adm/WORK/review-r7.txt
   183 adm/WORK/review-r8.txt
   168 adm/WORK/review-r9.txt
   183 adm/WORK/ruling-census-before.txt
   248 adm/WORK/spec/01-work-structure.txt
   347 adm/WORK/spec/23-features.txt
   415 doc/HOWTO-FEATURES.txt
   777 doc/HOWTO-HWUT-BRAINSTORM.txt
   130 doc/OLD/DOC-DISCIPLINE-RECOMMENDATION.txt
    44 doc/OLD/HOWDO.txt
    49 doc/disc-hwut-amend.txt
    41 doc/disc-hwut-lint.txt
    44 doc/manual-note-face-tests-test-the-face.txt
    53 doc/manual-note-painting-and-tdd.txt
    67 doc/manual-note-pype-is-part-of-the-oracle.txt
    44 doc/manual-note-representation-blast-radius.txt
   107 doc/note-independence-coverage-build.txt
    18 doc/note-narrative-and-scenario-coverage.txt
    56 doc/note-neighbouring-tools.txt
    87 doc/note-positioning-and-adoption.txt
 10504 total
```

(Not in this list and read all the same: `engine/compare/ARCHITECTURE.txt`, `engine/compare/DOC/SEMANTICS.txt`.)


---

# Findings: services

# Findings — label `services`

## hwut/services/TEST

documents read: `hwut/services/README.txt` (whole); `hwut/services/RATIONALE.txt` (index of E-1 … E-148 with PINNED lines; DECISION read for E-10, E-11, E-15, E-33, E-58, E-72, E-80, E-83, E-97, E-135, E-136, E-141); top `README.md` (whole); `hwut/bin/README.txt`; `hwut/doc/HOWTO-FEATURES.txt`; `adm/WORK/spec/23-features.txt`; `adm/WORK/intend/22-moving-and-renaming.txt`, `intend/00-configuration.txt` (grep); `adm/WORK/gathered/0q-disc-9-face-inventory.txt`, `0b-todo-1-run-face.txt`, `0s-todo-2-command-line-completion.txt` (head); `--help` of all 49 launchers (read in full for the faces tested here; the wish block once); the header of every test file; GOOD files where a header and a document disagreed.

features: 232  (proven-by-link 210, unproven 22)   NONSENSE? runs: 2   (302 test runs in 44 files)

The count is above the expected 100–180: 49 faces, and option-level claims of `--help` are kept apart where a gap could hide behind a merged sentence. Name prefixes: `face-`, `wish-`, `run-`, `spec-`, `plan-`, `config-show-`, `accept-`, `interactive-`, `diff-`, `play-`, `stability-`, `report-…`, `help-`, `sanitize-`, `remove-`, `rename-`/`move-`, `execute-`, `cov-`, `about-`, `pype-`, `dev-`, `renovate-`.

Verification: `hwut.report.features --directory=services` — OUTSIDE THE RELATION holds the two NONSENSE? runs and nothing else for `services/TEST`; `hwut.config.show --directory=services/TEST --no-default` — no SYNTAX / VOCABULARY / REFUSED line; every test file differs from its state before in `features = [...]` lists only (compared mechanically; the files as they were are in `S/svc-backup/`). The generator of conf and links is `S/svc_gen.py`.

### UNPROVEN — claimed, no test here

- face-sigpipe-quiet: a reader that hung up ends the face quietly with 141 — README 'EXIT STATUS', E-1. `test-exit.sh signal` drives SIGTERM (143) and Ctrl-C (130) only.
- face-directory-option: every face takes `--directory=<path>` — README first paragraph, README.md. No run proves it for "every" face; see Contradictions (several faces do not take it).
- wish-exclude: `--exclude <target>` outranks every include — E-15. No test file here types `--exclude `.
- run-no-store: no subject recorded, the verdict still booked — README 'hwut.run', `--help`. The word appears in `engine/display/TEST` only.
- run-jobs: `--jobs=<n>` bounds the work standing at once — README, README.md. Here `--jobs` is a fixture word; `face-words coverage_serial` shows overlap under `--jobs=3`, not the bound.
- config-show-directory-fault: a directory with one broken header prints the fault, then the tree of what stands, status 1 — README, paragraph after the list of faces. `test-config-show.py faults` shows the broken file ALONE.
- config-show-ids: `--show-ids` prints the register, VANISHED marked — `hwut.config.show --help`. The word appears in `engine/bookkeeper/TEST` only.
- config-show-verbose: null parameters written — `--help`.
- accept-dont-ask: suppresses the question, decides nothing — E-68, E-70. `--dont-ask` is never typed at `hwut.accept` in `test-accept.sh`.
- accept-force-run: runs every selected case first — README, `--help`. `--force-run` is typed in no test of the tree.
- accept-walks-tree: a bare `hwut.accept` walks the tree — README.
- accept-propose-only-divergence: no candidate / no nominal / equivalent / broken run are never proposed — README, E-44. `face-words propose` shows the divergence and the bound only.
- accept-apply-answers-every-line: a target that matched nothing is answered too — README 'hwut.accept.apply'.
- interactive-force: `hwut.accept.interactive --force` — `--help` only.
- diff-nothing-selected: `hwut.run.diff` exits 3 where no case is selected — README 'hwut.run.diff'.
- report-timings-recursive: `-r` walks the tree — `--help`.
- report-features-unnumbered: a feature without a number is reported `#-` — spec 23, o-6.
- rename-stain-follows: the book entry moves with any stain — `hwut.rename --help`.
- rename-stages-in-vcs: a move stages the touched paths and asks about committing — intend 22, 6.2. The intend itself says NOT BUILT.
- rename-copies-without-vcs: copy, remove script, note in the book's header — intend 22, 6.3. NOT BUILT, as the intend says.
- cov-run-cap-refused: `hwut.cov.run` exits 2 for an unenforceable cap — E-135. `test-run-uncapped.sh` drives `hwut.run`, `hwut.plan` and four other doors, not `hwut.cov.run`.
- dev-container-no-engine: neither podman nor docker is a fault by name — `hwut.dev.podman.build --help`.

### NONSENSE? — test runs proving nothing claimed

- test-cmdline.py [phantom]: `option_tuple` takes a word only where a dash begins it — an inner rule of the suggester's helper; no document states it as behaviour.
- test-header-words.sh [values]: a string wears double quotes, numbers in five radices with `_` — exploration R-49, R-62; no document of services claims it (the proof belongs to `engine/orchestrator/exploration/TEST`).

Could NOT be unlinked although they prove structure only, because the test states `choices = [...]` as a list and the link stands at the root (block form kept as instructed): test-cov_visitor.py [vocabulary], [walk] (the visitor's method vocabulary and traversal order); test-face-records.py [plain], [split] (record field types, the acting split from the saying); test-refresh.py (drives the engines' functions, not the faces — its header says so). Likewise test-exit.sh [law] carries `face-signal-ends-quietly` and [signal] carries `face-exit-status-law`, test-base-questions.py, test-preferences.py, test-renovate.sh, test-enter.sh and test-sanitize-scenarios.sh link every choice to every root feature: the root list is the union. A per-choice `choices { }` form would make these exact.

### Documents silent — behaviour tested, stated nowhere

Stated nowhere in the documents of services; where an engine RATIONALE holds the ruling, the feature names it in `documents`.

- run-table-separator: test-book-defects.sh [table-sep] — belongs in compare's MANUAL/RATIONALE (table region); only the test header says it.
- run-test-directory-name: test-book-defects.sh [test-directory] — `test_directory` and "the same result above and inside" belong in exploration's README.
- diff-fault-side: test-book-defects.sh [frame-side] — 'hwut.run.diff' in services/README (the FAULT line naming output or nominal).
- play-empty-explained: test-play.sh [silent], [why] — `hwut.run.play --help` names EMPTY (3) but not the explanation (call, PATH, exit, channels).
- wish-wishlist-elided: test-wishlist.sh [elided] — the ditto marks `:/` and `:/:` are mentioned in passing in E-30 and E-96; the format stands in no README and no `--help` (the SELECTION block's '--wishlist' says nothing of it).
- labels-query-here: test-face-words.sh [query_here] — "ruled 2026-10-09 (f-7)" per the test header; no RATIONALE entry. Belongs with E-19/E-20 or in `services/lib/labels`.
- run-cap-refused-every-door: test-run-uncapped.sh [doors], [plan] — E-135 names `hwut.run` and `hwut.cov.run` only.
- execute-command: test-execute.sh [command], [command-refused] — `hwut.execute -c` stands in `--help` only; README 'hwut.execute' and E-7 do not know it (E-7: "One target per invocation").
- config-show-labels: test-config-show.py [labels] — one clause inside E-19's DECISION ("'hwut.show' answers section 6"); README 'hwut.config.show' and its `--help` say nothing of the LABELS section.
- sanitize-rerun-trigger: test-sanitize.sh [apply], [command], [orphans] ("TOUCHED (the re-run trigger)") — `hwut.sanitize --help` only; README and E-125 silent.
- stated in `--help` only, not in README or RATIONALE: stability-counts-not-numbers, diff-setup-options, play-build-failure, report-timings-recursive, config-show-ids, config-show-verbose, interactive-force, rename-stain-follows, dev-container-no-engine.
- engine rulings proven through the faces here and absent from services' documents (cited to the engine RATIONALE): run-execute-expansion (R-68), run-same-nominal (R-45, B-30), run-directory-frame (R-31…R-36), run-dependency-cycle (R-33, R-35), run-pattern-before-number (C-14), diff-search-budget (C-16), run-pype-defect-fails (O-18), run-book-as-left (B-4, B-8, B-10, B-27), walk-no-entry (R-85), spec-block-found (R-9, R-72), spec-one-carrier (R-7, R-52, R-53), plan-session-node (P-5), cov-run-serial (coverage D-22).

### Proven elsewhere

- `hwut.report.wallflowers` — README.md 'Report' — `services/lib/config/TEST`.
- `hwut.config.ignore` — README.md — `services/lib/config/TEST`.
- `hwut.labels.create/add/remove/list`, the label expression language, hand comments surviving (E-19, E-24, E-96, E-106, E-112) — `services/lib/labels/TEST`. Only `labels.query`'s caller-relative output is proven here.
- `hwut` alone is `hwut.run`; every launcher answers by PATH and by path (E-8, E-15, bin/README) — `bin/TEST` (E-138 PINNED 'bin/TEST/test-launchers.sh answer').
- The keyed session: three takes, two cursors, the tolerance pane, the foot, unpaired lines (README 'the keyed session', E-61, E-63, E-64, E-75 … E-77, E-86 … E-94, E-117, E-118, E-120, E-121, E-142) — `services/lib/viewers/keyed/TEST` (PINNED in E-142).
- The run's flow rendering: `--show-timing`, `--show-jobs`, `--show-details`, `--no-failure-summary`, `--log`, `--colour`/`--no-colour`, `--dbd`, the repeat mark, the arrow, the count badge `||n` (E-30, E-33, E-69, E-71, E-97; `hwut.run --help`) — `engine/display/TEST` (the words appear there; not checked run by run).
- The live raw stream of `hwut.run.play` at a terminal (E-83) — `engine/operations` 'test-provider.py live' (named in E-83's COST).
- The pype language (`--trace`, `--dry-run`, `--example`, modes, handlers) — `test_writing_support/hwut_pype/TEST`.
- The feature adaption behind `relate`, `unrelate`, `hwut.move` — `engine/orchestrator/exploration/TEST/test-feature_adapt.py` (named by test-sanitize-relations.py).
- Rename within a directory — nominals, candidates, book, register — "exercised under the bookkeeper's own suites" (test-rename.sh header); here the labels and the across-directory case.
- `--since`/`--until` and the points as a parser — `engine/orchestrator/plan/TEST/test-wish.py` (named by test-plan.py).

### Contradictions and stale statements

- README.md 'Report' lists `hwut.report.wishlist`; E-137 renamed it `hwut.report.list`, and `bin/` holds `hwut.report.list` only. E-58's DECISION still spells `hwut.report.wishlist --unaccepted`.
- README.md 'Status': "911 ok, 1 fail (`services/TEST/test-dev_podman.py refused`)"; `services/TEST/GOOD/book.csv` records that run as passing (the feature report shows 0 failing).
- services/README 'hwut.accept': "THE UPDATE CHECK … a recording whose mtime is older than the test file's is refused, by name" (E-39) and, a few lines on, "It RUNS ON NECESSITY: a case whose recording is older than its source is run" (E-40, E-122). The tests (`accept refresh`, `play accept_runs`) show the latter; the feature is stated so.
- services/README 'hwut.accept.propose': "a file to hand back to 'hwut.accept -f'"; same README, 'hwut.accept': "It does not read a file of targets: that is 'hwut.accept.apply'". `hwut.accept --help` has no `-f`.
- `hwut.accept --help` DESCRIPTION: "blesses every candidate the wish selects that has no nominal yet -- the FIRST pole"; README, E-60 and README.md: a first acceptance without `--force` records the undecided shape. The header of `test-accept.sh` repeats the old sentence for [bless]. Feature stated as E-60/E-109.
- services/README first paragraph and README.md: "Every face … takes '--directory=<path>'"; the USAGE of `hwut.about`, `hwut.affected`, `hwut.pype`, `hwut.cov.formats` and the `hwut.cov.conv.*` faces has none.
- services/README 'EXIT STATUS': 2 means "the command line cannot be READ"; E-135: `hwut.run` exits 2 where a case is refused for want of a cap although the command line read (test-run-uncapped.sh [refused]). Neither the README's table nor `hwut.run --help` EXIT STATUS was amended.
- services/README: "one enum EVERY face relates to"; test-exit.sh [law] holds five faces (config.show, plan, run, pype, run.diff).
- test-plan.py header, [wish]: "a glob matching nothing -- an empty plan and a report, status 0"; its GOOD, `hwut.plan --help` and E-2 say status 3.
- services/README 'hwut.run.diff': "exit 0 equivalent, 1 shown differing, 2 unusable, 3 no case selected"; the NAME line of `hwut.run.diff --help` knows 0 and 1 only, and E-141's "1 for an equivalent, stained case" stands in neither.
- services/README's closing sentence ("a directory with one broken header prints the fault, then the tree or the plan of what stands") against `hwut.config.show --help` ("A specification carrying a fault yields its faults and no tree"). For one file the test shows faults and no tree; for a directory nothing is shown (see UNPROVEN).
- `hwut.config.show --help`: USAGE lists `--root-conf-template` and no `--show-ids`; DESCRIPTION and OPTIONS describe `--show-ids` and never `--root-conf-template`. The face takes both.
- services/README: "hwut.execute (target.py)"; the module is `services/execute.py`.
- test-stability.sh header, [refused]: "a bad '--rt-max', a bad '--epsilon'"; the GOOD shows both refused as words the face does not take. Its [bytes] line says "A warning" without the `--byte-pedantic` E-113 requires (the GOOD carries it).
- `adm/WORK/intend/00-configuration.txt` line 144: "'hwut.parse' shows every effective value WITH ITS ORIGIN"; no `hwut.parse` stands — it is `hwut.config.show --provenance`.
- `hwut/bin/README.txt` lists 33 of the 48 `hwut.<name>` shims; missing: accept.apply, accept.interactive, accept.propose, config.ignore, labels.add/create/list/query/remove, remove.apply, remove.propose, renovate, report.timings, report.wallflowers, run.play.
- `hwut.accept.interactive --help` and `hwut.run.diff --help` are argparse dumps under NAME/USAGE/DESCRIPTION, without EXIT STATUS and without EXAMPLE.
- RATIONALE numbering: no E-98 and no E-100.

### Doubtful

- face-directory-option is left UNPROVEN on purpose: dozens of runs use `--directory`, none proves "every face", and the sentence as written is false for several faces. Either the sentence or the faces should move.
- face-exit-status-law is linked to test-exit.sh only (five faces); the `refused` and `empty` choices of the other faces prove single cells of the law and are linked to `face-refusal-by-name` / `face-empty-said`.
- path-word-enters claims "every face that takes test words" (twelve named in README '_target.py'); proven here on report.list, run, config.show, run.diff, report.details.
- wish-faster-than is linked through test-base-questions.py as a whole (root link); its [asked] GOOD shows `--faster-than=100000   status 1`, i.e. the face answers — which cases it selects is not on the page.
- run-stderr-fails rests on test-help.sh [explain], where the run's 'unexpected stderr' failure is the fixture for `hwut.help`; no run here is about `stderr_ignored = true` at `hwut.run` (at `hwut.accept` it is: [stderr]).
- run-timing rests on the stability choices [cadence], [length], which run with `--timing` internally.
- accept-whole: `--force` and `--whole` are typed; `--as-is` is typed in no test of the tree.
- interactive-session / interactive-first-nominal are proven through `test-accept.sh [interactive], [opening]` with the line-based session; the screen itself is the keyed TEST directory's.
- rename-stages-in-vcs / rename-copies-without-vcs are RULED and, by the intend's own words, not built: stated as features because a document claims them.
- `gathered/0s-todo-2-command-line-completion.txt` (shell completion, "DESIGN, NOT BUILT") and `gathered/0b-todo-1-run-face.txt` ('hwut.run --format', "LABOUR OWED") are designs, not claims: no feature. `face-completion-table` covers only the table a face prints.
- `hwut.renovate --help` lists what it "DOES NOT DO YET" (the books, the stderr survey, the proof on the real quex tree): owed work, no feature.
- test-header-words.sh [climb] ("under 'TEST/TMP' the climb ends: no tree", exploration R-76) is linked to `tree-boundary-refused`: the same refusal reached another way, not E-25's own sentence.
- 16 features carry no `documents`: their claim stands in a `--help` text only, or in a test header only; the explanation says which. `--help` texts live in the services' sources, which were not named as documents.
- The engine RATIONALE ids cited (R-…, C-…, B-…, D-…, O-…, P-…) were taken from the test headers and checked to exist as headlines in the named file; their DECISIONs were not read.

---

# Findings: lib-bin-adm-aux

# Findings — lib-bin-adm-aux

Verified for all six: `hwut.report.features` shows no OUTSIDE THE RELATION entry; `hwut.config.show --no-default` shows no SYNTAX / VOCABULARY / REFUSED line; choice sets unchanged. No test was run.

## hwut/services/lib/config/TEST
documents read: `--help` of hwut.config.ignore, hwut.config.show, hwut.report.wallflowers (texts in `lib/config/ignore.py`, `show.py`, `lib/report/wallflowers.py`); services/README.txt (hwut.config.show); services/RATIONALE.txt E-54, E-99, E-116; engine/orchestrator/exploration/RATIONALE.txt X-SILENT; exploration/README.txt (wallflowers)
features: 10  (proven-by-link 9, unproven 1)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- ignore-asks-first: the face shows and asks before writing unless `--dont-ask` — help; X-SILENT COST. Every call in test-ignore.sh carries `--dont-ask`.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- show-defaults-merged: test-show.sh [app_defaults] — the help of hwut.config.show says only "defaults resolved"; that a directory's `app_defaults` is merged leaf by leaf over the root's belongs in that help / services README.
- stray-parameter-refused: test-show.sh [stray] — stated only in passing in E-99 ("MEASURED: a root 'tolerance' is refused"); the VOCABULARY fault is in no help.
### Proven elsewhere
- hwut.config.show: resolved tree, one file, faults-and-no-tree, labels section, provenance — help, services README — services/TEST/test-config-show.py
- `--gnu`, `--show-ids` (VANISHED mark), `-v`, `--root-conf-template`, "can be read back (R-50)" — help — not checked whether services/TEST proves them; none is proven here.
- the wallflower list itself, the closing NOTE — X-SILENT — exploration / services TEST.
### Contradictions and stale statements
- services/README.txt lists `hwut.config.show` among the faces but has no entry for `hwut.config.ignore` nor `hwut.report.wallflowers`.
- services E-54 names the suite `test-config-show.py` as following the face; a second suite for the same face now stands in lib/config/TEST (test-show.sh); nothing says which owns what.
- test-ignore.sh header cites "E-48" for "touches nothing else"; E-48 has no headline hit for that in services/RATIONALE's index (reference not followed up).
### Doubtful
- ignore-refusals: the help also refuses "a path naming a directory"; [refused] shows only a file that does not exist. Linked anyway.
- X-SILENT leaves OPEN that a directory's own `ignore` REPLACES the inherited one; not a feature, not tested here.

## hwut/services/lib/labels/TEST
documents read: `--help` of the five hwut.labels.* faces; services/README.txt (labels family); services/RATIONALE.txt E-19, E-20, E-24, E-96, E-106, E-112
features: 22  (proven-by-link 20, unproven 2)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- query-skips-orphans: an entry naming a run the tree no longer offers is not printed — help of hwut.labels.query, "THE DOMAIN"
- broken-file-is-fault: a broken labels file is FAULT (1), nothing written / printed — the five helps' EXIT STATUS; E-20 (services/TEST/test-config-show.py has "a broken labels file" for config.show only)
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- labels-accumulate: test-add.sh [standard] — that an application's entry and a choice's own entry unite is in no help and no RATIONALE entry; belongs in the help of hwut.labels.add or the file's header rule (E-96).
- reserved-names-refused: test-create.sh [doors] — the help says only "or is reserved"; which names (keywords, `all`, `meta`) is stated nowhere.
### Proven elsewhere
- the query prints paths relative to the caller's directory — E-106 AMENDED 2026-10-09 — services/TEST/test-face-words.sh query_here
- an undeclared label refused at every wish-taking face — E-19 AMENDED — services/TEST/test-face-words.sh label_unknown
- `-l` is `--label`; the hint on a bare word naming a label — E-112 — services/TEST/test-run.sh short-form
- names followed on rename/remove (`_follow.py`), the LABELS section of config.show — E-20 — services/TEST
- 'meta' silent in a bare wish at run/plan/report/accept — E-19, E-20 — services / engine plan TEST
### Contradictions and stale statements
- E-19 COST: "a hand comment does not survive a write" — E-96 rules the opposite; the feature follows E-96.
- E-19/E-20 still say `hwut.report.wishlist`, `hwut.show`, `hwut.stability`, `hwut.rename-choice`; E-54/E-111/E-137 renamed them.
- The first pass's test header (test-query.sh "silence") lists the grammar as 'AND', 'NOT', ','; help and E-19 add 'OR' and brackets — both are exercised ([forms] uses OR, [silence] brackets).
- The help of create says a glob warns where it meets only silenced runs ("a glob does not [override], it warns instead"); here only "met nothing" is shown.
### Doubtful
- The silenced-glob warning (E-19) is the wish's behaviour, not the label faces'; not stated here, proof not located.
- stateless-wish-refused is linked to test-remove.sh [delete] for the "asked for in words" half (`--label concern`).

## hwut/services/lib/viewers/keyed/TEST
documents read: services/README.txt ("the keyed session", hwut.accept.interactive); services/RATIONALE.txt E-61, E-63, E-64, E-75–E-77, E-79, E-86, E-87, E-89–E-95, E-117–E-121, E-136, E-142
features: 38  (proven-by-link 35, unproven 3)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- region-take: 'a' takes this region into its associated region — README "THREE TAKES", E-61. `E_Act.TAKE_REGION` occurs in no test; only its keymap row is printed.
- label-shares-first-row: the region label displaces the first filler on the screen — E-64 (its COST says "one projection GOOD moved"; no GOOD of this directory shows it)
- stderr-warning: the foot says the case's stderr spoke — E-91, E-136
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- none outright; `proposals-only-news` ("nothing differs: nothing proposed") rests on one clause of E-120.
### Proven elsewhere
- the fallback to the line-based tier where 'prompt_toolkit' does not import (`driver_for`) — README "THE SEAM", E-61 — engine/operations/interaction/TEST/test-merge.py, test-tui.py
- a tried tolerance asked about at the end ([1] TMP file, [2] header, <enter>) — E-119, `lib/accept/keep.py` — not in this directory; proof not located
- the book entry after save follows a check; 'saved [FAIL]' — E-89 AMENDED — services/TEST/test-accept-door.py ask_no, ask_quit, ask_save, short
- the keyed colours as preferences — E-87, E-90 — services/TEST/test-preferences.py defaults
### Contradictions and stale statements
- Foot layout: test-keyed.py [header] GOOD prints "<F1>=help at the left, whole hints right-aligned" (E-93) and shows no <F5>/<F6>; E-121 (later) rules the foot left-aligned, function keys first, and test-editing.py [foot] shows that. `project.banner` as driven by [header] is the pre-E-121 form. [header] is linked to screen-titles only.
- The first pass stated "nothing is proposed where a word stands on one side only"; E-120 and GOOD test-proposal.py--nothing.txt show a `nothing = ["<word>\\s*"]` proposal. Feature restated (propose-nothing-pattern).
- Realign key: E-61 'r', E-89 'g', E-92 'z'; README says 'z'. Later stands; E-61/E-89 are not marked amended.
- E-89 body "'q' is DONE and writes GOOD" vs its AMENDED 2026-10-09 ('q' asks, leaves without saving). E-121 still lists "q=done". README's keyed section does not mention 's'/'S'/'Q' at all.
- E-91 foot text "'q' will be refused without '--stderr-tol'": the option retired (E-110/E-136).
- E-76 "grey-green band" amended to "light grey on #303030"; no test records colours of the spent band.
- README and tests cite "intend 21"; `adm/WORK/intend/` holds no 21.
- E-86/E-87 header row ("top header", 'F1=help' right edge) superseded by E-90 "no header row"; not marked.
### Doubtful
- spent-lines linked to [token] and [remove]: they show the spent set and the re-takeable line, not "no cursor stands on a spent line" directly.
- element-status: [element] proves the status text for a number; the 'w'/'b' stepping itself is a key path not driven.
- foot-keys linked to test-screen.py [open] beside [foot].

## hwut/bin/TEST
documents read: bin/README.txt; top README.md (launcher table); services RATIONALE E-78 (headline), E-54
features: 5  (proven-by-link 4, unproven 1)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- dash-for-underscore: a launcher's name carries '-' where the module has '_' — README. No launcher of bin/ carries a '-' today: the rule has no instance.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- none
### Proven elsewhere
- `.hwut.conf` as the installation's default preferences, `~/.hwut.conf` read over it key by key — README, services E-78 — services/TEST/test-preferences.py (presumed)
### Contradictions and stale statements
- README: "hwut.<name> runs 'python3 -m hwut.services.<name>'" — a dotted face runs `hwut.services.lib.<family>.<name>` (bin/hwut.run.diff: `-m hwut.services.lib.run.diff`), as E-54 rules.
- README's launcher list is incomplete: missing hwut.accept.propose/.apply/.interactive, hwut.config.ignore, hwut.labels.*, hwut.remove.propose/.apply, hwut.renovate, hwut.run.play, hwut.report.timings, hwut.report.wallflowers.
- README: "TEST/ drives every launcher". test-launchers.sh's FACE_LIST omits hwut.config.ignore, hwut.report.features, hwut.report.timings, hwut.report.wallflowers (49 launchers stand; 45 are driven). launcher-per-face is linked nevertheless.
- README: "the PATH and by-path forms agree" — [path] checks ONE launcher (hwut.config.show).
### Doubtful
- bare-hwut-is-run: [answer] shows `hwut --help` giving hwut.run's first line, not a bare run.

## hwut/adm/TEST
documents read: adm/DEVELOPMENT.txt, adm/LAYERING.txt, adm/requirement-list.txt; usage/docstrings of bundle.sh, import_graph.py, book_stain.py, dependency.py, unread_modules.py, good_audit.py, rescue_goods.py, fail_book.py, requirement-check.sh (PHILOSOPHY.txt, ROLL-OUT.txt name no tool; SIGNATURE_UI_PROTOCOL.txt is empty)
features: 25  (proven-by-link 15, unproven 10)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- bundle-selection: git / find / `--since` / `--from-list`, `-x`, `-X`, `--exclude`, `-S` — bundle.sh usage
- bundle-dependencies: `--deps`, `--app` — bundle.sh usage, dependency.py docstring
- bundle-documents-by-default: `--no-doc` — bundle.sh usage
- bundle-chmod-script — bundle.sh usage
- unread-modules — unread_modules.py docstring
- static-analysis-needs-ruff: missing ruff is a stated precondition — DEVELOPMENT "NO RUFF, NO REPORT" (the branch exists in the test; the recorded run has ruff)
- requirement-check — requirement-check.sh head, DEVELOPMENT
- good-audit, rescue-goods, fail-book — the tools' docstrings
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- unreadable-reported: test-import_graph.sh [unreadable] — only an inner function docstring says it; belongs in the tool's head docstring / DEVELOPMENT.
- graph-refusals: test-import_graph.sh [refused] — stated nowhere.
- stain-conversion "reads back through the bookkeeper" (first pass): the docstring claims only the conversion; the read-back is tested, not documented.
### Proven elsewhere
- none known
### Contradictions and stale statements
- DEVELOPMENT "STATIC ANALYSIS -- THE RATCHET": "one more instance of a tolerated kind ... moves the GOOD and the suite says so". test-static-analysis.sh header (ruled 2026-10-09): it is a status report, tolerated findings are comment lines, only MUST STAND AT ZERO is compared. Feature follows the ruling; DEVELOPMENT is stale.
- DEVELOPMENT: the 'hwut' choice "records the real tree's outer picture and its layering, so a change to either shows up as a moved GOOD". The choice's eq_patterns now tolerate any module list, any edges and either judgement; only a refusal, a crash, or a component added/missing shows.
- DEVELOPMENT writes the key `eq-pattern`; the tests write `eq_pattern`.
- DEVELOPMENT's first FORMATS list omits 'svg' (named 100 lines later); the tool's docstring lists five.
- DEVELOPMENT names only `--exclude` patterns and direction rules for `--check`; SEALED and DOOR are stated in the tool and LAYERING.txt only.
### Doubtful
- cythonizer.py, python_tracer.py, version.py, find-files-without-license-note.sh, remove_trailing_whitespace.sh: no claim worth a feature (no docstring claim, or a one-liner); left out.
- graph-of-this-tree proves little by construction (everything but the frame is tolerated).

## hwut/auxiliary/TEST
documents read: auxiliary/README-directory_mutex.txt, RATIONALE-directory_mutex.txt (D-1..D-4); engine/orchestrator/exploration/RATIONALE.txt R-85 (no_entry)
features: 11  (proven-by-link 8, unproven 3)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- ground-race-retried: a contender meeting the parent just removed tries again — RATIONALE D-4
- no-liveness-no-lock: no start times, no lock, '.taken' says so — README section 1 (every choice bails out on such a platform instead of proving it)
- release-idempotent — README section 2
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- none
### Proven elsewhere
- `no_entry.no_entry_f`: no walk enters a marked directory, nor TMP/OUT of a test directory — exploration RATIONALE R-85 — services/TEST/test-cov_run.py, test-book-defects.sh
- `DirectoryLock` / `Store.lock()` as the face of the mutex — README section 3, D-1 — engine/test_run TEST (not checked)
### Contradictions and stale statements
- README says nothing of D-4 (the lock's parent removed at release); the claim stands in the RATIONALE only.
- README section 3 and D-1 name the user as `hwut/engine/test_run/store.py`; that file does not stand in the tree (stale path).
### Doubtful
- async_helper.py, binary_codec.py, clock.py, parent_child_list.py have neither a document nor a test here: no feature stated.

---

# Findings: compare

# FINDINGS compare  (hwut/engine/compare and below)

Documents read for all directories: `MANUAL.txt`, `README.txt`, `ARCHITECTURE.txt`,
`DOC/SEMANTICS.txt` (sections 1-10 in full, decision log D-1..D-27 by index, D-27 read),
`RATIONALE.txt` (C-1..C-21 by index; C-4, C-5, C-9..C-21 DECISION read),
`engine/README-constraint_namespace.txt`, `region/potpourri/solver/README.txt`,
`FEATURE-happy-constraints.md` (head only: a proposal, superseded by SEMANTICS 10),
`adm/WORK/intend/19-matching-separated.txt`, top `README.md` (tolerance / region / potpourri sections).
`S/DOCS.txt` does not list `ARCHITECTURE.txt`, `DOC/SEMANTICS.txt`, `IMPLEMENTATION-happy-constraints.txt`
-- the first two carry most claims (MANUAL calls SEMANTICS "the authoritative specification").

One deviation from the brief: `TEST/test-equivalence-vs-association.py` was turned from the root
form (`features` + `choices = [...]`) into `choices { }` with per-choice lists -- the five choices
prove five different claims (analogy, region privacy, numeric band, potpourri) and the root form
cannot say so. Choice set unchanged (checked with hwut.config.show).

## hwut/engine/compare/TEST
documents read: MANUAL, DOC/SEMANTICS, RATIONALE, README, ARCHITECTURE, engine/README-constraint_namespace, intend 19, top README.md
features: 55  (proven-by-link 50, unproven 5)   NONSENSE? runs: 2
### UNPROVEN -- claimed, no test here
- cross-check-mode: VUT_COMPARE_CROSS_CHECK=1 derives every verdict through the Lawyer and raises CrossCheckError -- SEMANTICS 1, D-4. No test sets the flag or shows the error (test-configuration only skips the field).
- whitespace-runs-equal: one space equals a run; leading/trailing whitespace stripped -- MANUAL 4, SEMANTICS 3. Only the negative inside 'verbatim' is shown ("whitespace width: False"); no outer-text positive.
- potpourri-counts-visible-nothing: VN-only lines are counted inside a potpourri -- MANUAL 6, SEMANTICS 4.
- old-delimiter-ordinary-content: '||||' is ordinary content -- MANUAL 15, SEMANTICS 7.6, D-19.
- anchored-alignment: equivalent-and-unique lines are paired first (patience/Heckel) -- RATIONALE C-15, intend 19. C-15 has no PINNED line; its COST cites the fixture pair of test-association-cost, which prints node counts, not anchors.
### NONSENSE? -- test runs proving nothing claimed
- regression-2.py [csp]: a mutable AnalogyDb handed to the solver does not crash (frozen conversion). Internal; no document claims it.
- regression-2.py [edit-merge]: separator-vs-content mismatches merge into SUBSTITUTE in the separator adaptor. Internal; ARCHITECTURE names 'separator_adaptor.py' in one line only.
### Documents silent -- behaviour tested, stated nowhere
- chunk-pair-description: test-pretty.py -- a ChunkPair renders itself as text ('__pretty__'); ARCHITECTURE 'DATA TYPES: ChunkPair' should say so.
- number-always-number: test-main [numbers] -- C-11/C-12 stand only in RATIONALE; MANUAL 4 still says numbers matter "when numeric tolerance is configured" and says nothing of sign, '1.0' = '1' at ratio 0, or 'x86'.
- unaccepted-region / constraint-violation-region / unaccepted-zip: only RATIONALE C-9, C-10, C-21. MANUAL (sections 7-12, 16) and SEMANTICS 7.5 list five handlers and do not know these two.
- regions-switchable, comment switch: only RATIONALE C-4.
- constraint-glob, constraint-reserved-names: only engine/README-constraint_namespace; MANUAL 13 does not mention 'glob'.
### Proven elsewhere
- pattern before numbers and blanks -- RATIONALE C-14 -- PINNED services/TEST/test-header-words.sh pattern_first; registration order also printed in reading/TEST test-pattern_finder [setup] (stated there as 'pattern-order').
- phase two after a spent budget -- RATIONALE C-16 -- PINNED services/TEST/test-header-words.sh budget_spent (here only the counted budget is linked).
- broken framing caught on the VERDICT, DISPLAY and STORE roads; 'output-region-syntax-error', the error carries its side -- RATIONALE C-5 with AMENDED 2026-10-10 -- consume/ and services/ (not my directories). Only the READING road is tested here (test-regions [caught]).
- 'tolerance.regions' as hwut word, "a run fails a GOOD carrying a bad region by its name" (services E-123) -- services/TEST.
- equivalence words -- MANUAL 6 -- reading/TEST (element level only; see Doubtful).
- no transposition inside a line -- C-13 -- core/edit_operations/TEST test-line-2 [transpose].
### Contradictions and stale statements
- MANUAL 4 SLASHES "when slash tolerance is on" -- RATIONALE C-18 (later): the switch is gone, '/' and '\' are an equivalence pattern. Feature stated as C-18 says (reading/TEST 'slash-is-pattern').
- MANUAL 2 "REGION features need no configuration ... they always work" and MANUAL 14 "a line that begins like a shebang is always treated as one" -- RATIONALE C-4 (later): 'regions_f' / 'tolerance.regions' switches framing off.
- MANUAL 13 "Constraints may refer to other variables; those must have entered on EARLIER lines" -- same section further down and C-19/SEMANTICS 10.1: fires when the last one enters, whichever. test-constraints [deps] 'reverse order' shows C-19.
- MANUAL 13 / SEMANTICS 10: constraints are a dictionary 'constraint_db = { variable: expression }' -- engine/README-constraint_namespace 5: a list 'constraints = ["x < y + 2", ...]', the relation derived by compare. test-configuration [constraint_db] derives it from the list form.
- MANUAL 14: a SPECIFICATION ERROR "stops with a message" -- C-20 (later) for constraints: a GOOD breaking its own rule is a finding and a mismatch, never raised (MANUAL 13 itself already says so; section 14 does not except it).
- MANUAL 14 example "known handlers: ignore, point-cloud, potpourri, table, verbatim" -- GOOD test-region-handlers [errors] prints also 'constraint-violation' and 'unaccepted'.
- MANUAL 4 "When numeric tolerance is configured ..." -- C-11: numbers are always lexed and compared by value.
- README 'Line Sequences vs. Potpourri': regions "framed by '||||' markers" -- MANUAL 15 / D-19: retired. README does not know regions other than potpourri.
- README 'Visible Nothing': "presence or absence does not affect equivalence", examples "SUCCESS", "IGNORE" -- SEMANTICS 4 IN-LINE LIMIT: 'alpha nothing beta' is NOT equivalent to 'alpha beta'.
- MANUAL and ARCHITECTURE refer to 'DOC/SEMANTICS.txt'; SEMANTICS and ARCHITECTURE name 'engine/input/line_scanner.py', 'engine/input/pattern_finder.py', 'engine/line.py', 'engine/semantics.py' -- the tree has 'reading/' and 'contract/'. ARCHITECTURE 'TESTING CONVENTIONS' names 'engine/input/TEST' and "HWUT (the older generation)", 'hwut-info.dat'.
- ARCHITECTURE 'KEY ALGORITHMS' lists TRANSPOSE among the line-level edits -- C-13 removed it. regression-1.py's three scenario texts (and its choice names 'amnesia', 'pruning_trans') still argue with a Transpose path; the GOODs show none.
- SEMANTICS 10.7 says verified by "TEST/test-constraints.py" -- true; but SEMANTICS 7.6 still presents 'tool/migrate_region_syntax.py' as existing; MANUAL 15 / C-7 say it is gone.
- test-main.py doc names "CHOICES: compare, line_associations, numbers" and functions 'compare()' / 'edit_operations()' -- the choices are compare(-2,-3), associate(-2,-3), numbers; the API is 'is_equivalent' / 'associate'.
### Doubtful
- visible-nothing: the whole-line rule is proven only inside the fuzz net (metamorphic 'vn_line'); regression-2 [visible-nothing] shows the in-line token skip (GOOD_DELETE), which SEMANTICS 6 covers but MANUAL 6 does not promise.
- comments-and-blanks-insignificant is linked to test-main [compare]: one case there has blank lines on both sides at different places; thin.
- region-parameters-nominal: linked from the lines "Nominal is authoritative" in point-cloud [dist] and table [columns]; also shown in potpourri-variants [subset] (not linked: root form).
- cheapest-line-alignment (regression-1) is behaviour of core/edit_operations, tested here through the pattern finder; it could move there.
- search-budget-counted: only [unrelated] prints a budget; the other five choices print node counts (the "counted, same on every machine" half of C-16).
- FEATURE-happy-constraints.md describes '(<name>: <value>)' single-paren, self-contained constraints -- a proposal overtaken by '((name: value))' and cross-variable constraints. Not used as a source; it should say it is superseded.

## hwut/engine/compare/core/edit_operations/TEST
documents read: ARCHITECTURE (KEY ALGORITHMS, DATA TYPES), DOC/SEMANTICS 3-6, RATIONALE C-13, C-15, C-16, intend 19, README
features: 9  (proven-by-link 7, unproven 2)   NONSENSE? runs: 0
### UNPROVEN -- claimed, no test here
- anchored-first: unique equivalent lines anchor; lines with analogy, tolerated number, pattern, or no content never anchor -- RATIONALE C-15. 'benchmark-anchoring.py' measures it but is no test.
- missing-lines-linear-cost: k missing lines cost k x 0.5 -- intend 19 o-2 (stated as the present state; the fork affine/concave is OPEN).
### NONSENSE? -- test runs proving nothing claimed
- none
### Documents silent -- behaviour tested, stated nowhere
- none outright; 'edit-classes' (test-line-permutation, all 5 choices) leans on SEMANTICS 6, which lists the classes but not that every class pair is meaningful.
### Proven elsewhere
- search budget and phase two -- C-16 -- services/TEST test-header-words.sh budget_spent; compare/TEST test-association-cost.
- numeric substitution price bounded to [0,1] -- D-27 -- reading/TEST test-line_element [NumberBand].
### Contradictions and stale statements
- test-line-2.py title "Lines: Transposition and Visible Nothing", PURPOSE "Verify Transposition distance scaling", choice 'transpose' -- C-13: no transposition; the GOOD shows DELETE/INSERT and SUBSTITUTE_TYPE only. Linked to 'no-transposition-in-line'. The first pass's feature "transposition cost grows with distance" was not-X.
- ARCHITECTURE: "'string.py' Levenshtein" -- test-string.py doc: operations include 'transpose' (that is Damerau-Levenshtein). Feature worded neutrally.
- ARCHITECTURE lists TRANSPOSE as a line-level edit; "do() is wrapped in lru_cache" unverified.
- intend 19 names 'line_sequence.py (_step_cost)' and says "every line-level step priced flat"; no test prints that price as a claim.
### Doubtful
- line-sequence-alignment cites C-15's aside "it reorders nothing" and README; no document states the three operations outright.

## hwut/engine/compare/engine/TEST
documents read: ARCHITECTURE, DOC/SEMANTICS 5, 6, 8, README, engine/README-constraint_namespace
features: 12  (proven-by-link 11, unproven 1)   NONSENSE? runs: 0
### UNPROVEN -- claimed, no test here
- line-pair-verdict: a pair of insignificant lines is equivalent, a one-sided content pair is not ('LinePair.is_equivalent()') -- SEMANTICS 2, 6, 8. test-line-pair-report tests only the element lists.
### NONSENSE? -- test runs proving nothing claimed
- none
### Documents silent -- behaviour tested, stated nowhere
- line-pair-element-lists: test-line-pair-report (4 choices) -- 'subject_and_nominal_line_element_lists()' with placeholders; ARCHITECTURE 'LinePair' says only "cell-level edit results".
- analogy-db-consistency [member_functions]: items/merge of FrozenAnalogyDb are described in ARCHITECTURE only as mechanism.
### Proven elsewhere
- the whole of engine/README-constraint_namespace.txt (the only document that stands in this directory) -- proven in compare/TEST (test-configuration [namespace, edges, constraint_db], test-constraints). This TEST directory has no constraint test.
- least-committal tie rule ('semantics.analogy_commitment') -- SEMANTICS 5.3 -- nowhere found; stated UNPROVEN in region/potpourri/TEST.
### Contradictions and stale statements
- ARCHITECTURE puts line.py, analogy_db.py, frozen_analogy_db.py, semantics.py, enums.py, input/ under 'engine/'; it later says 'contract/analogy_db.py'. The directory holds neither a README for what it is now.
- test-compare_line_sequence.py PURPOSE says "Comparison of two potpourris"; both potpourri tests point to 'friends_pairing/TEST', which does not exist (now region/potpourri/TEST).
### Doubtful
- the six verdict/association features are the first pass's, kept: the documents claim them only at whole-engine level (README MODALITIES); here they are shown per line / sequence / potpourri.

## hwut/engine/compare/feeder/TEST
documents read: ARCHITECTURE (feeder, EXTENSION POINTS), DOC/SEMANTICS 6, D-20, RATIONALE C-5, C-10, README NOTES
features: 6  (proven-by-link 4, unproven 2)   NONSENSE? runs: 0
### UNPROVEN -- claimed, no test here
- closing-token-section: the display names the '<hwut-end>' section 'CLOSING-TOKEN', set apart at the foot -- RATIONALE C-10. No GOOD here holds the word.
- protocol-signature: the feeder's protocol signature declares compatibility with a consumer -- ARCHITECTURE 'New output feeder'. 'verify_signature.sh' checks it but carries no '@hwut' block and is not in the relation.
### NONSENSE? -- test runs proving nothing claimed
- none
### Documents silent -- behaviour tested, stated nowhere
- test-ui.py states five things it verifies; no document says what the UI protocol (DisplayInst) carries. "Analogy provenance tracking" (item 5) appears in no document and no GOOD line I could tie to a choice -- not stated as a feature.
- the feeder has no README; README NOTES only points at 'feeder/ui.py'.
### Proven elsewhere
- 'region-syntax-error' report on the DISPLAY road -- C-5 -- consume/ (services side).
- subset surplus lines and collapsed duplicates "shown neutrally" -- SEMANTICS 7.5 -- compare/TEST test-potpourri-variants.
### Contradictions and stale statements
- SEMANTICS D-20 "ConfigInst lost potpourri_begin_end_marker" and C-18 "ConfigInst -- the DOWN protocol's signature moves": the signature changed twice; only verify_signature.sh would notice.
### Doubtful
- html-report: one run, no choices; proves a page is written, not that it is "side by side".

## hwut/engine/compare/reading/TEST
documents read: DOC/SEMANTICS 2, 3, 7.1, 10.7, D-27, RATIONALE C-4, C-10, C-11, C-12, C-14, C-17, C-18, MANUAL 3, 4, 6, ARCHITECTURE
features: 13  (proven-by-link 12, unproven 1)   NONSENSE? runs: 0
### UNPROVEN -- claimed, no test here
- visible-nothing-line-element: an insignificant line lexes into ONE visible-nothing element covering the line -- SEMANTICS 3, last paragraph.
### NONSENSE? -- test runs proving nothing claimed
- none
### Documents silent -- behaviour tested, stated nowhere
- overlapping-patterns: test-pattern_finder [aggressive] -- SEMANTICS 3 says "same pattern set" but not that one lexeme may carry several pattern indices.
- element-comparison: the relative edit distance per element class is stated nowhere but in D-27 (numbers only).
### Proven elsewhere
- closing token is a chunk of its own, for every stream -- C-10 -- compare/TEST test-unaccepted-zip [token].
- regions switch judged in 'line_scanner.classify()' -- C-4 -- compare/TEST test-regions [off].
- a number is always a number; the sign is the number's -- C-11, C-12 -- compare/TEST test-main [numbers] (the lexed-number table stands there).
- classification precedence, '#####' is a comment -- SEMANTICS 2 -- compare/TEST test-region-handlers [errors].
### Contradictions and stale statements
- MANUAL 4 SLASHES vs C-18 (see compare/TEST). GOOD test-pattern_finder [setup] registers '[\\/]+' as EQUIVALENCE_PATTERN -- as C-18 rules.
- GOODs and enum spell 'SEPERATOR'; all documents say SEPARATOR.
- test-chunk_pipe.py PURPOSE "LineSequence and Potpourri" only; five more region kinds exist. C-4 COST says this test states 'regions = false' for one choice -- not visible in its block today (not checked further).
- SEMANTICS 2/3 name 'engine/input/...'; the component is 'reading/'.
### Doubtful
- pattern-order and slash-is-pattern are read off the registration table printed by [setup]; the table shows the order, not a comparison that depends on it (that is the services PINNED test).
- equivalence-words is linked to [LineElementEquivalencePattern] only; no whole-text test of MANUAL 6 "either word matches either word" was found in my directories (the fuzz net configures 'happy'/'glad' but proves agreement, not the rule).

## hwut/engine/compare/region/potpourri/TEST
documents read: DOC/SEMANTICS 5.3, 7.5, MANUAL 8, ARCHITECTURE (MODULE MAP, KEY ALGORITHMS), README
features: 8  (proven-by-link 7, unproven 1)   NONSENSE? runs: 0
### UNPROVEN -- claimed, no test here
- least-committal-tie: among equal matchings a symbol stands for itself where it can, then lowest nominal line -- SEMANTICS 5.3 TIE RULE, D-6. The code is there ('contract/semantics.py', 'potential_pair_db.py'); no test names it.
### NONSENSE? -- test runs proving nothing claimed
- none
### Documents silent -- behaviour tested, stated nowhere
- match-db-pairing, forced-matches, analogy-interference: test-match_db (3 choices) -- ARCHITECTURE gives 'matching.py' and 'potential_pair_db.py' one line each ("ultimates, feasibility"); the tests call the class 'MatchDb', a name no document has.
### Proven elsewhere
- subset / duplicates -- SEMANTICS 7.5, D-25 -- compare/TEST test-potpourri-variants.
- 'max_comparisons' by shebang > section > default -- SEMANTICS 7.3 -- compare/TEST test-region-handlers [params].
- crossed frames found where forced; pigeonhole fails -- SEMANTICS 5.3 -- compare/TEST test-equivalence-vs-association [sudoku, potpourri].
### Contradictions and stale statements
- test docs speak of 'friends-pairing', 'FriendsPairing', 'FriendsPairingMax', 'friends_pairing/similar'; the modules are pairing.py, matching.py, best_match.py.
- test-similar [restricted_cmp] GOOD prints "cost: -1.00000" for a restricted run; SEMANTICS gives the cap (128) but not what the display shows once it is spent.
### Doubtful
- fail-quickly: the documents state the reason (counts must agree; structural upper bound), not "without a similarity analysis".
- potpourri-counts-visible-nothing is stated in compare/TEST (UNPROVEN there); it could as well stand here.

## hwut/engine/compare/region/potpourri/solver/TEST
documents read: region/potpourri/solver/README.txt, ARCHITECTURE (KEY ALGORITHMS, New solver), RATIONALE C-6
features: 5  (proven-by-link 3, unproven 2)   NONSENSE? runs: 0
### UNPROVEN -- claimed, no test here
- thousand-lines-in-fractions-of-a-second: README 'IMPORTANT'. The stress choices run but assert no time; C-6 measured 1069 MB for two of them.
- alternative-solvers: chronological backtracking, arc-consistency/'lilly pad', the adapter -- README files 3-5 and USAGE GUIDE 3-4 describe them as usable. Sources and tests are named 'ON_HOLD-*'; none runs.
### NONSENSE? -- test runs proving nothing claimed
- none
### Documents silent -- behaviour tested, stated nowhere
- long-augmenting-paths: test-maximum_bipartite_matching [chain] -- a path of any length without recursion; README says "Uses Depth-First Search" and nothing of recursion depth.
- C-6 (a stress test states its memory cap) is about the test, not the software: dropped.
### Proven elsewhere
- none
### Contradictions and stale statements
- solver README lists 'csp_chronological_backtracking.py', 'csp_arc_consistency.py', 'lilly_pad_lanes_adapter.py' -- the files are 'ON_HOLD-csp_...py'. ARCHITECTURE: "retained ... but are not active".
- solver README title says "this directory contains a suite of algorithms"; typos 'futuer', 'proof'.
- test choice 'soduko' (sudoku).
### Doubtful
- consistent-pairing is linked from all four choices by the root form; 'massive-pipe' and 'soduko' are the stress runs.

---

# Findings: exploration

## hwut/engine/orchestrator/exploration/TEST

documents read: exploration/README.txt (whole), exploration/RATIONALE.txt (index of R-1..R-92, E-9, X-*; entries R-44, R-69, R-74..R-76, R-80, R-83, R-91, R-92, X-HEAD..X-AMEND read), adm/WORK/intend/00-configuration.txt (head), adm/WORK/intend/23-features.txt, doc/HOWTO-FEATURES.txt (sections 1-4); test headers and GOOD files of the directory. spec/23-features.txt and the hwut_hocon README only cited/grepped, not read through.

features: 56  (proven-by-link 54, unproven 2)   NONSENSE? runs: 0

Verification: `hwut.report.features` prints no OUTSIDE THE RELATION block for the component; `hwut.config.show --no-default` shows no SYNTAX / VOCABULARY / REFUSED line; only `features` values were changed in the test blocks.

### UNPROVEN — claimed, no test here
- climb-ends-at-tmp: the climb for the root conf ends at a 'TMP' beside a 'GOOD/' — README section 6, RATIONALE R-76 (no PINNED line; test-tree.py only USES the boundary in its fixture, `root` shows RootConfMissing but not the TMP stop).
- language-found: language = header word, else 'extensions' of a 'language-setup' entry, else none; an extension claimed twice refused at the root — README section 7, RATIONALE R-73 (no PINNED line; may be shown in services/TEST/test-header-words.sh or test-config-show.py, not checked).

### NONSENSE? — test runs proving nothing claimed
- none. Every run shows behaviour some document states.

### Documents silent — behaviour tested, stated nowhere
- cases-selected: test-task_list.py [all] — "files sorted, choices sorted within a file" and "a [MISDEP] case is SELECTED, not dropped" stand only in the test header; README sections 11/12 say "ordered" without saying how.
- configuration-printed: test-printer.py [directory] — the directory form of the print (directory keys, then applications, then unreachable cases) is not described in README 7.1.
- tree-walked: test-tree.py [walk, root, stream] and marker-name-inherited, configuration-inherited, local-keys-do-not-flow — the tree walk stands in RATIONALE R-69/R-70 only; README has no section on 'explore_tree' (and section 3 still says "Nothing above the TEST directory is consulted").
- execute-stated: test-execute.py — 'execute' is absent from README section 2 (THE TEST PARAMETERS); only R-68/R-82 state it.
- header-amended: test-amend.py — 'amend.py' is absent from the README; only X-AMEND.
- empty-choices-refused, info-dat-not-read: RATIONALE only (X-EMPTY-CHOICES, X-INFO-DAT); README silent on the refusal of 'choices = []' and on the directory 'title' key in section 5.
- key-places-enforced: test-namespace.py — the GOOD is the only complete table; README section 6 lacks 'test_directory', 'app_defaults', 'execute', 'output', 'features', 'diff_display_parameters' and the 'app_defaults'/'apps' places.

### Proven elsewhere
- backup-shaped names are refused as candidates and reported (README 0, 12; E-41, X-SILENT amendment) — services/lib/config/TEST test-ignore.sh refused, refused_too.
- 'TMP/wallflowers.txt' lists, the closing NOTE, 'hwut.config.ignore --wallflowers/--wishlist' (README 0; X-SILENT) — services/lib/config/TEST test-ignore.sh wallflowers, wishlist, reported.
- 'collision'/'dependency' in a run, [CYCLE] under LINKS (R-33 and its 2026-10-09 amendment) — services/TEST test-header-words.sh cycle, directory.
- the tolerance scope and the refusal of the five root spellings (README 12; R-77) — services/TEST test-header-words.sh tolerance.
- the constraint namespace (R-66, R-81) — services/TEST test-header-words.sh constraint, constraint_refused.
- 'execute' EXPANDED at the call (R-82) — services/TEST test-header-words.sh execute.
- '%' as the source file's stem (README 4.1; R-74) — implemented in orchestrator/run (adapter, coverage_dispatcher), not here; tests naming it: services/TEST test-header-words.sh, engine/operations/TEST test-coverage_provision.py.
- an unenforceable cap refuses the test unless 'procsitter { <platform> }' acknowledges it (README 2, 6; R-48, R-80) — engine/orchestrator/plan/TEST test-confinement.py, services/TEST test-gate.py, test-run-uncapped.sh.
- no walk enters a coverage output (R-85) — services/TEST test-book-defects.sh coverage-ground.
- per feature, the code its runs reached (README 13 'feature_code.py'; R-86) — services/TEST test-report-features.py code.
- a conf above the TEST directory named by its path (R-87) — services/TEST test-config-show.py above.
- a tree relating nothing by id is not judged (R-88) — services/TEST test-report-features.py outside.
- string escapes printed as read (R-89) — services/TEST test-config-show.py file (also visible in test-printer.py read_back, linked here to configuration-printed).
- 'doc' and triple quotes (R-90) — test_writing_support/python/TEST test-hwut_hocon.py triple; services/TEST test-report-features.py document.
- 'documents' of a feature (R-92) — services/TEST test-report-features.py tree, document.
- quoted strings, bare tokens, radix numbers (README 1; R-49, R-62) — the parser's own TEST directory, test_writing_support/python/TEST.
- user targets 'target { }', standard name refused (README 5) — presumably services/TEST test-execute.sh (not checked).
- '--language' as selector (README 7; R-75) — a face matter, presumably services/TEST test-face-words.sh (not checked).

### Contradictions and stale statements
- README section 3 is headed "THE THREE CARRIERS", says "Exploration therefore EXECUTES", "ONLY AN EXECUTABLE FILE IS ASKED, and its answer is memoised"; README section 0 and X-SILENT say there is no third carrier and nothing is asked. GOOD test-interview.py--memo: a plain walk asks nobody, an injected runner asks on every walk and no memo file is written. X-INTERVIEW's "'test-interview.py memo' pins the three rules" is therefore stale too (X-SILENT says the memo is dormant). Features stated as X-SILENT says; no memo feature stated. The first pass's "an unchanged file is not asked twice" was false against the GOOD.
- README section 3 "INTERVIEW ... 'HAPPY:' (-> eq-pattern)" and "ONLY AN EXECUTABLE FILE IS ASKED": GOOD memo shows 'notes.log' and 'helper.py' asked by the injected runner.
- README section 10, last paragraph: "--hwut-info ... reported choices are compared against the specification and the difference feeds error message hints" — R-2's idea, in R-44's GRAVEYARD; nothing does this.
- README section 8: "THE DETECTOR finds the first occurrence ... at any position in the file" vs README section 4 / X-HEAD: first eight lines only. test-detector_unwrapper.py header ('detect: found at its first occurrence, anywhere') repeats the stale wording; GOOD [head] shows the head rule.
- README section 3: "Nothing above the TEST directory is consulted" (R-8) vs R-69, the configuration tree, tested in test-tree.py.
- README section 2 lists 'numeric', 'eq-pattern', 'nothing', 'analogy', 'constraints', 'comment' as root keys and 'slash_eqv'/'whitespace_eqv'; README section 12 / R-77 say they live in 'tolerance { }' only ('numeric_ratio', 'whitespace', 'slash', 'eq_pattern') and are refused at the root. Section 2.1 ('analogy = []' at root) and the 7.1 examples ('comment = "//"', 'tolerance { slash = false }') carry the old spellings as well.
- README section 2 (caps): "The runner's '--ignore=<cap>' runs it anyway" — struck by R-80 (GRAVEYARD); README section 6 already describes the 'procsitter' acknowledgement.
- README section 5: a cycle gives '[MISDEP]' to every case; R-33 amendment 2026-10-09 adds '[CYCLE]' for the links a cycle holds. GOOD test-explorer.py--graph shows '[MISDEP]' only (exploration level) — consistent with the amendment being a plan/display matter, but the README does not mention '[CYCLE]'.
- README section 6 table: 'title' not in hwut-root.conf and 'procsitter' a root key; GOOD test-namespace.py: 'title', 'ignore', 'app_defaults', 'test_directory' are read at the root conf, and 'procsitter' is not among "every key the framework knows" in the test. R-69 calls 'test_directory' "root-only" while the GOOD reads it at 'dir' too.
- test-namespace.py GOOD: 'colors' is refused ('-') in every place — a key "the framework knows" that is read nowhere by this reader; either the row or the claim is off.
- README section 6: 'language-setup' in a nearer 'hwut.conf' is refused by name (R-73); test-validator.py [conf] header and GOOD show 'language-setup' read from "a full hwut.conf". (test-namespace.py agrees with the README.) The validator page seems to read a root-shaped text under the name of a directory conf.
- README section 5.1a: 'variant_group' stands in 'hwut-root.conf'; test-variant.py header says "'variant_group { }' in 'hwut.conf'". The README example names no 'gcov' alternative yet selects '--variant=gcov,slow'.
- README section 0 / X-TITLE: a lacking title stands in; test-validator.py header [vocabulary] still says "a missing 'title' -- each refused by name". The GOOD shows the stand-in.
- README section 13 gives the feature entry as 'name title explanation'; 'documents' (R-92, HOWTO-FEATURES) is missing.
- test-interview.py: its 'CHOICES:' line omits 'memo' and 'relic', which the block declares.

### Doubtful
- Tests whose block keeps the root form with a 'choices' list (test-detector_unwrapper.py, test-defaults.py, test-task_list.py, test-output.sh, test-variant.py) could not be linked per choice without changing the block form; each choice is linked to ALL features of its test (e.g. detector [blank] also "proves" decoration-any-language). Precise mapping: detector detect/head -> marker-in-head, decoration -> decoration-any-language, star/hash/dash/single/blank -> region-unwrapped, offsets -> positions-file-relative; defaults table/declared -> defaults-related-to-owner, refused -> unrelated-parameter-refused, instantiate -> complete-configuration, merge -> record-keeps-chosen; task_list all/named -> cases-selected, refused -> selection-refused; output declare/cycle -> output-subjects, forgotten -> output-file-missing, refuse -> stderr-never-subject; variant declared/vocabulary -> variant-groups-declared, selected/refused -> variant-selected.
- test-output.sh drives 'services.run/accept/play': the 'output' laws are run-time behaviour and arguably belong to services/TEST; only the '<stderr>' refusal is exploration's own. Kept here because R-71 and README section 2 claim them here and the test stands here.
- interview-read / interview-only-where-silent: after X-SILENT the interview is "the reader hwut.renovate drives"; test-interview.py [directory] still shows a 1.0 file EXPLORED with origin INTERVIEW when a runner is injected into 'explore'. Whether that door should still exist in 'explore' is not ruled in the documents read.
- candidate-files: test-explorer.py [directory] shows the ignore globs; "the framework's own files, by name" (hwut-traces.csv, hwut-root.labels, feature files) is not visibly exercised there.
- app-defaults-yield is linked to test-printer.py [origins] (the 'hwut.conf:<line>' provenance); no page shows directly that an application's own value stands over 'app_defaults' within ONE directory (test-tree.py [inherit] shows it across levels).

---

# Findings: orchestrator

None of the three RATIONALE files carries a PINNED line; the claim-to-test map was made
from test headers and GOOD files.

## hwut/engine/orchestrator/plan/TEST
documents read: plan/README.txt, plan/RATIONALE.txt, orchestrator/README.txt, orchestrator/RATIONALE.txt (index), exploration/RATIONALE.txt R-48, R-80
features: 23  (proven-by-link 21, unproven 2)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- tree-plan-faults-printed: the printed tree plan states the walk's faults and each directory's faults — README section 8. The `tree` fixture has no fault.
- frame-outside-plan: an entry carries `on_entry`/`on_exit`, the scripts appear in no print — README intro and section 8, RATIONALE P-10. No fixture states a frame.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- required-caps, unenforceable-cap-refused, cap-lack-acknowledged: test-confinement.py (all four choices) — `plan/confinement.py` is described only in exploration/RATIONALE R-48/R-80 (the features point there). plan/README section 9 names the nominal gate alone; the confinement gate, the reason line and the `hwut-root.conf` acknowledgement belong there.
- test-wish.py [base] also shows `--faster-than=1`; `wish.py` further reads `--unaccepted`, `--exclude`, `--exclude-dir`, `--dir`, `--wishlist`, `--label`, `--language`. plan/README section 6 lists five keywords only. Not stated as features (no document here claims them; `--dir` stands in orchestrator/RATIONALE R-74).
### Proven elsewhere
- The nominal gate: a case without a nominal is refused, enters no plan — plan/README section 9 (services E-41) — services/TEST (test-accept.sh shows "not accepted"); not checked further. Here the tree_plan fixture only satisfies the gate.
- `hwut.plan` / `hwut.config.show` as faces — RATIONALE P-16 — services/TEST.
- `--dir <glob>` — orchestrator/RATIONALE R-74 — not tested here.
### Contradictions and stale statements
- plan/RATIONALE P-17 says "directories run SERIALLY"; plan/README section 8 repeats it; run/RATIONALE O-11, O-15, O-29 (later) say the strategy decides, default successor.
- plan/RATIONALE P-11 (special commands) is superseded by its own note (services E-7, `hwut.execute`); dropped.
- plan/README section 7 gives `determine(app_set, task_list, build_interview=None) -> (CTestPlan, list[str])`; section 9 and the tests show a third return value (refused) and `admit=`.
- test-form.py header lists CHOICES "nodes, derived, refused, closure"; the block has a fifth, `stage`.
### Doubtful
- deterministic-plan: the documents say it only as a COST of P-4 ("determination must be deterministic and tested so") and "deterministic" in README section 4.
- "A print is never read back as input" (P-4) is a non-behaviour; not stated as a feature.

## hwut/engine/orchestrator/run/TEST
documents read: run/README.txt, run/RATIONALE.txt (O-1..O-34, DECISION parts), adm/WORK/intend/20-bundled-strategy.txt, orchestrator/README.txt
features: 30  (proven-by-link 24, unproven 6)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- wish-refused-at-call: a refused wish raises at the call, before any event — README intro, O-1.
- launch-failed-lifted: report `test-app-launch-failed` carries verdict `launch-failed` — O-6. The end-to-end `test-dead.sh` ends `test-failed` / `test-app-session-gone`, session node `ok`; no run shows `launch-failed`.
- raising-unit-contained: a raising unit becomes `fault` + `dir-done good=false`, others run on — README section 2, O-13.
- warning-event: a `warning` event before the first run — O-26. No GOOD holds the kind.
- directory-lock: one lock per dispatcher lifetime, DirectoryBusy refused at the door — README section 5, O-7.
- directories-ordered: directories started in selection order, weighed by longest case — O-28, O-33. Only the node/application key is tested (`together`).
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- test-endtoend.py [stream] GOOD carries a kind `silent` (nodes `Makefile`, `strip_noise.py`) and `report` texts "REGISTERED ... accepted outside the book (E-41)"; README section 1 lists neither `silent`, `warning` nor `refused`. Not stated as features (the kinds belong to engine/protocol).
- test-adapter.py [sweep] also shows `output`, `features` (-> feature relation) and `diff_display_parameters` arriving; README section 6's table lacks them. Covered by parameters-reach-owners.
### Proven elsewhere
- `--jobs` as one host-global budget, every dispatch a slot — O-12 — mechanism in scheduler/TEST (test-scheduler.py budget); the option in services/TEST.
- `--deterministic` = linear,name-sorted; homogeneity of the digest across strategies; pype digest of parallel runs — O-14, O-15, O-30 — services/TEST, display/TEST/test-run.sh.
- A kill names its cap and number (`detail`) on both roads — O-19, O-21 — procsitter/TEST/test-reporting.sh.
- A failing canonicaliser ends provision — O-18 — operations.
- Fault in the flow, `--log` — O-24; unaccepted nominal as [FAIL] — O-25 — display/TEST, services/TEST.
### Contradictions and stale statements
- README section 2a: "'DEFAULT_STRATEGY_NAME' is 'linear'", three strategies. RATIONALE O-29/O-31 and code: default SUCCESSOR, a fourth member `bundled`, selection orders and `words_of`. test-strategy.py [contract] GOOD shows 'sf' -> SUCCESSOR. Feature stated as the RATIONALE says.
- README sections 1, 3, 4 describe `vocabulary.py`, `summary.py`, `receiver.py` as this component's; O-17/O-22 moved them to engine/protocol and deleted them here. test-receiver.py still stands in run/TEST and imports engine/protocol; engine/protocol/TEST holds test-line.py only. The four receiver/vocabulary features are kept here because the README claims them here.
- O-27 "unmeasured goes first" is reversed by O-30 (unmeasured last); O-33 still ends "A directory nobody has measured still goes first (O-28)" — after O-30. Unresolved in the text; `directories-ordered` leaves it out.
- O-8 says the store's ground is `.hwut-store/`; its own amendment says `TMP/store/`, "no ruling records the move".
- test-endtoend.py header: "test-m.sh depends on a file that is not there -> misdep". GOOD: `test-m.sh` runs and ends `test-failed` / `not-equivalent-with-nominal`; the stream opens with the fault "hwut.conf:1:1: VOCABULARY: no 'hwut { ... }' block" — the fixture's hwut.conf is not read, so the dependency never applies. No end-to-end run shows `misdep` (test-orchestrator.py [broken] does, over the tick dispatcher).
- test-endtoend.py header says `test-dead.sh` "dies before the protocol"; O-6 would suggest `launch-failed`; GOOD shows the SESSION node `ok` and the choice `test-failed`.
- test-strategy.py header CHOICES lists six, DESCRIPTION describes four (`bundled`, `together` missing).
- orchestrator/README.txt is stale throughout: describes `bookkeeper/`, `explorer/`, `orchestrator.py`, `GOOD/result_db.json`; the tree holds exploration/plan/run/scheduler, the bookkeeper is engine/bookkeeper. orchestrator/RATIONALE D-1..D-8 likewise are the bookkeeper's. Nothing taken from either.
- README closing law (nothing here renders): "'TEST/' does not police this" — stated as untested by the document itself; not a feature.
### Doubtful
- strategy-defaults is proven only through `words_of` in [contract], not through a run.
- empty-wish-run: the claim stands in plan/RATIONALE P-9; run's own documents do not state it.
- summary-fold is linked to the stream runs that print "folded"; `drain(queue)` itself is not shown.
- intend 20 section 4 leaves the default's move to BUNDLED open; not a feature.

## hwut/engine/orchestrator/scheduler/TEST
documents read: scheduler/README.txt, scheduler/RATIONALE.txt, run/RATIONALE.txt (O-12, O-27..O-32), adm/WORK/intend/20-bundled-strategy.txt
features: 13  (proven-by-link 11, unproven 2)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- ready-count: `Scheduler.ready_n()` answers how many nodes could start now — intend 20 section 3 (1), run/RATIONALE O-31. scheduler/README does not mention it.
- node-selection-order: which admissible node starts follows the selection order (`scheduler._selected`) — run/RATIONALE O-27, O-28, O-30. No test here passes a selection order.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- none (test-state.py [admission] also prints `done_f`/`stuck_f`, not in the README).
### Proven elsewhere
- The sort key itself (longest-first, choices together, unmeasured last) — run/RATIONALE O-30, O-32 — run/TEST test-strategy.py [together].
- Bundled's use of `ready_n` — run/TEST test-strategy.py [bundled], over a scripted model unit, not over a real Scheduler.
### Contradictions and stale statements
- scheduler/README section 2 "the first ready name starts" / S-3 "takes the first name" versus run/RATIONALE O-27 (later): the selection order chooses.
- scheduler/README does not know `ready_n` or `selection_order`; the RATIONALE ends at S-4.
### Doubtful
- node-selection-order may be exercised by display/TEST/test-run.sh (`--strategy=`); not checked.
- run-report is linked to [frame] and [misdep] only; every scheduler choice prints a REPORT block.

---

# Findings: operations

# Findings — label `operations`

Features are what the documents claim; links are what the runs of each TEST directory show.
`README` below is `hwut/engine/operations/README.txt` unless said otherwise.

## hwut/engine/operations/TEST
documents read: operations/README.txt (whole), RATIONALE.txt (R-70, O-35), DISCUSSIONS.txt (todo-16, -17, -20, -21, -23), run/README-provider.txt, bookkeeper/RATIONALE.txt (B-6, B-25 headlines), coverage/RATIONALE.txt (D-38, D-39 headlines), orchestrator/run/RATIONALE.txt (O-17..O-24), top README.md (grep)
features: 31  (proven-by-link 29, unproven 2)   NONSENSE? runs: 4
### UNPROVEN — claimed, no test here
- request-stop-event: a caller ends a running test through `Request.stop_event` — README 2.8. `stop_event` is exercised in consume/TEST and run/TEST on the operations and providers, never through `run_test`.
- missing-source-and-display-named: SOURCE_NOT_FOUND and DISPLAY_TARGET_UNREACHABLE are reported by name — README 13. No test in the six directories names either token.
### NONSENSE? — test runs proving nothing claimed
- test-hygiene.py [good_files]: no environment value stands in a GOOD file — a property of the suite, not behaviour.
- test-hygiene.py [no_crash]: no crash hides behind a green verdict — suite property.
- test-hygiene.py [no_orphans]: no public name is declared and unused — source property.
- test-hygiene.py [return_first]: every function comment begins with RETURN — source convention.
  (`token_ranks` of the same test IS linked: README 13, every failure token has a rank.)
### Documents silent — behaviour tested, stated nowhere
- build-report-names-reason: test-build_action.py [reasons, contained] — "tool reasons outrank target reasons" and "a contained build is told from a failed one" stand in no document; README 13 gives only the token families. Belongs in README 13 or a section on `build_action.py` (README has none; `build_action.py` appears only in the NAMES list).
- build-without-tool-refused: test-build_action.py [argv] — README 2.6 states the refusal in one table row; that the argv is built from an enumerated vocabulary (MAKE, ...) is said nowhere.
- coverage-run-harvested / coverage-absence-answered: test-coverage_provision.py — `coverage_action.py` is not mentioned in operations/README at all; the claims stand in coverage/RATIONALE D-38/D-39 only. README PART II should name the coverage road.
- book-entry-holds-no-configuration: test-session.py [setup, book] — see contradictions; stated in bookkeeper/RATIONALE B-6, not in operations.
### Proven elsewhere
- a lock whose holder is gone is removed and retaken (README 6, steal) — auxiliary/TEST/test-directory-mutex.py [dead]
- `hwut.run.play` diagnoses an empty answer (RATIONALE O-35, PINNED) — services/TEST/test-play.sh [silent, why]
- colliding source stems refused where configurations are made (README 3, NOTE) — a requirement on the caller; exploration, not located
- caps reach the choice that asks (orchestrator/run O-20, `configuration.caps_of`) — orchestrator test-adapter.py [caps_inherit]
### Contradictions and stale statements
- README 6 "BOTH HALVES OF FREEING ARE RECORDED with it" (canonicaliser and compare setup in the book entry) — test-session.py [book] GOOD: "the canonicaliser is NOT recorded (B-6)"; [setup] GOOD: "NO SETUP REACHES THE ENTRY (B-6)". The feature is stated as B-6 says. Yet [setup] still closes with "SUCCESS: what the verdict meant is recorded beside the verdict" — the closing line contradicts its own OK lines.
- README 6 names the book `GOOD/result_db.json`; the book is `GOOD/book.csv`.
- README 2.8 ceremony "a Run's subjects -> candidates" / README 4 — test-session.py [recording] GOOD: stderr is excepted (E-5), never a record. README STDERR says so too; section 4 does not.
- README 4 "Raw deltas and a host tag are kept" — test-session.py [book]: the host is not in the book (E-20, E-22); no run here shows a host tag in the cadence sidecar.
- README PART II still describes `StageBuild`/`StageAcquire` memoising and "ACQUISITION IS A SUPERVISED CALL" at length, right after saying both left with the surgery. No `stage_acquire.py` exists. README 14 NAMES lists `provision/`, `store.py`, `operations/`, `services/` — the directories are `run/`, `consume/`, bookkeeper's `stream_store.py`. DISCUSSIONS todo-23 admits the deep sections are owed a pass.
- README 2.8 `Request` lists `replay: bool`; the channel (PART II) speaks of `production=`/`force_run=` — not checked against the code, flagged.
- RATIONALE.txt holds two entries only (R-70, O-35); the rulings of todo-23 "stand in NO RATIONALE entry" (DISCUSSIONS says so itself).
### Doubtful
- test-hygiene.py: four NONSENSE? runs are deliberate house-keeping. If hygiene is to count, a feature needs a document that claims it (DEVELOPMENT.txt?).
- display-target-selects-driver is stated here and as target-builds-driver in interaction/TEST: test-session.py [target] and test-tui.py [target_wiring] prove the same `driver_for`. The [target] GOOD lists a `keys` target (KeyedDisplay) the README does not know.
- products-kept-apart is close to internal structure; kept because callers read `comparison is None`.

## hwut/engine/operations/consume/TEST
documents read: as above (README 2.4-2.6, 6-10, 11.2, 11.4, 12, 13, THE TERMINAL TOKEN, STDERR; RATIONALE R-70)
features: 24  (proven-by-link 23, unproven 1)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- file-subjects-exempt-from-token: a file subject needs no `<hwut-end>` — README THE TERMINAL TOKEN, RATIONALE R-70. test-equivalence-check.py [terminated] covers stdout only.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- every-named-subject-shown: test-difference-display.py [every_subject] — README 9 should say that the display, unlike the check, does not stop at the first differing subject.
- accept-all-or-nothing: test-accept.py [all_or_nothing] — README 10 says "replaced WHOLESALE, per subject" and nothing of a half-readable set of dumps; only the STDERR section says "writes nothing at all". Belongs in README 10.
- accept-pulls-provision: [pulls_run] — "ONCE however many subjects need it" is in the test header only.
- initiate-stores-session-stream: [initiate] — "does NOT fall back to the current output" is not in README 10.
- cut-short-subject-named: [terminated] — "trailing blank lines after the token are forgiven" is implied by "last non-empty line", not said.
### Proven elsewhere
- a run that fails `unexpected-stderr` sets the `stderr-untolerated` stain (README STDERR, THE STAIN) — services/TEST/test-diff.sh [stderr]; here only the accept side (test-accept.py [stderr])
- acceptance refuses a candidate whose last line is not the token, and evidence older than its test (R-70 CITED BY, services E-6, E-39) — services/TEST
- `hwut.accept.interactive`, `hwut.compare` faces (README 11.5) — services/TEST
### Contradictions and stale statements
- README 11.5 says a COMMIT writes "the nominal, the register, the book"; test-accept.py is titled around a "ledger" and its [ledger] GOOD shows the book only (B-25: no acceptance instant). "Register" and "ledger" are not explained in the README.
- README 9: "a recorded timing channel MAY annotate each line with its delta" — no run shows it; too weak to state as a feature.
### Doubtful
- test-accept.py [the_loop] is linked to dump-replaces-nominal and verdict-from-comparison; it proves the run -> differ -> accept -> pass arc of README 6's last paragraph, which is a narrative rather than a claim.
- stderr-stain-cleared: the [stderr] table shows the stain staying where the acceptance was refused and clean after every acceptance that stands — matches README; the setting of the stain is not shown here.

## hwut/engine/operations/interaction/TEST
documents read: README 2.6, 11 (all), DISCUSSIONS todo-2, -16, -17, -20
features: 18  (proven-by-link 18, unproven 0)   NONSENSE? runs: 1
### UNPROVEN — claimed, no test here
- none stated (see contradictions: block-scoped realignment)
### NONSENSE? — test runs proving nothing claimed
- test-tui.py [elements]: its GOOD file records `FAILURE: every element kind renders, with the meta DOWN carries.` with five FAIL lines (numeric measurement, the deciding number, analogy conflict, the conflicting binding's site, the named pattern). The book says `ok` because OUT equals that GOOD. A passing run of a recorded FAILURE proves no feature; left unlinked on purpose.
### Documents silent — behaviour tested, stated nowhere
- unknown-intent-refused: test-merge.py [unknown] — README 2.6 has the row "an UP intent nobody defined"; 11.3 should say it.
- down-carried-uninterpreted: [widened_down] — "an item whose fields cannot be read at all is refused" and "a kind with no fields is readable and empty" are in the GOOD only.
- display-only-driver in the TUI: test-tui.py [display_only] — README 11.3 speaks of a driver without `resolve`; that the TUI has such a mode is not said.
### Proven elsewhere
- the keyed session (`KeyedDisplay`, services E-61) realigns on 'r' — services/lib/viewers/keyed/TEST
- `hwut.accept.interactive`, `hwut.compare` (README 11.5 TWO SERVICE FACES) — services/TEST
### Contradictions and stale statements
- README 11.7 states block-scoped re-association, per-generation ids and framing voids as design in force, and README 11.3 shows `Resolution.block_id`; DISCUSSIONS todo-16 (later, audit r10): "'block_id' on SectionBeginInst and on Resolution ... STILL OWED", "the hub ... still re-feeds in full". No test names `block_id`. No feature stated; README 11.7 needs "not built" or a pointer.
- README 11.5 "verdict-marked spans, analogy provenance" and DISCUSSIONS todo-20 "CARRIED TODAY, and rendered: ... analogy provenance (... the conflicting binding's site after the feeder's bake fix)" — test-tui.py [elements] GOOD: "FAIL: the conflicting analogy is told as a CONFLICT", "FAIL: ... naming the site of the binding it conflicts with". todo-20 itself says NumericMeta/PatternMeta are not in the tree (B-32) — consistent with three of the five FAIL lines, not with the two analogy ones.
- README 11.5/14 place the TUI at `interaction/tui.py` and the hub at `interaction/feed.py`; the directory holds `port.py` only, the TUI is `services/lib/viewers/tui.py`. orchestrator/run O-22 calls `interaction/feed.py` and `tui.py` dead islands. test-tui.py therefore tests a module of another component from this TEST directory.
- README 11.6a default `MERGE_ROUND_MAX = 1000`; test-merge.py does not name the constant (it passes `max_round_n`), so the default is unproven.
- DISCUSSIONS todo-16 "20/20 green" counts test-merge + test-tui runs; one of the twenty is the recorded FAILURE above.
### Doubtful
- basic-mergetool-tier is linked to test-merge.py [commit, cancel] because both drive `MergeToolDisplay`; the BASE/LOCAL/REMOTE/MERGED file convention of README 11.5 is not what the test shows (it passes `{subject}` `{nominal}` to a tool).
- tui-renders-down is proven by [rendering, regions] only; with [elements] recorded as a failure the "every element kind" half of the claim is open.

## hwut/engine/operations/run/TEST
documents read: run/README-provider.txt (whole), README PART II, 3, 4, 5, 13, THE TERMINAL TOKEN; DISCUSSIONS todo-23; orchestrator/run/RATIONALE O-18..O-21
features: 22  (proven-by-link 19, unproven 3)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- no-terminal-word-set: `HWUT_NO_TERMINAL` is set at launch where a stdout canonicaliser stands — README THE TERMINAL TOKEN, RATIONALE R-70, procsitter MANUAL (ENVIRONMENT OVERLAY). No test file of the whole tree names the word.
- negative-status-contained: a negative session status delivers with `test-app-contained` — README-provider 3. test-multi-execute.py [status] shows zero and positive only.
- wave-build: `MultiBuild` / `TargetBuild`, one invocation per wave — README-provider 2 and 4. No `multi_build.py` exists in the tree; README PART II says building went to the plan's BUILD nodes. Either stale or proven under another name in orchestrator/plan.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- raw-stream-live: test-provider.py [live] — README PART II says "raw streams, fanned out"; that a listener receives them while the application runs is nowhere.
- session-needs-registered-capability: test-multi-execute.py [refused] — the refusal of a choice name with a blank ("the wire is blank-separated") is in no document; README-provider 3 should state it beside the wire.
- absent-application-is-launch-failure: test-provision.py [absent_application] — README has no sentence for the plain road; README-provider 3 has it for sessions ('fail' -> test-app-launch-failed).
- channels-and-declared-files-are-subjects: [subjects] — "read AND REMOVED" (R-71) is cited by the tests; R-71 stands in exploration's RATIONALE, not in operations' documents.
### Proven elsewhere
- the orchestrator's decision plain vs multi (README-provider 5) — engine/orchestrator/run/TEST
- a session that died names the choice in flight and tells the others "not run: the process had already died" (orchestrator/run O-21, `run/containment.py`) — engine/procsitter/TEST/test-reporting.sh [multi]; here only the plain road (test-provision.py [containment])
- caps of the choice vs of the application per stage (O-20) — orchestrator test-adapter.py [caps_inherit]
### Contradictions and stale statements
- README-provider 3 "A session serves CHANNEL subjects only ('OUT/' is shared across its choices)" and 5 "channel subjects only" — DISCUSSIONS todo-23 (audit r10, 2026-10-04): "BUILT: FILE SUBJECTS in a session ... the old law is dead"; test-multi-execute.py [files] shows it. Feature stated as built. (DISCUSSIONS also names a stale docstring at multi_execute.py:88-92.)
- README-provider 3: sinks under `TMP/session/`; DISCUSSIONS todo-23: `.hwut-session/`.
- README-provider 3 "a session ending first answers 'test-app-contained'" — superseded by orchestrator/run O-21 (cap token for the choice in flight, TEST_APP_SESSION_GONE for the rest).
- README-provider head: "Companion of provision/core.py and provision/provider.py" — the directory is `run/`; its section 1 still walks acquire and build stages that README PART II says left.
- README 5 shows `loaded(store, test, choice, subjects)` with fields `record_directory`, `test_directory` — two shapes in one block.
### Doubtful
- cadence-in-delivery [plugged]: "a sink has no arrival: the cadence is absent" — the session road never measures cadence; README 4 promises timing "even when raw content is too big" without excepting interactive tests.
- partial-streams-delivered is proven for the wall clock/stall only.

## hwut/engine/procsitter/TEST
documents read: procsitter/MANUAL.txt (whole; there is no README or RATIONALE in the directory), orchestrator/run/RATIONALE O-19..O-21, adm/WORK/gathered/10-todo-4-caps-vocabulary.txt, top README.md (grep: procsitter named once)
features: 21  (proven-by-link 16, unproven 5)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- stop-event-stops-call: a set `stop_event` ends the call as FAIL_STOPPED — MANUAL 5, 6. Only seen indirectly, through the chain's shared event ([chain_stop_early]).
- handler-fault-surfaces: an exception in a caller's handler kills the process and then surfaces — MANUAL 5.
- environment-overlay: `env` merged over the parent's environment — MANUAL, ENVIRONMENT OVERLAY.
- chain-listener: a stage's `stdout_handler` is tee'd with the chain edge, edge first — MANUAL 7.4.
- chain-owned-key-refused: an owned key in a stage's extra arguments asserts at construction — MANUAL 7.5.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- missing-program-is-a-result: test-procsitter_limits.py [command_guard] — "a bare string command is rejected loudly (AssertionError)" is not in MANUAL 5, which only says the command is an argv sequence.
- stderr-tail-kept: [stderr_tail_cap] — the 4096-byte bound on one line is not in MANUAL 6.
- clean-under-caps: [clean_under_caps] — no sentence says a workload under every cap is left alone.
- tee-fans-out: test-procsitter_interact.py [tee_degenerate] — one consumer is the consumer itself, none discards: not in MANUAL 7.2.
- unenforced-caps-reported: test-capability.py [unenforced] — that the call's `.unenforced` agrees with the board is tested, not stated.
- cap-hit-ends-call-and-is-named: [output_gap] "exit_code is None when the procsitter ended it" — MANUAL 6 says only `int | None`.
### Proven elsewhere
- a cap stated per choice governs that choice (O-20) — orchestrator test-adapter.py [caps_inherit]
- FAIL_STALLED rendered as TEST_APP_STALLED (operations README 4) — operations/run/TEST/test-provision.py [containment]
### Contradictions and stale statements
- adm/WORK/gathered/10-todo-4-caps-vocabulary.txt, R-48: "a cap procsitter cannot enforce refuses the test"; MANUAL 10: "a pass without memory enforcement is a pass -- but say so", and the result merely reports `.unenforced`. Different layers (exploration vs procsitter), but nothing in MANUAL points to the refusal.
- MANUAL 8 table: the pid and RSS watchdog needs psutil on every platform; MANUAL 4 `UTILITY_DB` and test-capability.py [board] show `max_disk_mb`, `min_free_disk_mb`, `max_output_gap_sec` watched without any utility — the table of section 8 does not list those three caps.
- MANUAL 6: "Fork bomb death by the NPROC rlimit ... race" — MANUAL 8 says RLIMIT_NPROC is NOT used. The race cannot exist as described.
- test-reporting.sh lives in procsitter/TEST but proves orchestrator/run O-21 (`operations/run/containment.py`, hints of `hwut.run`); MANUAL does not mention hints. Its feature points at orchestrator/run/RATIONALE.
- orchestrator/run O-21 FOUND: a fractional `cpu_sec` is rounded up, TypeError suppressed — not in MANUAL 4, no test here.
- The task named "MANUAL.txt and its README/RATIONALE": procsitter has neither.
### Doubtful
- cap-hit-ends-call-and-is-named is one feature over seven runs; [file_size] accepts "SIGXFSZ death or EFBIG self-abort", so the result does NOT always name the cap there (MANUAL 6 says so as a subtlety). Seven features would show that one as weaker.
- man-in-the-middle [control_signals, pype_interactor]: the consumer B "keeps listening undisturbed" is part of the claim; not verified that both runs have a third listener.

## hwut/engine/protocol/TEST
documents read: none exists in the component; orchestrator/run/RATIONALE O-17, O-22, O-24; adm/LAYERING.txt; services/RATIONALE (grep); the head of `line.py`
features: 3  (proven-by-link 3, unproven 0)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- none
### NONSENSE? — test runs proving nothing claimed
- none (see below: all three runs are linked under "documents silent")
### Documents silent — behaviour tested, stated nowhere
- line-round-trip, content-forms, malformed-line-refused: test-line.py [roundtrip, quoting, refused] — the grammar '<t>:<kind>:<content>' and its three content forms are documented in the module head of `line.py` only. The one document sentence is orchestrator/run O-24 COST: the line language "stays in 'engine/protocol/line.py' with its suite: it costs nothing standing". By that sentence no face writes this line any more ('--log' writes the flow, not the line). The component needs a README, or the module and its test are a candidate for removal.
### Proven elsewhere
- the fold over the report stream and the receiver class (O-17; `summary.py`, `receiver.py`, `vocabulary.py`) — engine/orchestrator/run/TEST (test-receiver.py, test-endtoend.py, test-orchestrator.py)
- the seal: protocol imports nothing of the tree (O-17, adm/LAYERING.txt) — the layering check (C-2), not located
### Contradictions and stale statements
- `line.py` and test-line.py cite "O-23"; orchestrator/run/RATIONALE.txt has no entry O-23 (O-22 is followed by O-24).
- test-line.py [roundtrip] GOOD says "12 kinds"; `CONTENT_DB` in `line.py` lists 11 — a kind absent from the table is written as JSON by default, so a vocabulary kind has no declared form.
### Doubtful
- With O-24 in force the three features describe a line language nothing uses; they are proven and possibly dead.

---

# Findings: book-cov-display

# Findings — book-cov-display

Verified: `hwut.report.features` shows no undefined feature, no missing document, no unread statement for the six directories; `hwut.config.show --no-default` shows no SYNTAX / VOCABULARY / REFUSED line. No test was run.

## hwut/engine/bookkeeper/TEST
documents read: README.txt, RATIONALE.txt (index, B-4, B-5, B-14 in full), test_run_info/RATIONALE.txt, adm/WORK/intend/22 and spec/23 (grep)
features: 31  (proven-by-link 27, unproven 4)   NONSENSE? runs: 1
### UNPROVEN — claimed, no test here
- empty-name-as-above: an empty test cell means the row above — README 1a, B-8. The committed book.csv shows it; no run prints or asserts it.
- known-before-member: an id issued with no row makes a row with verdict 'aspirant' — B-14.
- retired-book-name: 'result_db.csv' / 'result_db.json' read, replaced by 'book.csv' at first write — README 1a, B-10.
- adopt-entry: 'adopt()' takes a removed entry, a standing name refused — README 1a.
### NONSENSE? — test runs proving nothing claimed
- test-bookkeeper.py [setup_delta]: 'compare_setup_delta' records only the compare options that differ from the default ("what somebody CHOSE is what the book keeps"). README 1a and B-6 say the book holds no configuration at all; no document claims a setup delta.
### Documents silent — behaviour tested, stated nowhere
- protected-base: test-bookkeeper.py protection, damage — write protection of book.csv and "a damaged book reads as empty" belong in README 1a.
- lock-dead-holder: test-stream_store.py lock_dead — README 1a states only the live holder ('DirectoryBusy').
- promotion, nominal-kinds: test-stream_store.py — README names 'stream_store.py' in one line and says nothing of promotion or the one-pass stream.
- register-shown: test-test_id_db.py face — 'hwut.config.show --show-ids' stands only in the face's help.
- divergence-on-call: README names 'divergence()' as a door, not what it answers.
### Proven elsewhere
- the naming law 'same' (B-30) — RATIONALE PINNED — services/TEST/test-header-words.sh same
- 'shape_of' GREW/SHRANK/DIVERGED (B-5) — services/TEST (test-report), per the entry
- 'stderr-untolerated' as a stain (B-29) — services/TEST (test-accept.sh / test-face-words.sh mention it; not verified)
- a test carried into another directory is retired here and issued afresh there (README 4, D-14) — services (hwut.move), not verified
- a refusal is shown '[ ?! ]' / '[REFUSED]' and exits 2 (test_run_info B-17) — services/TEST/test-accept.sh
### Contradictions and stale statements
- README 1 and 1a say the register is 'GOOD/test_ids.dat'; test-test_id_db.py book_format and the committed book.csv show the register IN book.csv ('# vut-register' block, columns test_id;choice_id). B-14 cites "B-13 making the book the register", and RATIONALE.txt holds no B-13 entry (nor B-19..B-23). Feature 'register-in-the-book' is stated as the tests and B-14 say.
- README 1a gives the header 'test;choice;verdict;report;stain' and then describes a 'coverage' column; B-27 removed it. The header also lacks test_id;choice_id.
- README 1a says "no row carries a configuration" (B-6); test-bookkeeper.py setup_delta says a chosen compare setup is kept.
- README 5 (the tests) omits test-traces.py, test-unaccepted.py and the choices one_act, stain, book_format.
- test-bookkeeper.py header still says "one entry per (test, choice, operation)"; B-7 and the GOOD say one row per choice, an operation is no dimension.
### Doubtful
- retired-book-name: services tests mention 'result_db' (test-accept.sh, test-refresh.py); it may be proven there.
- one-row-per-choice / decision-only-book are linked to 'reproduce' as well; that choice prints the id columns the README does not know.

## hwut/engine/bookkeeper/test_run_info/TEST
documents read: README.txt, RATIONALE.txt (B-15, B-16, B-17)
features: 8  (proven-by-link 7, unproven 1)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- verdict-apart-from-state: 'last_verdict' None where nothing judged, a failed member still a member — README 'The verdict and the state are factually separate'. 'sealed' judges with True only; 'CTestRunInfo' / 'of_row' / 'on_stain' appear in no run.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- none
### Proven elsewhere
- an incomplete acceptance is booked 'aspirant' (B-16) — engine/bookkeeper/TEST/test-unaccepted.py booked
- refusal shown in the flow, exit status 2 (B-17) — services/TEST/test-accept.sh
### Contradictions and stale statements
- README event table lists 'on_stain(repeat_n, when)' citing "B-2"; B-18 made the stain one cell of keywords and B-25 removed the instant.
- RATIONALE B-15 says "Nothing calls it yet"; B-16/B-17 say it is wired. B-14 calls ASPIRANT "a verdict", README says "'aspirant' is not a verdict".
### Doubtful
- 'on_detected_unaccepted_in_good' from ASPIRANT and 'on_nominal_removed' from UNKNOWN are not in the transitions page; whether "every event from every state" is meant is open.

## hwut/engine/coverage/TEST
documents read: README.txt (whole), RATIONALE.txt (index; D-29 and D-40-neighbourhood only), OVERVIEW-coverage-roads.txt (part), DISCUSSIONS.txt (index), HOW-TO-INTEGRATE (grep)
features: 11  (proven-by-link 11, unproven 0)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- none kept (see Proven elsewhere)
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- affected-help: test-affected.py help — '--help' of the face.
- diff-strip: test-affected.py diff — README 4c shows '-p N' in the synopsis and never says what it does.
- source-rebased: test-output.py rebased — README states rebasing for the face (4c) only, not for the gathered output.
### Proven elsewhere
- '--cov-dir' / './hwut.coverage' as input of hwut.affected, runs spelled as wishlist lines (README 4c) — services/TEST/test-book-defects.sh affected. Every run here uses '--records'.
- the output directory's three files, exactly one run, '-o' / '--dont-ask' (README 5, D-42) — services/TEST/test-cov_run.py output, door
- the coverage run: not a test run, testimony, one case at a time, caps, badges '[REC]' / '[NO REC]', the local trace (D-19, D-21, D-22, D-38, D-41) — services/TEST/test-cov_run.py, operations/TEST/test-coverage_provision.py
- the converters and 'hwut.cov.formats' (D-13, D-44, D-45) — services/TEST/test-cov.py
- 'hwut.tell' carries its coverage (D-24) — not looked up
### Contradictions and stale statements
- README 6b: the GOOD file of 'hwut.cov.formats' "stands in 'TEST/GOOD/'" — it does not; the 'formats' choice is in services/TEST/test-cov.
- README 9 "RATIONALE D-1 .. D-11" — the file runs to D-45. D-25 is WITHDRAWN.
- README 4c closing paragraph ("'record_iterable' walks for '*.cover'. That is a stand-in") is stale against D-42 (records are removed once gathered).
- test-affected.py refused: the section is titled "no '--records'" and the refusal speaks of '--cov-dir'.
### Doubtful
- affected-rebase is linked to 'answer' on the strength of 'parser/TEST:0.0' in the page; the page does not print the join itself.

## hwut/engine/coverage/database/TEST
documents read: ../README.txt, ../RATIONALE.txt (index), FORMAT.txt (section index), DISCUSSIONS.txt (index)
features: 31  (proven-by-link 30, unproven 1)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- group-ids-kept: 'index_of' handed the persisted group table keeps its group ids across builds — README 4b. test-index.py never hands one in.
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- points-of-items: test-measure.py points — the conversion to (line, name, total, mask) stands only inside D-43's text.
- README 2 and 6c name 'function' once; test-measure.py registration counts FIVE measures; README Status says four.
### Proven elsewhere
- the group table itself (B-3) — engine/bookkeeper/TEST/test-group_table.py
- the HTML / TeX presenters (D-29, D-45) — services/TEST/test-cov_visitor.py
### Contradictions and stale statements
- README 2 places record.py, measure.py, index.py, binary.py, FORMAT.txt directly in coverage/; they stand in coverage/database/.
- README 6c: "MC/DC is registered and nothing produces it yet" — still so; the feature proves the encoding only.
### Doubtful
- presenter-vocabulary rests on D-28/D-29, which are about structure; the run checks the class against the visitor's vocabulary — close to a test of how the code is written.

## hwut/engine/coverage/readers/TEST
documents read: ../README.txt 6b/6c/7, ../RATIONALE.txt (index), ../OVERVIEW-coverage-roads.txt, ../HOW-TO-INTEGRATE-A-COVERAGE.txt (grep)
features: 22  (proven-by-link 22, unproven 0)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- none
### NONSENSE? — test runs proving nothing claimed
- none
### Documents silent — behaviour tested, stated nowhere
- readers-agree: test-readers.py agreement — three formats of one run, one answer; OVERVIEW says it for simplecov only.
- verilator-native-read, psl-read, simplecov-read, ucis-read: stated only in OVERVIEW 'Formats read since'; README 6b 'What each format says' has no paragraph for them.
- lcov: counts are read where asked for, an absolute 'SF' is made relative, a file named twice is unioned — in the page, not in README 6b.
### Proven elsewhere
- the election and the candidate lists (D-2, D-26) — engine/coverage/database/TEST/test-record.py election
- the registry table 'hwut.cov.formats' (D-13) — services/TEST/test-cov
### Contradictions and stale statements
- README Status "ELEVEN READERS over eleven formats"; README 2 lists seven modules; the directory holds eleven (ghdl_psl, simplecov, ucis, verilator missing from the list). README 2 also places reader.py and registry.py in coverage/; they stand in readers/.
- README 6b: 'gcov' serves VHDL through GHDL; test-readers.py ghdl states "the header MISNAMES the language: the gcov reader says 'c' over a '.vhdl' file". The run is linked to gcov-serves-vhdl; the record's language is wrong.
- README 6b: "Those three are the only shapes there are" (coverage / gcov / lcov) — written before the native .dat, psl, ucis readers.
- README 8 test list says nothing of test-real-input.py.
### Doubtful
- real-artefact-per-format (D-30) is a rule about the test input; it is a claim on the tree's discipline more than on the software.

## hwut/engine/display/TEST
documents read: README.txt, RATIONALE.txt (index; D-9, D-15, D-31, D-32, D-35, D-40, D-46, D-47 in part)
features: 29  (proven-by-link 27, unproven 2)   NONSENSE? runs: 0
### UNPROVEN — claimed, no test here
- setup-lines-silent: session/build lines silent unless '--show-details', VERBOSE or failure; '--show-timing' restores the seconds column — D-9. Neither option appears in any run here or in services/TEST.
- here-name: a run asked inside a TEST directory names it from the root conf — D-47 (2026-10-11); its PINNED line names no test.
### NONSENSE? — test runs proving nothing claimed
- none left unlinked; see "Documents silent" — six runs of test-run.sh prove nothing DISPLAY's documents claim.
### Documents silent — behaviour tested, stated nowhere
- jobs-budget (jobs-budget), busy-directory-fault (busy), store-and-timing-knobs (nostore, timing), short-form (short-form), label-silence (labels), strategy-refused (strategy-refused): all in test-run.sh. README says these are EXECUTION and SELECTION words, "the face's", not display's. They are real behaviour of 'hwut.run'; the claims belong in services' / orchestrator's documents and the runs arguably in services/TEST.
- empty-selection-noted: test-plain.py empty — the NOTE line and the roll-call of zeros.
### Proven elsewhere
- the REFUSED block and '[REFUSED]' ink (README 'Refused', D-46) — services/TEST (test-run-uncapped.sh; D-46 names test-ignore.sh refused_too)
- the coverage vocabulary '[REC]' / '[NO REC]' (D-40) — services/TEST/test-cov_run.py run, door
- 'hwut.report' as wide as the run, 'not in book' (D-33, D-37), the reason word in the report (D-31) — services/TEST/test-report.sh run_agrees
- HINTS against 'hwut.help' (D-35, D-36) — services/TEST/test-help.sh explain
### Contradictions and stale statements
- README 'The line format' gives 'hh:mm:ss | NNN | [EVENT] NICK:base [choice]'; D-9/D-15/D-20 and every GOOD show 'START test-a.sh  a ... [OK]  ||1' — no clock, no nickname, no brackets around the badge.
- README 'Nickname derivation' describes 'derive_nickname'; no such function stands in the code and no page shows a nickname (SILENT prints 'stderr> ERROR ...'). No feature stated.
- README 'The closing blocks' names DIRECTORIES, FAULTS, FAILURES; the pages show DIRECTORIES, HINTS (D-35), then RESULTS.
- README lists the tiers' flow as 'DIR, START, END, SKIP, FAULT, NOTE'; the pages say 'ERROR' for a fault, and 'DONE' under '--brief'.
- RATIONALE D-13/D-14 say "'test-run.sh labels' STAYS RED"; the book has it 'true'.
- RATIONALE numbering jumps D-20 -> D-31, D-37 -> D-40 -> D-46.
### Doubtful
- GOOD/ holds four '*.txt.candidate' files (test-plain.py mixed, tiers, unknown, words; 2026-10-10) that differ from their nominals — pre-D-31 pages left behind, or an unfinished acceptance.
- exit-status (D-3 / E-1) is the face's law recorded in display's RATIONALE; kept here because the entry and the runs both stand here.

---

# Findings: support-demo

# Findings — support-demo

## hwut/test_writing_support/hwut_pype/TEST
documents read: hwut_pype/README.txt, hwut_pype/MANUAL.txt, top README.md (pype section), doc/manual-note-pype-is-part-of-the-oracle.txt
features: 38  (proven-by-link 32, unproven 6)   NONSENSE? runs: 0

### UNPROVEN — claimed, no test here
- pype-mode-information: `pype.file_name()`, `pype.mode_name()`, `pype.stack_depth()` — MANUAL 6, README DISPATCH. No test or example calls any of the three.
- switch-request-order: switch applied after the handler's effects, last request wins, switch to the active mode is a no-op — MANUAL 7 SWITCHING, README MODES.
- import-once: a file imported twice is entered once ("idempotent") — README SCRIPT GRAMMAR, MANUAL 4. `imports` shows resolution, env expansion, unquoted, missing, cycle — not the double import.
- block-exception-traceback: an exception in a block gives a traceback pointing into the pype script — README ERRORS, MANUAL 3.
- wait-guard: an `if` cause on `pype.time()` fires when a wait exceeds its limit — MANUAL 1 and 9, top README. Example 05 carries the guard, but it never fires in any run (`pype.time() >= 0` is all that is shown).
- runs-under-pypy3: the engine runs unmodified under pypy3 — MANUAL 10.

### NONSENSE? — test runs proving nothing claimed
- none

### Documents silent — behaviour tested, stated nowhere
- input-file-arguments: test-pype.py [pipe] — `hwut.pype SCRIPT FILE...` reads the files in order as one stream, and the trace names file and per-file line. Neither README INVOCATION nor MANUAL 3 mentions input-file arguments; both show stdin only.
- absent script file (linked to exit-status): test-service.sh [absent_script] — exit 1, `pype: [Errno 2] ...` on stderr, nothing on stdout. The documents speak of "script error" with `file:line`; a script that cannot be opened is not mentioned (belongs in MANUAL 3, exit status).
- `sys.exit(n)` skipping pending `<eof>`/`<exit>` handlers (MANUAL 6) is only half shown by [imports]: the status is shown, the skipping is not visible in the GOOD.

### Proven elsewhere
- "A pype-d stream that ends without the token is the pype script's fault; the framework's diagnosis names the script", `HWUT_NO_TERMINAL`, 'terminated-without-hwut-end' — MANUAL 1b — framework behaviour (engine/operations, services); not checked where.
- "A pype is part of the oracle" — doc/manual-note-pype-is-part-of-the-oracle.txt — a statement of method, no behaviour of pype; not a feature.

### Contradictions and stale statements
- MANUAL 8 / README INHERITANCE: `"abc"` and `"abc" "def"` are "disjoint, lawful", and "pattern dispatch is order-free: at most one pattern can match a line". test-pype.py [patterns], banner "first-match dispatch: earlier handler wins": the line `abc def` matches BOTH (patterns are found anywhere in the line), and the first one fires. Either the interference check misses this pair or the manual's example is wrong; as it stands dispatch is NOT order-free for it. Feature `one-handler-per-line` is stated as MANUAL 6 says (definition order, first fires); `shadowing-forbidden` as MANUAL 8 says.
- README NAMESPACE: "provides `mode(name)` and, during a match, `line`". MANUAL 6 and the implementation know only the `pype` object (`pype.goto()`, `pype.line()`); `mode()` and `line` do not exist. README MODES also still says "the namespace function `mode("OTHERMODE")`". The test header and several banners ("mode() call form", "mode('<default>') rejected", "'line_n' and 'time_sec'") carry the same old words.
- README KEYWORDS / MANUAL 4: "no word is reserved as a mode name". test-pype.py header says "'FLUSH' is reserved", and [inheritance] carries the banner "IGNORE reserved as mode name" (what it records is an unknown-mode error and a bad effect, not a reservation). Stale test wording.
- README FILES: "TEST/ HWUT test suite (16 choices)" — there are 17 choices in test-pype.py and 3 in test-service.sh. The `CHOICES:` line in the test's docstring lists 16 (no `terminal`). README also names "manual.txt"; the file is MANUAL.txt.
- MANUAL 3: "Exit status: 0 ... 1 on a script error. Errors go to stderr with 'file:line'" — the absent-script error carries no file:line (it is the platform's errno text).
- MANUAL 5 says unmatched lines "meet the mode's 'else:'"; the cause is spelt `<else>` everywhere else.

### Doubtful
- one-handler-per-line and shadowing-forbidden cannot both be the whole truth (see first contradiction); both are linked and both show PROVEN.
- no-reserved-mode-names is linked to [boundaries_stack] and [else_flush]; [inheritance] holds the contrary banner and is not linked to it.
- python-version-independence: the audit is static, on one interpreter (MANUAL 10 says so itself).
- trace is linked to [boundaries_stack] and [pipe]; "stdout stays clean" is shown only indirectly.

## hwut/test_writing_support/python/TEST
documents read: README-hwut_hocon.txt, README-hwut_runner.txt, RATIONALE-hwut_runner.txt, README-hwut_vterm.txt, doc/HOWTO-HWUT-BRAINSTORM.txt (section 9), adm/WORK/review-r10.txt (vterm lines). No HOW-TO-WRITE-HWUT-TESTS.md stands in the tree.
features: 45  (proven-by-link 29, unproven 16)   NONSENSE? runs: 0

### UNPROVEN — claimed, no test here
- hocon-keys: a dot in a key is literal (`test-gen.c`), a key with a blank carries quotes — README-hwut_hocon 1, 2.
- runner-command-line, runner-info-block, runner-coroutine-choices — README-hwut_runner head, section 1.
- runner-interactive-session, runner-two-sinks, runner-stray-output, runner-done-status, runner-session-end — README-hwut_runner 2; RATIONALE entries 1-4.
- runner-interactive-byte-exact — RATIONALE entry 1 ("batch is a pure accelerator"), README 5.
- runner-done-barrier — README 4, RATIONALE entry 6.
- runner-process-scheme — README 3, 5; RATIONALE entry 5.
  (hwut_runner has NO test of its own in this directory: all eleven of its features are unproven here.)
- vterm-alternate-screen: a full-screen program's picture does not mix with earlier lines — README-hwut_vterm 2. [events] shows only the property event `alternate-screen = 1`.
- vterm-expect: `expect` waits for a text, `TimeoutError` carrying the screen — README-hwut_vterm 2. Never called in the test.
- vterm-wait-kills: `wait` kills an application that does not end — README-hwut_vterm 2.
- vterm-library-probe: `python3 hwut_vterm.py` — README-hwut_vterm 4.

### NONSENSE? — test runs proving nothing claimed
- none (the ten features of the two `deterministic_*` modules are kept under "documents silent"; without that fairness all 16 runs of test-deterministic-random.py and test-deterministic-timeline.py would be NONSENSE?).

### Documents silent — behaviour tested, stated nowhere
- random-stream-reproducible, random-gauss, random-sampling, random-spread-selection: test-deterministic-random.py (7 choices) — `deterministic_random.py` has no README; only class docstrings. Wants a README-deterministic_random.txt (generator, seed, what is exact and what is libm-bound, SelectionMarker).
- timeline-schedule, timeline-order-in-tick, timeline-termination, timeline-yields, timeline-cancel-silent, timeline-trigger-contract: test-deterministic-timeline.py (9 choices) — `deterministic_timeline.py` has a module docstring (ticks, priority, stable order) and no README; termination, stop, cancel, yielding are stated in the test header only.
- `script_runner.py` (do, CRunScript, tree_boundary) and `space_iterator.py`: neither document nor test here; no feature stated.
- hwut_runner prints `<hwut-end>` unless `HWUT_NO_TERMINAL` is set (hwut_runner.py ~l.300); README-hwut_runner does not mention the terminal token at all.
- hwut_runner offers the closest choice name for a mistyped one (`_levenshtein_best_match`); not in the README.

### Proven elsewhere
- runner interactive protocol, as the framework's side sees it — README-hwut_runner 2 — tests naming HwutRunner together with the protocol words stand in engine/orchestrator/run/TEST (test-endtoend.py), engine/procsitter/TEST (test-procsitter_interact.py), engine/orchestrator/exploration/TEST; not verified which claim each holds.
- "In a HWUT specification a key bound to nothing switches a feature off ..." — README-hwut_hocon 4 — the exploration component's concern.
- vterm "first user: services/lib/viewers/keyed/TEST/test-screen.py" — README-hwut_vterm 3.
- "The engine converts ParseFault into its own record" — README-hwut_hocon 7 — engine.

### Contradictions and stale statements
- README-hwut_runner 6: "make_script_application(), ScriptApplication" as "further content of the module" — neither exists in hwut_runner.py; the content is `script_runner.do()` / `CRunScript`.
- README-hwut_hocon 6 titles the section "REFUSED, BY NAME" and lists a duplicate key there; the GOOD files report a duplicate key and an unquoted string as kind SYNTAX, only include / `${}` / `+=` as REFUSED. Consistent with section 7's two kinds, but the first pass's feature ("an unquoted string is refused by name") was not.
- README-hwut_vterm 4 quotes the message "libvterm is not installed, and 'HWUT_LIBVTERM' names no file"; [missing] records "libvterm cannot be loaded from '/nowhere/libvterm.so'" (the case of a named file that does not load, which the README does not describe).
- README-hwut_runner 1 "Exit status is the process's exit status" says nothing; section 2 gives the real rule for 'done' only.
- RATIONALE-hwut_runner entries carry no ids (noted already in adm/WORK/RATIONALE-INDEX 2.4); `explanation` therefore counts entries 1-6.
- adm/WORK/README-INDEX gives README-hwut_hocon 174 and README-hwut_runner 141 lines; they hold 185 and 140.

### Doubtful
- hocon-booleans-and-nothing is linked to [scalars], whose GOOD shows one True, one False and three None; that every spelling (yes/no, nil/none/nihil) is among the input was not checked line by line.
- hocon-faults-are-values: "recovers at the next line" is not stated in the feature; [unclosed] shows the parse ENDING, not that it continues behind the fault.
- vterm-cell-attributes: "the same on every libvterm version" is proven by one recorded run on one version; the three-version measurement stands in the README only.
- benchmark-hwut_hocon.py is a measurement, not a test (it answers --hwut-info with nothing); it appears in no report.

## hwut/demo/python/TEST
documents read: top README.md (Try it; Describing behaviour; Order, tamed: potpourri / pype; A failure, from run to blessing), demo.py docstring, protocol.sh comment, pype MANUAL 1b. No README stands in hwut/demo.
features: 10  (proven-by-link 9, unproven 1)   NONSENSE? runs: 0

### UNPROVEN — claimed, no test here
- law-breach-verdict: `protocol.pype` on a law-breaking stream prints the four BREACH/NOT answered lines and `law: BROKEN` — README "The same script on a stream that breaks the law (in demo/python/TEST)". Only `protocol.sh clean` runs; the breaking stream is a command for the reader's hand. A second choice `broken` in protocol.sh would prove it (deterministic input, no race).

### NONSENSE? — test runs proving nothing claimed
- none

### Documents silent — behaviour tested, stated nowhere
- none; pype-owns-terminal-token is stated in the pype MANUAL 1b and in protocol.sh's comment, the top README only shows `<hwut-end>` in the output.

### Proven elsewhere
- regions `##! table`, `##! point-cloud`, `##! verbatim`, `##! ignore` — README "Describing behaviour" — no demo shows them; engine/compare/TEST.
- "A line missing, extra or different still fails", "a worker that did not report, or reported 4 jobs, fails the block", "a handle that changes in mid-stream is red", "a binding that breaks its law is red", "20.30 would not [pass]" — README and demo.py docstring — every demo run is a PASSING run and proves the tolerant side only; the refusing side is engine/compare/TEST.
- "A failure, from run to blessing" (one choice red, exit status 1, hwut.run.diff, hwut.accept.interactive, hwut.report, hwut.help) — README — services/TEST.
- `hwut.pype --dry-run / --trace / --example` — README — test_writing_support/hwut_pype/TEST (features dry-run, trace, example-input).
- "A stream that does not end in `<hwut-end>` never completed and is not accepted" — README — engine/operations, services.

### Contradictions and stale statements
- README Status: "Tests: 911 ok, 1 fail ... at commit 70417c0" — a dated measurement, not checked.
- README potpourri section: "15 of 15 runs pass ... failed 12 of 15 runs on a two-core machine" — a measurement no run holds.
- README "Try it" says `RESULTS: 6 ok, 0 fail`; the six runs stand (5 in demo.py, 1 in protocol.sh), all PASS in book.csv.

### Doubtful
- demo-passes-on-every-run is linked to all six runs: it is PROVEN exactly when all six pass, which is the README's claim; "on every run" is a statistical statement one recorded verdict cannot hold (hwut.run.stability would).
- The demo's features 2-7 are compare's behaviour shown in the demo; they are stated here because the README claims the DEMO shows them, with engine/compare/MANUAL.txt as second document.
- equivalence-pattern and numeric-ratio share the one run [tolerance].
