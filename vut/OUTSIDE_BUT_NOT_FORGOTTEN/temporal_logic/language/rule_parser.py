"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE PARSER -- the facade binding the reactive-engine rule language (the
                    OUTER "language" layer) to the grammar-agnostic core engine.

The seam between "this specific language" and "the general machinery":

  language/ (this layer)  grammar.py   the GRAMMAR dict + terminal bindings + the
                          rule_parser  this facade

  core/ (general)         a grammar-agnostic LL(2) engine, lexer, CST node tree,
                          terminal factory, diagnostics -- knows nothing of the
                          rule language; it is PARAMETERISED by the grammar.

The facade does three things, once: register the grammar's string keywords with
the core lexer (so its token spec can be generated), compile GRAMMAR into a
validated Grammar (LL(2) + role vocabulary checked at load), and expose parse().
A different language supplies its own grammar.py and facade, reusing core
unchanged (the three-file outer-layer contract, CARRY-OVER-HARVEST item 1).

PASS-1 SCOPE. This is the language-binding SKELETON. parse() runs the engine in
pure-CST mode and returns the canonical CST -- a STAR_Node("<file>") of the
parsed top-level items. The typed-AST overlay (an ast_map rule->constructor
table over ast_nodes) and the module-spine wrapper (SourceModule -> ParsedModule)
are LATER passes; this facade deliberately stops at the CST so the grammar and
its core binding can be tested in isolation first (settle-before-code).
______________________________________________________________________________
"""
from ..core.parser_generator.ll2_engine import Grammar, EngineParser
from ..core.diagnostic import DiagnosticReporter
from ..core.lexer.lexer import register_grammar

from .grammar import GRAMMAR
from .ast_map import load_ast_map, make_module_root
from .module_states import SourceModule, ParsedModule


# Compiled once, on first use -- see compiled_grammar(). Module import has no
# side effects (CARRY-OVER-HARVEST item 2): importing this facade neither lexes,
# compiles, nor mutates the core lexer's registered-grammar state.
_COMPILED = None


def parse(source_text, reporter: DiagnosticReporter):
    """RETURN: STAR_Node, the CST of 'source_text' -- a "<file>" node whose items
              are the parsed top-level constructs, if parsing reached end-of-file.
              A PARTIAL "<file>" node, if the parser recovered from one or more
              errors: the recovered items are present and every fault is recorded
              in 'reporter' (reporter.has_fatal() then answers whether a later
              phase may proceed).

    Diagnostics accumulate in 'reporter'; parsing never raises on a malformed
    input -- it collects-and-continues, so one call reports every fixable fault.
    The returned node is always the finalised file node (see finalize_file), so
    the file shape is identical whether parse() or a direct EngineParser driver
    produced it.
    """
    file_node = EngineParser(source_text, reporter, compiled_grammar()).parse()
    return finalize_file(file_node)


def parse_module(source: SourceModule, reporter: DiagnosticReporter) -> ParsedModule:
    """RETURN: ParsedModule, the next module state -- the finalised "<file>" CST
              of the text behind 'source.path' with 'source' carried as its
              provenance, if the path could be read.
              Raises OSError, else (an unreadable path is a LOAD fault, not a
              parse diagnostic: there is no source position to point at).

    The module-spine 'parse' transition (module_states): reads the text through
    'source.path', parses it via parse() above -- so every parse fault is
    collected in 'reporter', never raised -- and discards the text. The text is
    ephemeral by design: a ParsedModule holds the tree and the provenance, not
    the bytes.
    """
    with open(source.path, "r") as fh:
        source_text = fh.read()
    return ParsedModule(origin=source,
                        file_node=parse(source_text, reporter))


def compiled_grammar() -> Grammar:
    """RETURN: Grammar, the compiled and validated rule-file grammar, built once
              on first call and cached for every call thereafter.

    The build registers the grammar's string keywords with the core lexer (so
    the token spec can be generated), compiles GRAMMAR, then loads the AST map
    as the engine's transformers: every rule reduces straight to its typed
    product (three-file contract; no CST leaves this facade). All load-time
    gates fire here, eagerly, at the earliest possible point rather than
    mid-parse: LL2ConflictError if the grammar is not LL(2);
    RoleUniquenessError if one sequence gives two positions the same role
    (D-10: role meaning is rule-scoped; there is no global vocabulary -- a
    misspelled role surfaces at the factory's strict read instead); and
    load_ast_map's coverage gate (LookupError: every rule mapped, no entry
    unaccounted, A-2) plus kind gate (TypeError: a dict route table on OR
    rules, a callable factory on SEQ rules), which normalises the raw map
    into the core family so the engine keeps its ONE transformer seam and
    every factory stays free of runtime isinstance checks. The map is loaded
    AFTER compilation because typing entries requires the compiled rule
    shapes; the engine reads transformers only at reduce time, so the
    post-compile assignment is the natural order, not a workaround.
    Done lazily (not at package import) so importing this facade has no side
    effects and cannot deadlock on a partial initialisation.
    """
    global _COMPILED
    if _COMPILED is None:
        # The engine flattens subspaces internally (D-21); register_grammar and
        # Grammar each flatten what they receive, so GRAMMAR is passed nested.
        register_grammar(GRAMMAR)
        _COMPILED = Grammar(GRAMMAR, cst=True, start="top-level")
        _COMPILED.transformers = load_ast_map(_COMPILED)
    return _COMPILED


def finalize_file(file_node):
    """RETURN: ModuleRoot, the typed file product over the engine's
              "<file>" STAR node -- the single exit through which every parse
              driver yields its file result.

    The engine's parse loop (start rule to EOF) builds the file STAR itself;
    it is not a rule, so the transformers never touch it -- this is the ONE
    place the typed root is produced. Every driver -- parse() here, and the
    fuzz harness, which injects its own lexer and drives EngineParser directly
    -- routes through this function, never growing its own slightly-different
    file shape (CARRY-OVER-HARVEST item 9).
    """
    return make_module_root(file_node)
