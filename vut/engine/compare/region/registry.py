"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: THE region-handler registry -- shebang name -> region handler.

A region declares its own interpretation through a shebang line:

    ##! <handler> [<param> | <param>=<value>]*
    ...region lines...
    ####

The registry maps the handler name to a 'RegionHandler' descriptor which
knows (a) the InputChunk class implementing the two faces (Judge/Lawyer),
and (b) the parameter specification. This is the OPEN axis: a new region
kind is a new package under region/ plus one registration here -- no shared
machinery is touched.

SYNTAX RULES (loud errors, never silent misinterpretation):

    - unknown handler name                   -> RegionSyntaxError + line number
    - unknown / malformed parameter          -> RegionSyntaxError + line number
    - '##!' inside an open region (nesting)  -> RegionSyntaxError + line number
    - '####' outside any region              -> RegionSyntaxError + line number
    - EOF with an open region                -> RegionSyntaxError + line number

PARAMETER RESOLUTION (precedence, highest first):

    1. shebang parameter        '##! potpourri max_comparisons=64'
    2. handler-scoped config    Configuration.region['potpourri'][...]
    3. the spec's default

A braced value '{...}' may contain whitespace (expression parameters).

NOMINAL IS AUTHORITATIVE (user ruling): the comparison SEMANTICS are
governed by the NOMINAL side's resolved parameters; the subject's shebang
need only name the same handler (its parameters are syntax-checked but
never applied and -- for expression parameters -- NEVER evaluated). The
faces implement this by reading parameters from the nominal chunk.

THE REGION-HANDLER CONTRACT (DOC/SEMANTICS.txt section 7): both faces
satisfy THE LAW; no analogy state in or out; line insignificance and lexing
come from the shared substrate.
________________________________________________________________________________
"""
from dataclasses import dataclass, field


class RegionSyntaxError(Exception):
    """Region framing of the INPUT is broken (unknown handler, bad
    parameter, nesting, stray/missing '####'). Deliberately loud: a region
    marker must never be silently reinterpreted as content.
    """
    def __init__(self, line_n, message):
        self.line_n = line_n
        super().__init__("line %s: %s" % (line_n, message))


@dataclass(frozen=True)
class ParamSpec:
    """Specification of one shebang parameter."""
    name:    str
    kind:    str            # 'flag' (bare) or 'value' (name=value)
    convert: object = str   # value converter, e.g. int; raises on bad input
    default: object = None


@dataclass(frozen=True)
class RegionHandler:
    """Descriptor of one region kind.

    'chunk_class' implements the faces: '_is_equivalent_to_nominal' (Judge)
    and/or '_associate_with_nominal' (Lawyer). Its constructor signature is
    (start_line_n, end_line_n, line_list, config, params).
    """
    shebang_name: str                   # name after '##!'
    chunk_class:  object                # resolved lazily via 'resolve()'
    param_spec:   dict = field(default_factory=dict)  # name -> ParamSpec

    def resolve_params(self, given, config, line_n):
        """RETURNS: dict, the fully resolved parameter set for one region:
                          shebang > handler-scoped config > spec default.

        Raises RegionSyntaxError on unknown names or unconvertible values.
        """
        section = {}
        region_db = getattr(config, "region", None)
        if region_db:
            section = region_db.get(self.shebang_name, {})
            for key in section:
                if key not in self.param_spec:
                    raise RegionSyntaxError(line_n,
                        "configuration section region['%s'] carries unknown "
                        "parameter '%s'" % (self.shebang_name, key))

        result = {}
        for name, spec in self.param_spec.items():
            if   name in given:   raw = given[name]
            elif name in section: raw = section[name]
            else:
                result[name] = spec.default
                continue
            try:
                result[name] = spec.convert(raw) if raw is not True else True
            except (ValueError, TypeError):
                raise RegionSyntaxError(line_n,
                    "parameter '%s' of region handler '%s': cannot interpret "
                    "value '%s'" % (name, self.shebang_name, raw))
        return result


def _tokenize_params(text, line_n):
    """RETURNS: list of str, the parameter tokens of a shebang tail.

    A token is '<param>' or '<param>=<value>'. A value may be BRACED,
    '{...}', in which case it runs to the matching closing brace and may
    contain whitespace (and nested braces):

        constraint={abs(y - sin(x)/x) < 0.01}
    """
    token_list = []
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i == n:
            break
        start = i
        while i < n and not text[i].isspace() and text[i] != "{":
            i += 1
        if i < n and text[i] == "{":
            depth = 0
            while i < n:
                if   text[i] == "{": depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            else:
                pass
            if depth != 0:
                raise RegionSyntaxError(line_n,
                    "unbalanced '{...}' in region parameter: %r"
                    % text[start:].strip())
        token_list.append(text[start:i])
    return token_list


def parse_shebang(line, line_n, handler_db):
    """RETURNS: [0] RegionHandler, the handler named on the shebang line.
                [1] dict, the raw given parameters (flags map to True).

    Grammar:  ##! <handler> [<param> | <param>=<value> | <param>={...}]*

    A braced value may contain whitespace (expression parameters). Raises
    RegionSyntaxError on anything unexpected -- an input that LOOKS like a
    region declaration is never silently degraded to content.
    """
    tail = line.strip()
    assert tail.startswith("##!")
    token_list = _tokenize_params(tail[3:], line_n)

    if not token_list:
        raise RegionSyntaxError(line_n,
            "region shebang '##!' without a handler name; known handlers: %s"
            % ", ".join(sorted(handler_db)))

    name = token_list[0]
    handler = handler_db.get(name)
    if handler is None:
        raise RegionSyntaxError(line_n,
            "unknown region handler '%s'; known handlers: %s"
            % (name, ", ".join(sorted(handler_db))))

    given = {}
    for token in token_list[1:]:
        key, eq, value = token.partition("=")
        if value.startswith("{") and value.endswith("}"):
            value = value[1:-1].strip()
        spec = handler.param_spec.get(key)
        if spec is None:
            raise RegionSyntaxError(line_n,
                "region handler '%s' knows no parameter '%s'; known: %s"
                % (name, key, ", ".join(sorted(handler.param_spec)) or "(none)"))
        elif spec.kind == "flag" and eq:
            raise RegionSyntaxError(line_n,
                "parameter '%s' of region handler '%s' is a flag; "
                "no '=<value>' allowed" % (key, name))
        elif spec.kind == "value" and not eq:
            raise RegionSyntaxError(line_n,
                "parameter '%s' of region handler '%s' requires '=<value>'"
                % (key, name))
        elif key in given:
            raise RegionSyntaxError(line_n,
                "parameter '%s' given twice" % key)
        given[key] = value if eq else True

    return handler, given


def make_region_chunk(handler, start_line_n, end_line_n, line_list, config,
                      given_params):
    """RETURNS: InputChunk, the handler's chunk carrying the region's lines
                            and its resolved parameters.
    """
    params = handler.resolve_params(given_params, config, start_line_n)
    return handler.chunk_class(start_line_n, end_line_n, line_list, config,
                               params)


# ------------------------------------------------------------------------------
# THE registry. A new region kind: implement the chunk class (faces) in its
# package under region/, then register it here.
# ------------------------------------------------------------------------------

def _handler_db():
    """RETURNS: dict, shebang name -> RegionHandler.

    Late import: chunk classes live near their faces; importing them at
    module load would cycle through reading/input_chunk.
    """
    from vut.engine.compare.region.potpourri.chunk import InputChunkPotpourri
    from vut.engine.compare.region.verbatim.chunk    import InputChunkVerbatim
    from vut.engine.compare.region.ignore.chunk      import InputChunkIgnore
    from vut.engine.compare.region.point_cloud.chunk import InputChunkPointCloud
    from vut.engine.compare.region.table.chunk       import (InputChunkTable,
                                                             convert_ignore,
                                                             convert_numeric)

    return {
        "table": RegionHandler(
            shebang_name = "table",
            chunk_class  = InputChunkTable,
            param_spec   = {
                "key":       ParamSpec("key", "value", convert=int,
                                       default=None),
                "ignore":    ParamSpec("ignore", "value",
                                       convert=convert_ignore, default=None),
                "numeric":   ParamSpec("numeric", "value",
                                       convert=convert_numeric, default=None),
                "unordered": ParamSpec("unordered", "flag", default=False),
                "sep":       ParamSpec("sep", "value", convert=str,
                                       default=None),
            }),
        "point-cloud": RegionHandler(
            shebang_name = "point-cloud",
            chunk_class  = InputChunkPointCloud,
            param_spec   = {
                "limit":      ParamSpec("limit", "value",
                                        convert=float, default=None),
                "dist":       ParamSpec("dist", "value",
                                        convert=str, default="euclidean"),
                "pair":       ParamSpec("pair", "flag", default=False),
                "constraint": ParamSpec("constraint", "value",
                                        convert=str, default=None),
            }),
        "potpourri": RegionHandler(
            shebang_name = "potpourri",
            chunk_class  = InputChunkPotpourri,
            param_spec   = {
                "max_comparisons": ParamSpec("max_comparisons", "value",
                                             convert=int, default=128),
                "subset":     ParamSpec("subset", "flag", default=False),
                "duplicates": ParamSpec("duplicates", "flag", default=False),
            }),
        "verbatim": RegionHandler(
            shebang_name = "verbatim",
            chunk_class  = InputChunkVerbatim),
        "ignore": RegionHandler(
            shebang_name = "ignore",
            chunk_class  = InputChunkIgnore),
    }


_db_cache = None

def handler_db():
    """RETURNS: dict, shebang name -> RegionHandler (cached)."""
    global _db_cache
    if _db_cache is None:
        _db_cache = _handler_db()
    return _db_cache
