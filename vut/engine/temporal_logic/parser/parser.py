"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE PARSER

Consumes the Lexer token stream and builds the AST (ast_nodes). The parser is
context-aware: it knows, at each '{', which Luau Role applies and passes it to
the lexer's read_luau_block -- CONDITION for a guard, EXPRESSION for an rvalue,
STATEMENT_BLOCK for a '=>'/init/deinit body. The lexer never guesses.

ERROR MODEL:

    On a grammar violation the parser reports a PARSER-phase Diagnostic and
    RESYNCS: it discards tokens up to the next safe anchor -- the keyword 'off'
    (consumed) or a top-level keyword (on/mode/state_machine/event/clock, left
    in place to start the next construct). One resync tier only; constructs
    below that boundary abort rather than attempt finer recovery. This bounds
    cascade errors: one malformed rule does not blind the parser to the rest.

    Lexer diagnostics (MISMATCH, malformed Luau) are already in the reporter;
    the parser treats a MISMATCH token as a resync trigger. The parse always
    runs to end-of-file so every construct is attempted; the caller checks the
    reporter at the phase boundary.
______________________________________________________________________________
"""
from typing import List

from   .lexer                                       import Lexer, E_Token, Token
from   .diagnostic                                  import Diagnostic, Phase, DiagnosticReporter
import vut.engine.temporal_logic.parser.ast_nodes   as ast
from   vut.engine.temporal_logic.luau.luau_fragment import Role


# Keywords that may start a top-level construct -- resync anchors.
_TOP_LEVEL = {
    E_Token.KW_ON, E_Token.KW_MODE, E_Token.KW_SM,
    E_Token.KW_EVENT, E_Token.KW_CLOCK,
}

# Trigger keywords usable where an event name is expected in a <cause>.
_TRIGGER_KW = {
    E_Token.KW_ANY, E_Token.KW_BEGIN, E_Token.KW_END, E_Token.KW_SWITCHED,
}


class _ResyncError(Exception):
    """Internal control-flow signal: abandon the current construct and resync.

    Never escapes the parser. Raised by the expectation helpers when the token
    stream does not match the grammar, caught at the top-level loop which then
    skips to the next anchor.
    """
    pass


class Parser:
    """Builds a RuleFile AST from a rule-file text via a pull-driven Lexer.

    One-token lookahead in 'self.tok'. 'parse()' is the entry point. All
    grammar methods consume from the lexer and append to the AST; on mismatch
    they raise _ResyncError, handled centrally.
    """
    def __init__(self, source_text: str, oracle, reporter: DiagnosticReporter):
        """RETURN: None. Wires a Lexer over 'source_text' and primes lookahead."""
        self.reporter = reporter
        self.lexer    = Lexer(source_text, oracle, reporter)
        self.tok      = self.lexer.next()

    # -- token plumbing -----------------------------------------------------

    def _advance(self) -> Token:
        """RETURN: Token, the current token; then loads the next into lookahead.

        A MISMATCH in the stream is a lexer-reported error; surfacing it here as
        a resync keeps the parser from building on garbage.
        """
        current  = self.tok
        self.tok = self.lexer.next()
        return current

    def _at(self, *kinds) -> bool:
        """RETURN: True,  if the lookahead token is one of 'kinds'.
                  False, else.
        """
        return self.tok.kind in kinds

    def _expect(self, kind: E_Token) -> Token:
        """
        RETURN: Token, the consumed token of kind 'kind'.

        Reports a PARSER diagnostic and raises _ResyncError if the lookahead is
        not 'kind'. The message names what was expected and what was found.
        """
        if self.tok.kind != kind:
            self._error("expected %s, found %s"
                        % (kind.name, self.tok.kind.name))
            raise _ResyncError()
        return self._advance()

    def _error(self, message: str, fatal: bool = False):
        """RETURN: None. Appends a PARSER-phase Diagnostic at the lookahead."""
        self.reporter.report(Diagnostic(
            phase         = Phase.PARSER,
            message       = message,
            source_offset = self.tok.begin,
            fatal         = fatal,
        ))

    def _resync(self):
        """RETURN: None. Skips tokens to the next anchor after an error.

        Consumes through and including the next 'off'; or stops with a
        top-level keyword as the lookahead so it begins the next construct; or
        reaches END_OF_FILE. Leaves the parser ready to attempt the next item.
        """
        while True:
            if self._at(E_Token.END_OF_FILE):
                return
            if self._at(E_Token.KW_OFF):
                self._advance()
                return
            if self.tok.kind in _TOP_LEVEL:
                return
            self._advance()

    # -- entry point --------------------------------------------------------

    def parse(self) -> ast.RuleFile:
        """
        RETURN: RuleFile, the assembled AST (possibly partial on errors).

        Loops over top-level constructs to end-of-file. Each construct is
        attempted independently; a _ResyncError from any one triggers a resync
        and the loop continues, so all fixable errors accumulate in one pass.
        """
        rule_file = ast.RuleFile()
        while not self._at(E_Token.END_OF_FILE):
            try:
                item = self._top_level_item()
                if item is not None:
                    rule_file.items.append(item)
            except _ResyncError:
                self._resync()
        return rule_file

    def _top_level_item(self):
        """
        RETURN: node, one top-level construct, or None to skip a stray token.

        Dispatches on the leading keyword. An unexpected leading token is
        reported and raises _ResyncError so the loop recovers.
        """
        if self._at(E_Token.KW_ON):
            return self._causality()
        if self._at(E_Token.KW_MODE):
            return self._mode()
        if self._at(E_Token.KW_SM):
            return self._state_machine()
        if self._at(E_Token.KW_EVENT):
            return self._event_def()
        if self._at(E_Token.KW_CLOCK):
            return self._clock_def()
        if self._at(E_Token.MISMATCH):
            # Already reported by the lexer; just recover.
            raise _ResyncError()
        self._error("expected a top-level construct, found %s"
                    % self.tok.kind.name)
        raise _ResyncError()

    # -- causality ----------------------------------------------------------

    def _causality(self) -> ast.Causality:
        """
        RETURN: Causality, a parsed 'on <cause> (=> <effect>)+ off' rule.

        Requires at least one effect; reports and resyncs if 'off' arrives
        before any effect, or if the closing 'off' is missing.
        """
        begin = self._expect(E_Token.KW_ON).begin
        cause = self._cause()

        effects = []
        while self._at(E_Token.ARROW):
            self._advance()
            effects.append(self._effect())

        if not effects:
            self._error("causality has no '=>' effect before 'off'")
            raise _ResyncError()

        self._expect(E_Token.KW_OFF)
        return ast.Causality(cause=cause, effects=effects, begin=begin)

    def _cause(self) -> ast.Cause:
        """RETURN: Cause, a trigger with an optional '& <guard>'."""
        trigger = self._trigger()
        guard   = None
        if self._at(E_Token.AND):
            self._advance()
            guard = self._luau_block(Role.CONDITION, "guard")
        return ast.Cause(trigger=trigger, guard=guard, begin=trigger.begin)

    def _trigger(self) -> ast.Trigger:
        """
        RETURN: Trigger, an event-name identifier or an implicit keyword.

        Accepts ID or one of ANY/BEGIN/END/switched. Anything else is reported
        and resyncs.
        """
        if self._at(E_Token.ID):
            t = self._advance()
            return ast.Trigger(name=t.text, is_keyword=False, begin=t.begin)
        if self.tok.kind in _TRIGGER_KW:
            t = self._advance()
            return ast.Trigger(name=t.text, is_keyword=True, begin=t.begin)
        self._error("expected a trigger (event name, ANY, BEGIN, END, "
                    "switched), found %s" % self.tok.kind.name)
        raise _ResyncError()

    def _effect(self):
        """
        RETURN: node, one effect: EventSpec, ModeArming, ReportString, Mutation.

        Distinguishes by lookahead: '{' -> Mutation (STATEMENT_BLOCK), '+' ->
        ModeArming, STRING -> ReportString, ID -> EventSpec.
        """
        if self._at(E_Token.LUAU_OPEN):
            body = self._luau_block(Role.STATEMENT_BLOCK, "mutation")
            return ast.Mutation(body=body, begin=body.begin)
        if self._at(E_Token.PLUS):
            begin = self._advance().begin
            name  = self._dotted_name()
            args  = self._paren_args()
            return ast.ModeArming(name=name, args=args, begin=begin)
        if self._at(E_Token.STRING):
            t = self._advance()
            return ast.ReportString(text=t.text, begin=t.begin)
        if self._at(E_Token.ID):
            begin = self.tok.begin
            name  = self._dotted_name()
            args  = self._paren_args()
            return ast.EventSpec(name=name, args=args, begin=begin)
        self._error("expected an effect (event, '+' mode-arming, string, or "
                    "'{ }' mutation), found %s" % self.tok.kind.name)
        raise _ResyncError()

    # -- arguments ----------------------------------------------------------

    def _paren_args(self) -> List[ast.Arg]:
        """
        RETURN: list, the Args inside '( ... )'; empty list for '()'.

        Requires the opening '('. Parses comma-separated args until ')'.
        """
        self._expect(E_Token.LPAREN)
        args = []
        if self._at(E_Token.RPAREN):
            self._advance()
            return args
        args.append(self._arg())
        while self._at(E_Token.COMMA):
            self._advance()
            args.append(self._arg())
        self._expect(E_Token.RPAREN)
        return args

    def _arg(self) -> ast.Arg:
        """
        RETURN: Arg, one '[member =] rvalue' argument.

        A leading 'ID =' names the member; otherwise the arg is positional. The
        rvalue is a NUMBER, STRING, or an EXPRESSION Luau span.
        """
        member = None
        begin  = self.tok.begin
        if self._at(E_Token.ID):
            # Peek for '=' to decide member vs positional bare-ID rvalue.
            ident = self._advance()
            if self._at(E_Token.EQUAL):
                self._advance()
                member = ident.text
            else:
                # Bare identifier rvalue is not in the grammar; report.
                self._error("expected '=' after member name '%s' or a literal "
                            "rvalue" % ident.text)
                raise _ResyncError()
        value, is_luau = self._rvalue()
        return ast.Arg(member=member, value=value, is_luau=is_luau, begin=begin)

    def _rvalue(self):
        """
        RETURN: (value, is_luau), the rvalue and whether it is a Luau span.

        NUMBER/STRING return their lexeme text with is_luau False; '{' returns
        an EXPRESSION Luau node with is_luau True.
        """
        if self._at(E_Token.NUMBER) or self._at(E_Token.STRING):
            return self._advance().text, False
        if self._at(E_Token.LUAU_OPEN):
            return self._luau_block(Role.EXPRESSION, "rvalue"), True
        self._error("expected an rvalue (number, string, or '{ }' expression), "
                    "found %s" % self.tok.kind.name)
        raise _ResyncError()

    # -- mode ---------------------------------------------------------------

    def _mode(self) -> ast.Mode:
        """
        RETURN: Mode, a parsed mode with members and 'until' causes.

        Parses the signature, then members (causalities, one init, one deinit)
        until 'until' begins the closing cause list. Duplicate init/deinit is a
        validator concern; the parser keeps the last and does not reject here.
        """
        begin  = self._expect(E_Token.KW_MODE).begin
        name   = self._dotted_name()
        params = self._opt_param_list()
        self._expect(E_Token.COLON)

        init = deinit = None
        causalities: List[ast.Causality] = []
        while not self._at(E_Token.KW_UNTIL):
            if self._at(E_Token.KW_INIT):
                init = self._init_deinit_body()
            elif self._at(E_Token.KW_DEINIT):
                deinit = self._init_deinit_body()
            elif self._at(E_Token.KW_ON):
                causalities.append(self._causality())
            else:
                self._error("expected mode element (on/init/deinit) or "
                            "'until', found %s" % self.tok.kind.name)
                raise _ResyncError()

        untils = self._until_list()
        return ast.Mode(name=name, params=params, init=init, deinit=deinit,
                        causalities=causalities, untils=untils, begin=begin)

    def _init_deinit_body(self) -> ast.Luau:
        """RETURN: Luau, the STATEMENT_BLOCK body after 'init'/'deinit'."""
        self._advance()                      # consume init/deinit keyword
        return self._luau_block(Role.STATEMENT_BLOCK, "init/deinit body")

    # -- state machine ------------------------------------------------------

    def _state_machine(self) -> ast.StateMachine:
        """
        RETURN: StateMachine, a parsed state machine with its elements.

        Parses the signature then elements: at most one 'default =', one init,
        one deinit (multiplicity enforced by the validator), then the mandatory
        'until' list.
        """
        begin  = self._expect(E_Token.KW_SM).begin
        name   = self._dotted_name()
        params = self._opt_param_list()
        self._expect(E_Token.COLON)

        default = None
        init = deinit = None
        while not self._at(E_Token.KW_UNTIL):
            if self._at(E_Token.KW_DEFAULT):
                default = self._default_clause()
            elif self._at(E_Token.KW_INIT):
                init = self._init_deinit_body()
            elif self._at(E_Token.KW_DEINIT):
                deinit = self._init_deinit_body()
            else:
                self._error("expected state-machine element "
                            "(default/init/deinit) or 'until', found %s"
                            % self.tok.kind.name)
                raise _ResyncError()

        untils = self._until_list()
        return ast.StateMachine(name=name, params=params, default=default,
                                init=init, deinit=deinit, untils=untils,
                                begin=begin)

    def _default_clause(self) -> ast.StateMachineModeRef:
        """RETURN: StateMachineModeRef, the 'default = SM.member|VOID' target."""
        begin = self._expect(E_Token.KW_DEFAULT).begin
        self._expect(E_Token.EQUAL)
        sm_name = self._expect(E_Token.ID).text
        self._expect(E_Token.DOT)
        if self._at(E_Token.KW_VOID):
            self._advance()
            return ast.StateMachineModeRef(sm_name=sm_name, mode_name="VOID",
                                           is_void=True, begin=begin)
        member = self._expect(E_Token.ID).text
        return ast.StateMachineModeRef(sm_name=sm_name, mode_name=member,
                                       is_void=False, begin=begin)

    # -- shared sub-rules ---------------------------------------------------

    def _until_list(self) -> List[ast.Cause]:
        """
        RETURN: list, the one-or-more causes of the closing 'until' clauses.

        Each 'until' is followed by a cause. Requires at least one; the grammar
        makes the until list mandatory for modes and state machines.
        """
        untils = [self._one_until()]
        while self._at(E_Token.KW_UNTIL):
            untils.append(self._one_until())
        return untils

    def _one_until(self) -> ast.Cause:
        """RETURN: Cause, the cause following a single 'until' keyword."""
        self._expect(E_Token.KW_UNTIL)
        return self._cause()

    def _event_def(self) -> ast.EventDef:
        """RETURN: EventDef, a parsed 'event name(arg-decls)'."""
        begin = self._expect(E_Token.KW_EVENT).begin
        name  = self._expect(E_Token.ID).text
        params = self._param_list()
        return ast.EventDef(name=name, params=params, begin=begin)

    def _clock_def(self) -> ast.ClockDef:
        """RETURN: ClockDef, a parsed 'clock event-name number'."""
        begin  = self._expect(E_Token.KW_CLOCK).begin
        name   = self._expect(E_Token.ID).text
        period = self._expect(E_Token.NUMBER).text
        return ast.ClockDef(name=name, period=period, begin=begin)

    def _opt_param_list(self) -> List[ast.ArgDecl]:
        """RETURN: list, the parameter declarations, or empty if no '(' follows."""
        if self._at(E_Token.LPAREN):
            return self._param_list()
        return []

    def _param_list(self) -> List[ast.ArgDecl]:
        """
        RETURN: list, the 'member : type' declarations inside '( ... )'.

        Requires '('. Declarations are separated by ';'. Empty parens yield an
        empty list.
        """
        self._expect(E_Token.LPAREN)
        decls = []
        if self._at(E_Token.RPAREN):
            self._advance()
            return decls
        decls.append(self._arg_decl())
        while self._at(E_Token.SEMI):
            self._advance()
            decls.append(self._arg_decl())
        self._expect(E_Token.RPAREN)
        return decls

    def _arg_decl(self) -> ast.ArgDecl:
        """RETURN: ArgDecl, one 'member : type' declaration."""
        member = self._expect(E_Token.ID)
        self._expect(E_Token.COLON)
        type_id = self._expect(E_Token.ID)
        return ast.ArgDecl(member=member.text, type=type_id.text,
                           begin=member.begin)

    def _dotted_name(self) -> str:
        """
        RETURN: str, a possibly-dotted name reassembled from ID (DOT ID)*.

        The lexer emits '.' as DOT; this rejoins 'SM.MEMBER' into one string for
        the AST. Requires a leading ID.
        """
        parts = [self._expect(E_Token.ID).text]
        while self._at(E_Token.DOT):
            self._advance()
            parts.append(self._expect(E_Token.ID).text)
        return ".".join(parts)

    def _luau_block(self, role: Role, what: str) -> ast.Luau:
        """
        RETURN: Luau, the span for the '{' at the lookahead under 'role'.

        Requires a LUAU_OPEN at the lookahead, then drives the lexer's
        read_luau_block with the parser-chosen 'role'. A None return (oracle
        infrastructure failure) is reported fatal and resyncs. 'what' names the
        context for diagnostics.
        """
        open_tok = self._expect(E_Token.LUAU_OPEN)
        block    = self.lexer.read_luau_block(open_tok, role)
        if block is None:
            self._error("Luau oracle failed reading %s" % what, fatal=True)
            raise _ResyncError()
        # Reload lookahead: read_luau_block advanced the lexer cursor directly.
        self.tok = self.lexer.next()
        return ast.Luau(text=block.text, role=role, begin=block.begin)


def parse(source_text: str, oracle, reporter: DiagnosticReporter) -> ast.RuleFile:
    """
    RETURN: RuleFile, the AST for 'source_text' (possibly partial on errors).

    Convenience entry point: constructs a Parser and runs it. Diagnostics
    accumulate in 'reporter'; inspect it (or call abort_if_fatal) at the phase
    boundary.
    """
    return Parser(source_text, oracle, reporter).parse()
