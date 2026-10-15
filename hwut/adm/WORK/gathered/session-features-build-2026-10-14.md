# Build hand-off -- the central feature file (R-96), 2026-10-14

RULED, NOT BUILT. Statement: `adm/WORK/spec/23-features.txt` VERSION 10
(sections 3-11, open points 12). Rulings with graveyard: exploration
`RATIONALE.txt` R-96. User words: `doc/HOWTO-FEATURES.txt` section 13. Book
note: `doc/the_book/dev/NOTES-feature-ids-keys-wish-2026-10-13.md` (Projects
store) section 9. This replaces the restructuring part of
`session-restructuring-and-map-2026-10-14.md`; the o-14 / o-10 rulings in
that file STAND, o-12 / o-13 / o-11 / o-15 are replaced or closed.

## Measured start (the BUILT tree, bundles 111-113)

    engine/orchestrator/exploration/feature_relation.py   1297 lines  read + judge
    engine/orchestrator/exploration/feature_adapt.py       594 lines  text surgery
    engine/orchestrator/exploration/feature_wish.py        221 lines  -F / -k
    engine/orchestrator/exploration/feature_code.py        121 lines  (--code, untouched)
    readers: services/lib/report/features.py, feature_document.py,
             services/lib/sanitize/{command,propose}.py, services/{sanitize,
             remove,rename,help}.py, exploration/{task_list_query,finder,
             configuration_tree}.py, engine/bookkeeper/id_scope.py
    34 feature files stand in the tree (`hwut-features.conf` +
    `hwut-feature-map.conf`).
    pinned by: exploration TEST test-feature_relation.py / test-feature_adapt.py /
    test-feature_wish.py; services TEST test-report-features.py,
    test-sanitize-relations.py, test-help.sh [nonsense];
    engine/orchestrator/run/TEST/test-adapter.py; GOOD pages listed by
    `grep -rl hwut-feature` under */TEST/GOOD.

## Order of the build (each a bundle, census between)

STATUS: step 1 BUILT (bundle 116), step 2 BUILT (bundle 117: the detector),
step 3a BUILT (bundle 118: the writer, 'init', 'register', 'tree'), step 3b
BUILT (bundle 119: 'retire', 'move', 'key.add', 'key.remove'), step 3c BUILT
(bundle 120: 'hwut.sanitize register|redirect|repoint|fold', the hint of
'hwut.run', 'hwut.help'), step 4a BUILT (bundle 121: 'feature_view.py', the
report's page and '--matrix' on it), step 4b BUILT (bundle 122: the feature
document on the view), step 4c BUILT (bundle 123: the wish on the view; the
usage line of every wish face gained '-e'), step 5 BUILT (bundle 124: our
tree migrated by 'adm/migrate-feature-map-2026-10-14.py' -- 34 directory ids,
934 leaves under their published ids (all equal to their full ids), the tree
mirroring the directories with colliding names qualified ('orchestrator-run',
'compare-engine', ...), 'hwut-feature-map.conf' deleted; census equal to the
baseline, 'register' and 'sanitize.propose --relations' find nothing), step 6
BUILT (bundle 125: the migration script deleted; 'feature_adapt.py' deleted,
its link readers and the carrying of a moved test's features re-made for the
central file in 'feature_carry.py'; 'feature_relation.py' reads TEST files
and per-TEST relations only; the sanitizer kinds and verbs
'relate/unrelate/retire' gone; report, document and wish read the view only
and refuse without a central file; the old tests deleted or ported, six
features retired on this tree; HOWTO-FEATURES rewritten whole). DONE.
A new feature is registered with 'hwut.features.register'. Step 3c: 'hwut.sanitize redirect |
repoint | fold' (the proposal lines of the detector applied), the hint line of
'hwut.run', 'hwut.help'. The pairing of leaves
by title was IMPOSSIBLE (a live leaf keeps no title) and is corrected in
spec 23 section 7.

1. READER. New module (name: `feature_registry.py`) reading
   `hwut-root-features.conf`: directory_map, tree, retired; LAZY (nothing is
   read at import or by a face that does not ask). The faults of the file (spec
   23 section 3 rules, section 4 identifiers = o-10). The relation (leaf ->
   linked runs) is built from it and the TEST files. State/verdict (section 6,
   o-14). Reuse hwut_hocon, unwrapper faults.
2. DETECTOR (section 7) as ONE function used by `register` and
   `sanitize.propose --relations`; pairing by fingerprint; the SWAP check;
   named pairings on the proposal lines.
3. FACES `hwut.features.{init,register,retire,move,tree,key.add,key.remove}`
   (section 8), `hwut.sanitize redirect|repoint|fold`. Surgery by `amend.py`.
   The hint line of `hwut.run` (measure its cost: it reads one file).
4. REPORT / DOCUMENT / WISH on the new relation: `-F` tree paths, `-e/--feature-ext`,
   `-k` effective keys; `hwut.report.list` round trip. Usage lines of the faces
   that take a wish move: run `hwut.run --glob "test-*"` (the census does NOT
   reach the `meta` pages).
5. MIGRATION of our own tree by a ONE-OFF script (under adm/, NOT part of
   HWUT): component files -> aggregates with the same nesting and keys; the map
   -> leaf lines keeping every external id; `= none` -> `retired` (id only);
   directory ids generated. `hwut.features.init` refuses the old vocabulary and
   names it. DELETE the script in the next bundle (`--delete`).
6. DELETE: `feature_adapt.py` parts replaced, the old sanitizer kinds
   (no-file, unlisted, moved, dangling, twin, map-*), the old GOODs they pin,
   and `hwut-feature-map.conf` / component files. Doc pass: HOWTO sections
   3, 5, 6 rewritten (section 13 folds in), README of exploration, services.
7. GATE: real tree `hwut.features.register` says nothing to register;
   `hwut.sanitize.propose --relations` says "nothing to sanitize".

## Proof (unchanged procedure)

`cp -a` the tree to scratch, strip TMP, OUT, `__pycache__`, hwut-traces*,
hwut.log, .coverage, htmlcov; run `hwut.run` in the copy; compare the fails
with the 11 standing ones (no libvterm: test-screen.py x3, test-hwut_vterm.py
x8). The VM restarts between turns: run the census inside ONE turn
(`setsid nohup`, poll with `sleep` under 10 minutes). The standing flake
`test-sanitize-books` stays named, not fixed.

## Decisions taken without a ruling (spec 23 o-20, strike if wrong)

base64url 8-character quoted directory ids; ids only for directories owning a
TEST feature file (path = the component directory); one namespace for
aggregate keys and external ids; `register` directories first, then leaves;
`--list` names leaves by external id; no `hwut.features.remove` (retire);
pairings as `hwut.sanitize redirect|repoint|fold`; the migration script is
deleted after use.

## Open (ask, do not decide)

- o-16: does `-F` also accept an internal id `<dir id>:<name>`?
- the empty aggregate: OPEN (assumed).
- wording of all sanity messages; the `# vut-register` data markers.
- standing: `test-sanitize-books` flaky; recorded-failure GOOD in
  `engine/operations/interaction/TEST/test-tui.py [elements]`.
