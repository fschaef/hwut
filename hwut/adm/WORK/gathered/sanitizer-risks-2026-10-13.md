# What may go wrong for the sanitizer -- feature files and the map

Written 2026-10-13 with the implementation of the feature model (bundle A):
ONE file kind `hwut-features.conf`, ids built by the parent's `childs` keys,
the required `hwut-feature-map.conf`, `keys`. The sanitizer's part is
`hwut.sanitize.propose --relations`, `relate`, `unrelate`, `retire`, and
`hwut.move` / `hwut.rename` / `hwut.remove`, which call the same adaption
(`engine/orchestrator/exploration/feature_adapt.py`).

Each entry: WHAT HAPPENS, WHY, WHAT SAVES US / WHAT TO DO.

## 1. The tree flips from implicit to explicit

**What.** A tree whose only feature files stand in TEST directories is
*implicit*: nothing is judged but the map. The moment ONE `hwut-features.conf`
stands outside a TEST directory (in the tree, or directly above the root
asked), the tree is *explicit*: every component on the way must then state a
file and be listed by its parent. One new component file makes the sanitizer
propose `relate` for every directory down to it.

**Why.** The rule "an explicit tree is judged completely" has no half-way.

**Saves us.** `relate` writes an empty `features {}` and lists the directory
under its directory name as key (`key_of_name`). Nothing is lost; the proposal
can be read before it is applied.

**Watch.** Adopting is all-or-nothing. A proposal of 40 `relate` lines on the
day the first component file is written is correct, not a bug.

## 2. A directory moved by hand

**What.** `mv a/x b/x`: the file above `a` still lists `x`; `b` does not.

**Detected only if** exactly one other component of that name states a file,
is not listed by its own parent, and the old lister is the only one that still
lists it (`old_lister_of`, `_moved_to`). Then: MOVED, `relate` carries the entry
WITH ITS KEY. Ids below keep their keys; only the chain above changes.

**Goes wrong when** two candidates exist (two directories called `core`): the
sanitizer proposes UNLISTED for the new place and DANGLING for the old one.
`relate` then lists the new one under its directory name, `unrelate` drops the
old one -- the KEY is lost, so the ids below change if the author had renamed
the key.

**Also.** Moving a directory into a place where a sibling of the same key
exists: the key is taken twice in `childs` (duplicate key fault, the first
stands). The author must rename.

## 3. The map after a move: pairing by suffix

**What.** After a move the map points to full ids that stand nowhere
(MAP_GONE) while the same features stand unmapped under new ids (UNMAPPED).
`map_pair_list` pairs them by the longest common SUFFIX of gone id and new id
(at least the feature name); only a UNIQUE best pair is repointed.

**Goes wrong when**
- the directory was also renamed at its leaf -- the feature name is the same
  but the chain's tail differs; still paired if unique;
- two features share a name (`scroll` in two components): a tie -> nothing is
  repointed, `retire` and a fresh id result, and the customer's id is lost;
- features were MERGED or SPLIT: no unique pair -> the old ids stay MAP_GONE,
  the new ones UNMAPPED. This is for the author: `retire` the old id, or edit
  the map by hand so the old published id points to one survivor;
- a WRONG pair that is unique by suffix but semantically another feature: the
  published id silently re-binds. Mitigation: the proposal text names the
  pairs; the sanitizer should be read before applying. (Open: print old -> new
  on the proposal line itself, not only in the `relate` result.)

## 4. Renaming a feature or a key

**What.** Renaming `line-pairing` to `pairing` changes the full id. The map has
the old id (gone) and the new one is unmapped: paired if unique by suffix,
else retire + new id.

Renaming a KEY in a parent's `childs` (`eng = "./engine"` -> `engine = ...`)
changes every full id below. The pairing handles it only when the suffix rule
finds unique partners for EACH feature. For big components that is usually the
case; for repeated feature names it is not.

**Advice for authors.** To keep published ids across a rename: rename the key,
then run `relate` -- check the proposal repoints rather than retires.

## 5. MAP_CLASH, MAP_TWIN

- MAP_CLASH: a RETIRED published id equals the full id of a standing feature.
  `relate` cannot publish the feature under its own id (the id is taken by
  history). The author must rename the feature or revive the id deliberately
  (bind it to the feature's full id). Nothing is healed automatically.
- MAP_TWIN: two published ids bound to one full id, or one published id twice
  (duplicate key fault, first stands). Not healed; noted on stderr.

## 6. Cost

Every `relate`, `unrelate`, `retire` explores the whole tree again
(`relation_of_tree`). A proposal with 100 lines applied costs 100 explorations.
Fine for our 917 features; for a tree 20 times larger apply gets slow. If it
hurts: one exploration per `apply` run, with the relation updated in memory.

## 7. The map is judged completely only at the top

When the root asked lies BELOW the tree's top, only UNMAPPED is judged: entries
pointing outside the subtree are not seen (they are not gone, they are outside).
The map file is then at path `..`. `retire` of an id outside the subtree is
refused as "not a feature of this tree" or does nothing -- check before running.

## 8. Text surgery

`amend.py` edits files as TEXT so comments and layout survive. Known:
- triple-quoted strings are handled since this bundle (`_string_end`);
- a `}` or `{` inside a triple-quoted `doc` does not confuse it (tested);
- UNTESTED: single-quoted strings with escaped quotes in the middle of a
  feature body; keys written as quoted strings with dots; CRLF files;
  tabs. A hand-written feature file in an exotic layout may make `entry_add`
  put the new line at a wrong place. The result is re-read after each edit by
  the next `propose`: a broken file shows up as a fault, not as silence.
- `entry_remove` leaves a trailing comment line of a removed entry behind
  (with a wrong indent). Cosmetic.
- added map lines are not aligned with their neighbours.

## 9. Keys that cannot be keys

A directory called `my.dir` or `2nd-try` or `-x` has no valid key by itself
(`.` or a leading `-`). `key_of_name` maps it to `my_dir`, `2nd-try`, `_-x`.
Two directories can collide on one key (`a.b` and `a_b`): the second is a
TWIN-like duplicate key; the sanitizer proposes both lines, the second
`relate` fails with the duplicate. The author renames a directory or edits the
key by hand. No check yet that warns before.

A directory called `TEST` is never a component; one without tests is skipped.

## 10. Hand-edited maps

- a published id with spaces, dots or slashes is accepted as written (it is a
  published word, not a key); the wish grammar of stage 2 matches NAMES by
  key. Published ids with `*` or `{` will confuse the glob in stage 2 -- the
  map reader should refuse them then. (Open.)
- an entry with a target that has the wrong shape ("x" without dots) is read
  as a full id with one level; it is gone, then (MAP_GONE) unless a TOP-level
  feature of that name exists.
- a map with the outer node `features` is a vocabulary fault, nothing is read.

## 11. hwut.move / hwut.rename / hwut.remove

- The map follows a moved test's features through `full_id_of`, which needs a
  `hwut-root.conf` above both directories. If none stands (`RootConfMissing`),
  the map step is silently skipped and the next `propose` says UNMAPPED /
  MAP_GONE. (Open: say so in the move's output.)
- A feature that is moved AND still linked from the source: copied (new
  published id under its own full id); the old stays. Two features of the same
  name in different places then exist: fine, different full ids.
- `merged` (the target already has the name) retires the OLD published id. A
  customer who holds the old id sees RETIRED, not the surviving feature. Decision
  taken: no aliases (settled with the user). Authors who want the old id to
  mean the survivor edit the map: bind it to the survivor's full id.
- `hwut.remove`: a feature left without a linked run becomes UNPROVEN; the
  feature is NOT removed from the file and the map is untouched (removing
  a claim is the author's decision). Only noted.

## 12. Old files

Files in the vocabulary of the past (`issued`, numbered entries, `id`, `parent`,
`hwut-composition.conf`) produce VOCABULARY faults and are not read; there is no
legacy reader. The 33 files of our own tree were migrated by a script; a user's
tree must be migrated by hand (or a one-off converter, not part of HWUT).
`hwut-composition.conf` is simply an unknown file: it is not named by any fault
(the finder does not list it). Open: a one-line NOTE when such a file stands.

## 13. Concurrent edits

`relate` reads, edits, writes; there is no lock. Two sanitizer runs at once in
one tree can lose an edit. The same holds for the old model; not new.

## 14. What a test of the sanitizer should keep doing

- the scratch-tree cases of `test-feature_adapt.py` and
  `test-sanitize-relations.py` (every kind judged, every adaption, move
  detected, map repointed, retire refused for a standing id);
- the real tree: `hwut.sanitize.propose --relations` must say "nothing to
  sanitize" after every bundle that touches a feature file or moves a
  directory. This is the cheapest regression of all.

## 15. Session to be held: restructuring and the map

Ruled 2026-10-13: a separate session on moves, inserted levels, merges, splits,
the suffix pairing and what a published id means afterwards (spec 23 o-12,
o-15). The risks of sections 3, 4 and 11 above are its input. Until then the
pairing rule stays as built and the proposal should be read before applying.
