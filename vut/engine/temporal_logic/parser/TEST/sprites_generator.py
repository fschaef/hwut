#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

NOT A TEST. Generates the 'sprites' menagerie rule file -- a large, structured
exercise of the full rule-file grammar surface in one source text.

The hand-authored monkey_data/sprites.rule-git-ignored used to carry this by
hand. It is a TEST INPUT, never a GOOD file, so it does not belong in version
control; monkey-fuzz.py regenerates it on demand (see generate()) and only reads
the on-disk copy as a cache when present. The GOOD oracle is the AST census in
monkey-fuzz.py--sprites.txt, NOT this text.

DETERMINISM: the emitted text is a pure function of the seed. DeterministicStream
is MINSTD (platform-independent), and every count/name here is drawn from it in a
fixed order, so 'generate(seed)' yields byte-identical output on every run and
every platform. Change the seed (or this code) and the census GOOD must be
re-promoted -- that is the intended single global change, not a per-line edit.

SURFACE COVERAGE (the reason sprites exists): the generator deliberately emits
every top-level construct the grammar admits, so the file is a canary for whole
classes of regression that the random-walk profiles can miss:

  - import: / into:                (mounts, recorded not resolved)
  - event: / clock:                (definitions)
  - declaration 'X is: mode'       <-- the kind keywords ('mode', 'state') in
    and         'X is: state'          their CAPTURED kind-decl position, the
                                       construct that catches keyword-tier
                                       regressions against 'mode:' / 'state:'.
  - open: / :close                 (namespaces, nested)
  - state_machine: / state:        (exclusive behaviour, default:)
  - mode_group: / mode:            (concurrent behaviour, has:)
  - on: <cause> => <effect>+       (top-level causality: mutation, spawn,
                                    unspawn, mode-arming, report-string,
                                    event-spec, name-dotted args through the
                                    'e'/'sm'/'mg'/'m' pseudo-symbols)
______________________________________________________________________________
"""
from vut.language_support.python.deterministic_random import DeterministicStream


# Fixed vocabulary. Names are drawn from these in a stream-determined order; the
# pools are intentionally larger than any single walk needs so the choice has
# room to spread without exhausting the pool.
_CATEGORIES = ("moving", "plants", "undead", "villains", "rules", "sea")

_CREATURES = (
    "Knight", "Archer", "Wizard", "Goblin", "Troll", "Wraith", "Lich",
    "Ghoul", "Bandit", "Ogre", "Sprite", "Pixie", "Dryad", "Treant",
    "Kraken", "Siren", "Eel", "Crab", "Beetle", "Wasp", "Moth", "Spider",
    "Wolf", "Bear", "Boar", "Stag", "Hawk", "Raven", "Serpent", "Drake",
)

_MODE_NAMES = (
    "Idle", "Charge", "Flee", "Hunt", "Guard", "Patrol", "Rest", "Lurk",
    "Stalk", "Ambush", "Retreat", "Rally", "Forage", "Roost", "Submerge",
)

_EVENTS = (
    "Tick", "SeesPlayer", "NoiseHeard", "SeesPrey", "PreyEscaped",
    "EnemyInRange", "ArrowIncoming", "BladeClash", "Spooked", "Splash",
    "RainFell", "SunRose", "Cornered", "Wounded", "WhipCracked",
)

_MEMBER_TYPES = ("int", "string")

# The opaque Luau bodies the generator splices verbatim into condition / mutation
# / lvalue positions. They are opaque to the parser (balance is all that matters),
# so a small fixed set keeps the text legible and the Luau census stable.
_LUAU_COND   = ("{ self.hp > 0 }", "{ self.fear < 5 }", "{ self.range <= 10 }")
_LUAU_STMTS  = ("{ self.hp = self.hp - 1 }", "{ self.pos = self.pos:step() }",
                "{ self.alert = true }")
_LUAU_LVALUE = ("{ db.slot }", "{ db.pool }")


class _Emit:
    """Accumulates rule-file lines, drawing every choice from one stream.

    The single stream threaded through every method is what makes the whole file
    a pure function of the seed: each name, count and branch is the next draw, in
    a fixed visitation order.
    """
    def __init__(self, stream):
        """RETURN: None. Binds the deterministic stream and an empty line buffer."""
        self.s     = stream
        self.lines = []
        self._uid  = 0

    def text(self):
        """RETURN: str, the assembled rule-file source (newline-terminated)."""
        return "\n".join(self.lines).strip() + "\n"

    def _uid_suffix(self):
        """RETURN: int, a fresh suffix so generated names stay distinct."""
        self._uid += 1
        return self._uid

    def _name(self, pool):
        """RETURN: str, a stream-chosen base name from 'pool' plus a fresh suffix.

        The suffix keeps every emitted name unique across the file (two 'Knight's
        from the same pool become 'Knight7' and 'Knight12'), so name collisions
        never perturb the AST census.
        """
        return "%s%d" % (self.s.select(pool), self._uid_suffix())

    def comment(self, text):
        """RETURN: None. Appends a '##' banner comment line."""
        self.lines.append("")
        self.lines.append("## " + "=" * 70)
        self.lines.append("## " + text)
        self.lines.append("## " + "=" * 70)

    def blank(self):
        """RETURN: None. Appends one blank line for legibility."""
        self.lines.append("")

    # -- leaf constructs -----------------------------------------------------
    def event_defs(self, count):
        """RETURN: None. Emits 'count' 'event: Name(member: type)' definitions."""
        for _ in range(count):
            member = self.s.select(("fear", "depth", "range", "weight", "amount"))
            typ    = self.s.select(_MEMBER_TYPES)
            self.lines.append("event: %s(%s: %s)"
                              % (self._name(_EVENTS), member, typ))

    def clock_defs(self, count):
        """RETURN: None. Emits 'count' 'clock: Name period' definitions."""
        for _ in range(count):
            period = self.s.next_int(1, 200)
            self.lines.append("clock: %s %d" % (self._name(_EVENTS), period))

    def forward_decls(self, count):
        """RETURN: None. Emits 'count' 'Name is: mode' / 'Name is: state' decls.

        This is the surface where the bare kind keywords stand in their
        captured kind-decl position, one lexer tier below their trailing-colon
        definition spellings ('mode:' / 'state:'). Emitting both kinds every
        run keeps sprites the canary for keyword-tier regressions -- the
        random-walk profiles do not reliably reach it.
        """
        for _ in range(count):
            kind = self.s.select(("mode", "state"))
            self.lines.append("%s is: %s" % (self._name(_CREATURES), kind))

    # -- causality -----------------------------------------------------------
    def _effect(self):
        """RETURN: str, one '<effect>' body (no leading '=>').

        Spreads across the effect alternatives so a run exercises mutation,
        spawn, unspawn, mode-arming, report-string and event-spec.
        """
        which = self.s.next_int(0, 5)
        if which == 0:                                   # mutation
            return self.s.select(_LUAU_STMTS)
        if which == 1:                                   # mode-arming
            return "! %s(%s)" % (self.s.select(_MODE_NAMES), self._arg_list())
        if which == 2:                                   # event-spec
            return "%s(%s)" % (self.s.select(_EVENTS), self._arg_list())
        if which == 3:                                   # report-string
            return '"%s reacts"' % self.s.select(_CREATURES)
        if which == 4:                                   # spawn
            return "+! %s(%s) in: %s" % (self.s.select(_CREATURES),
                                         self._arg_list(),
                                         self.s.select(_CATEGORIES))
        return "-! %s" % self.s.select(_CREATURES)       # unspawn

    def _arg_list(self):
        """RETURN: str, zero-or-more comma-separated <arg>s (possibly empty).

        An <arg> is '<rvalue>' or 'id = <rvalue>'. The emitter keeps the
        positional slot to a bare name and puts every richer form -- number /
        string literal, a pseudo-symbol member ('e.x' / 'sm.x' / 'mg.x' /
        'm.x', plain name-dotted references resolved in pass 2), or another
        identifier -- in the RVALUE after '=', so both shapes and the
        pseudo-symbol spellings are exercised on every run.
        """
        n = self.s.next_int(0, 3)
        if n == 0:
            return ""
        parts = []
        for _ in range(n):
            name = self.s.select(("speed", "power", "level", "rate", "depth"))
            if self.s.coin(0.4):
                parts.append(name)                       # bare-id positional
                continue
            kind = self.s.next_int(0, 3)
            if kind == 0:
                rvalue = str(self.s.next_int(0, 99))                  # number
            elif kind == 1:
                rvalue = '"%s"' % self.s.select(_MODE_NAMES)         # string
            elif kind == 2:
                binding = self.s.select(("e", "sm", "mg", "m"))
                member  = self.s.select(("x", "fear", "depth", "pos"))
                rvalue  = "%s.%s" % (binding, member)        # pseudo-symbol member
            else:
                rvalue = self.s.select(("fast", "slow", "loud"))    # id
            parts.append("%s = %s" % (name, rvalue))
        return ", ".join(parts)

    def causality(self, indent=""):
        """RETURN: None. Emits one 'on: <cause> => <effect> [=> <effect>]*' rule.

        The cause is a trigger with an optional guard; one-or-more effects follow,
        each on its own continuation line for legibility.
        """
        trigger = self.s.select(_EVENTS)
        guard   = (" & " + self.s.select(_LUAU_COND)
                   if self.s.coin(0.4) else "")
        self.lines.append("%son: %s%s" % (indent, trigger, guard))
        for _ in range(self.s.next_int(1, 3)):
            self.lines.append("%s        => %s" % (indent, self._effect()))

    # -- aggregates ----------------------------------------------------------
    def state_machine(self):
        """RETURN: None. Emits a 'state_machine:' with a default and 2-4 states."""
        name = self._name(_CREATURES)
        self.lines.append("state_machine: %s(rate: string)" % name)
        states = [self._name(_MODE_NAMES) for _ in range(self.s.next_int(2, 4))]
        self.lines.append("    default: %s.%s" % (name, states[0]))
        for st in states:
            self.blank()
            self.lines.append("    state: %s" % st)
            self.lines.append("        init: %s" % self.s.select(_LUAU_STMTS))
            self.causality(indent="        ")
            self.lines.append("        until: %s" % self.s.select(_EVENTS))
        self.lines.append(":end")

    def mode_group(self):
        """RETURN: None. Emits a 'mode_group:' with a has-ref and 2-3 modes."""
        name = self._name(_CREATURES)
        self.lines.append("mode_group: %s" % name)
        self.lines.append("    has: %s.%s"
                          % (self.s.select(_CREATURES), self.s.select(("x", "y"))))
        for _ in range(self.s.next_int(2, 3)):
            self.blank()
            self.lines.append("    mode: %s" % self._name(_MODE_NAMES))
            self.lines.append("        init: %s" % self.s.select(_LUAU_STMTS))
            self.causality(indent="        ")
            self.lines.append("        until: %s" % self.s.select(_EVENTS))
        self.lines.append(":end")


def generate(seed=0x5197):
    """RETURN: str, the deterministically generated sprites menagerie source.

    The output is byte-identical for a given seed on every platform (MINSTD
    stream). The file mounts each category as a namespace and fills it with a mix
    of aggregates and top-level causality rules, after a shared preamble of event
    / clock / forward-decl vocabulary. See module docstring for the surface the
    generator guarantees to emit.
    """
    s = DeterministicStream(seed)
    e = _Emit(s)

    e.comment("menagerie -- ROOT: shared vocabulary, then every category")
    e.blank()
    for cat in _CATEGORIES:
        e.lines.append('import: "sprites_%s.rule" into: menagerie.%s' % (cat, cat))

    e.comment("shared event, clock and forward-decl vocabulary")
    e.blank()
    e.event_defs(s.next_int(12, 18))
    e.blank()
    e.clock_defs(s.next_int(2, 4))
    e.blank()
    e.forward_decls(s.next_int(4, 8))

    for cat in _CATEGORIES:
        e.comment("category: %s" % cat)
        e.lines.append("open: menagerie.%s" % cat)
        for _ in range(s.next_int(2, 4)):
            e.blank()
            shape = s.next_int(0, 2)
            if shape == 0:
                e.state_machine()
            elif shape == 1:
                e.mode_group()
            else:
                e.causality()
        e.lines.append(":close")

    return e.text()


if __name__ == "__main__":
    import sys
    sys.stdout.write(generate())
