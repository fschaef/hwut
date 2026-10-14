# Feature Reminder: Happy Constraints (Comparison Engine)

## Background: happy patterns (already exist)

The HWUT comparison engine already supports **happy patterns**: a pattern
that, if it appears in *both* the nominal (known-good) and the actual
output, makes the comparison succeed at that position regardless of which
alternative matched on each side.

    Happy pattern:   "hello|hallo|bonjour"
    Effect:          nominal "hello" is equivalent to actual "bonjour"

The alternatives are treated as interchangeable. A match on any branch in
the nominal is equivalent to a match on any branch in the actual.


## Proposed feature: happy constraints

A **happy constraint** is a deliberate, computed extension of a happy
pattern. Instead of a fixed set of interchangeable literals, equivalence
at a text position is decided by *evaluating a predicate* over the value
carried by that position.

A constraint is **self-contained**: it constrains only the value of its own
element. It cannot reference any other element's value. (Relating two values
to each other is the test author's job, done in the test application's own
code — not in the comparison engine.) This keeps a constraint a pure,
stateless, per-element check, exactly like `NUMERIC` or `EQUIVALENCE_PATTERN`.

### Text element form

A text element subject to happy-constraint consideration has the form:

    (<name>: <value>)

Example occurrences in actual output:

    (integration_steps: 212341)
    (temperature: 37.4)
    (label: "UPPER")

### Value typing

`<value>` is **either a number or a quoted string — nothing else.**

- A numeric literal becomes `int` or `float` (Python literal form).
- A quoted literal becomes `str`.
- No bare words, no lists, no expressions, no other Python literals.

This restriction is deliberate: because a value can only be a number or a
quoted string, the closing `)` of the element is **never** ambiguous. A
`)` inside a quoted string is part of the string; a `)` outside quotes ends
the element. The lexer can therefore recognise `(<name>: <value>)` with a
single, well-defined rule (see implementation hints). Parse the value with
`ast.literal_eval` after isolating it, and reject anything that is not an
`int`, `float`, or `str`.

### Constraint definition

Constraints are defined in the same section where happy patterns are
defined, under a `HAPPY-CONSTRAINTS:` heading. Each constraint binds a
`<name>` to a Python predicate over the single free variable `<name>`. The
predicate must evaluate to a `bool`.

    HAPPY-CONSTRAINTS: integration_steps: integration_steps % 2 == 1 and integration_steps < 30000
    HAPPY-CONSTRAINTS: depth:             10 < depth < 500
    HAPPY-CONSTRAINTS: label:             label[3] == "upper"

The only name a predicate may reference is the `<name>` it is attached to.
A predicate referencing any other name is a **definition-time error**.

The mapping is `<name>` to predicate. If several conditions apply to one
`<name>`, combine them in the one predicate with `and` (as in the
`integration_steps` example) rather than across several definitions.


## Evaluation semantics

There is **no namespace and no rewrite.** When the comparison reaches a
constraint element, it checks that element in place against the predicate
registered for its `<name>`, and — if satisfied — continues. This mirrors
how `LineElementNumber.compare()` decides equivalence locally.

Given an actual-output element `(integration_steps: 212341)` and the
definition:

    HAPPY-CONSTRAINTS: integration_steps: integration_steps % 2 == 1 and integration_steps < 30000

the engine, on reaching that position:

1. Reads the element's name (`integration_steps`) and value (`212341`).
2. Looks up the predicate registered for that name.
3. Evaluates the predicate with its single variable bound to the value.
4. Predicate holds  -> the position is **equivalent**; comparison continues.
   Predicate fails  -> the position is **not equivalent**.

In short: a constraint element is equivalent **iff its own value satisfies
its own predicate**. Subject and nominal are compared position by position
as today; the constraint replaces the literal text match at that one
position with a predicate evaluation.

### Name agreement between subject and nominal

A constraint position pairs with the corresponding position on the other
side. The two must carry the **same `<name>`**; differing names at paired
positions is a normal `MISFIT`/`DIFFERENT`, just as differing tolerance
types are today. The values need not be equal — each side's value must
satisfy the predicate.

### Marking a difference

When a constraint is not satisfied, the diff marks the mismatch as:

    actual:    (<name> NEQ <original value>)
    nominal:   (<name>: <original value>)

so the failing position is legible against the unchanged nominal form.

### Refusing an invalid nominal

A nominal output whose own constraint value violates the constraint must
**not** be accepted by the HWUT engine. A nominal that cannot itself pass
its predicate can never serve as a valid reference. This is a valid reason
to throw an exception at parse time — an unacceptable nominal is rejected
outright rather than silently producing a passing or failing comparison.


## Parser: Python AST

The predicate language **is** Python expression syntax. Each predicate is
parsed with `ast.parse(expr, mode="eval")` and validated by walking the
AST:

- Only an allow-listed set of node types is accepted: comparisons, boolean
  ops, the single bound `<name>`, literals, subscripts, arithmetic, and
  calls to **built-in** functions only. No attribute access, no imports,
  no arbitrary calls.
- The only `Name` permitted is the constraint's own `<name>`. Any other
  free name is a definition-time error (this is what enforces
  "self-contained").
- The expression must **evaluate to a `bool`**; this is checked on the
  result at evaluation time, not statically.

Helper functions are limited to Python's **built-ins**; no custom helper
registry. For example `odd(...)` is not a built-in — write
`integration_steps % 2 == 1` instead.

Evaluation happens against a restricted namespace containing only the one
bound variable (and the permitted built-ins).

## Error handling

Errors collapse onto the two outcomes already defined — there is no third
"error" state surfaced to the user:

- A **syntax error** or **execution error** (type error, failed built-in
  call, non-boolean result) while evaluating against the **actual** output
  translates directly to **not equivalent**.
- The same failure while validating the **nominal** output translates to
  **unacceptable as nominal**, i.e. the parse-time exception that rejects
  the nominal.

Note: predicate *syntax* errors and the *unknown-name* error are caught
once at definition-compile time, so they surface before any comparison
runs. Only value-dependent runtime errors can occur during comparison.


## What this design deliberately avoids

Dropping cross-references between constraint elements removes:

- any **shared namespace** threaded through the comparison;
- any dependence on **line order** ("which value was bound first");
- any **potpourri special case** — because a self-contained predicate is
  order-independent, it works identically inside a `||||` region and a
  line sequence, with no CSP-style permutation search.

A constraint is therefore a stateless, local, per-element tolerance.
