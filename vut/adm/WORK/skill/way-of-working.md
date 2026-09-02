---
name: vut-work-discipline
description: The discipline for writing and discussing intent documents (intend/spec/plan files) in the VUT project's WORK structure, and for conducting design discussions with Frank-René. Use this skill whenever the user asks to write an "intend", "spec", or "plan" file, mentions adm/WORK or a component's WORK directory, asks to discuss an intent or a design fork, or asks to migrate disc-N/todo-N discussion files. Also use it when documenting rulings into RATIONALE, README, INTERNALS, or DISCUSSIONS files of the VUT project.
---

# VUT Work Discipline

How work is written down and discussed in the VUT project. The user
(Frank-René) is the sole ruling authority; Claude reports forks, never
closes them, and implements after rulings are played back.

## The WORK structure

```
adm/WORK/intend/<name>.txt     WHY, what-for; every todo is BORN here
adm/WORK/spec/<name>.txt       WHAT, precisely; derived from intend
adm/WORK/plan/<name>.txt       HOW, ordered steps
<component>/WORK/...           same three, received by TRANSFER when
                               the work becomes the component's
```

One name threads intend → spec → plan. WORK holds only what is OPEN;
when built and blessed, files are deleted and residue distributes to
the permanent bins:

```
README.txt        how to USE the component, what it does
INTERNALS.txt     internals, for those who dive in
RATIONALE.txt     RESULTS of discussions (rulings + graveyard),
                  never their history; append-only
DISCUSSIONS.txt   the history, kept only while relevant
```

One item, one bin. A sentence that fits two bins is two sentences.

## Writing an intend file

- Plain `.txt`, British spellings, `==` banner head naming the file as
  `intend/<name> -- TITLE`, then `COMPONENTS CONCERNED:` listing every
  component the work touches.
- State the INTENT: why the thing exists, what "done" changes. ASCII
  diagrams for structure and flow. Intent prose MAY say "because" —
  the Defence Test binds README, not intend files.
- Cite existing rulings by number (R-, E-, D-, B-) rather than
  restating them; never contradict a ruling silently.
- Every open fork stands in an `OPEN` section at the end, numbered
  o-1, o-2, ..., each stated as a genuine alternative with the cost of
  each branch visible. NEVER write an intend that presupposes an
  unruled answer.
- One law, one place: if a fact is ruled elsewhere, point, don't copy.

## Discussing an intent (the ritual)

1. **Familiarise first.** Read the current dump and relevant WORK /
   RATIONALE / DISCUSSIONS files before saying anything of substance.
   Measurement before assertion: for architectural claims, measure the
   tree (imports, sizes, counts) and present the measurement.
2. **Play back before building.** Restate the ruling precisely, in a
   diagram where structure is involved, and invite correction. List
   the CONSEQUENCES you read out of a ruling so any over-reading can
   be struck.
3. **One question per message.** Present exactly one fork, as an ASCII
   diagram with labelled branches (a)/(b)/..., each branch annotated
   with what it buys and costs.
4. **Recommendation first, one sentence.** Before the diagram, state
   the recommended branch and the single reason, then mark the branch
   `<- recommended` in the diagram.
5. **Track the queue.** Forks the user has not answered remain open;
   surface them ("standing open, oldest first: ...") rather than
   letting them silently expire. Never treat silence as consent.
6. **Terse rulings are complete rulings.** A single word or letter
   ("b") closes the fork it answers and nothing else.

## After a ruling

- Record it: the result into RATIONALE (append-only, PROBLEM /
  DECISION / COST / GRAVEYARD), the intend/spec/plan files updated,
  the OPEN item removed or rewritten.
- Deliver changed files; verification is census from clean extraction
  (`adm/census.py` with `compare.main.is_equivalent`), never the
  working tree, never `diff -q`.
- GOOD files are recorded on real infrastructure, never fabricated.

## Style constants

- British spellings throughout all documents.
- Function docstrings use `"""` and START with
  `RETURN: xxx, a something if success` / `yyy, else`; generators use
  indexed, column-aligned `YIELD:` blocks; description AFTER the
  return block.
- `E_` prefix for enums.
- Absence is `None`, never an empty stand-in; absence is data.
