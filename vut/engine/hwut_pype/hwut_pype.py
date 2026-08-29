"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

'pype' -- a line-matching language that triggers Python actions.

A pype script defines MODES. Each mode carries HANDLERS. A handler pairs a
line PATTERN with one or more Python action blocks. Input lines arrive on
stdin. For each line, the handlers of the ACTIVE mode are tried in definition
order; the first whose pattern matches fires. All Python blocks share one
single namespace.

Script grammar (line-oriented):

    HANDLER  :=  [ MODE "/" ] "on:" CAUSE "=>" EFFECT { "and:" EFFECT }
    INHERIT  :=  [ MODE ] "is:" BASE { "," BASE }
    IMPORT   :=  "import:" FILE-PATH

    CAUSE    :=  PATTERN                  match handler
              |  "if" "(" python-condition ")"
              |  "<else>"                 no match handler fired
              |  "<entry>" | "<exit>"     mode activated / deactivated
              |  "<bof>"   | "<eof>"      file begins / ends
    EFFECT   :=  "{" python block "}"     run the block
              |  "goto" OTHERMODE ";"     switch mode
              |  "push" OTHERMODE ";"     stack the mode, switch
              |  "pop" ";"                return to the stacked mode
              |  "ignore" ";"             nothing (consume the line)
              |  "flush" ";"              emit the line unchanged

A missing MODE addresses the DEFAULT MODE. Each "and:" appends one
further EFFECT to the preceding handler; effects run in order.
"import:" merges another pype file (resolved against the importer's
directory, then the '--pype-dir' directories; idempotent; cycles are
errors).

Pattern tokens (whitespace-separated; matched left-to-right in the line,
gaps of arbitrary whitespace permitted between tokens; the pattern matches
anywhere in the line -- no anchoring to line start):

    "text"                       constant string
    <name = number>              floating point number -> float
    <name = int>                 integer               -> int
    <name = "GLOB">              glob on one token     -> str
    <number> <int> <"GLOB">      unnamed variants (match, no binding)

Special handlers '<entry>' and '<exit>' fire on mode activation/deactivation.
Bare 'on:' handlers form the DEFAULT MODE. The default mode, when present,
is active at start-up; otherwise the first mode defined in the script is.
The start mode's '<entry>' fires before the first input line. At end of
input the active mode's '<exit>' fires. The default mode has no name; once
left, it cannot be entered again.

'=> OTHERMODE' switches the active mode: '<exit>' of the old mode fires, then
'<entry>' of the new one. Inside Python blocks the same is available as
'mode("OTHERMODE")'; the switch is applied after the current handler's
blocks have completed.

'MODE/else:' (bare 'else:' in the default mode) fires when every match
handler of the active mode failed on the line; the first 'else' of the
effective list fires.

'LEFT is: BASE1, BASE2, ...' gives LEFT all handlers (<entry>, <exit>,
match, <else>) of every named base, transitively. A handler arriving
twice over a diamond is entered once. SHADOWING IS FORBIDDEN: any two
distinct pattern handlers of one effective list whose languages
intersect (some line matches both), and any second <else> handler, are
a hard error -- pattern dispatch is therefore order-free. 'if(...)'
causes are conditions, not patterns; they are exempt and fire in
effective-list order. '=> ignore;' consumes the line without effect;
'on: <else> => flush;' turns a script into a pass-through filter.
______________________________________________________________________________
"""
import os
import re
import sys
import textwrap
import time

# Compatibility policy: this file restricts itself to language features
# available across the widest practical range of Python 3 versions --
# no f-strings, no type annotations, no keyword-only arguments, no
# match statements. '%'-formatting throughout.
_monotonic = getattr(time, "monotonic", time.time)


class PypeError(Exception):
    """RETURN: --. Error in a pype script (parse or pattern error).

    Carries a message already formatted as 'file:line: text'.
    """
    pass


RE_HANDLER_HEAD = re.compile(r"^([A-Za-z_]\w*)\s*/\s*on\s*:\s*(.*)$")
RE_DEFAULT_HEAD = re.compile(r"^on\s*:\s*(.*)$")
RE_AND_HEAD     = re.compile(r"^and\s*:\s*(.*)$")
RE_IS_HEAD      = re.compile(r"^([A-Za-z_]\w*)\s+is\s*:\s*"
                             r"([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*$")
RE_IF_CAUSE     = re.compile(r"^if\s*\((.*)\)\s*$")
RE_CAUSE_KEYWORD = re.compile(
    r"^<\s*(entry|exit|bof|eof|else)\s*>$")
RE_IMPORT_HEAD  = re.compile(r"^import\s*:\s*(.*)$")
RE_IMPORT_PATH  = re.compile(r'^"((?:[^"\\\\]|\\\\.)*)"$')
RE_IS_DEFAULT   = re.compile(r"^is\s*:\s*"
                             r"([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*$")

# Name of the default mode. Not writable in a script ('/' and 'on:' heads
# admit identifiers only), hence the default mode cannot be switched into
# nor inherited from.
DEFAULT_MODE = "<default>"

# No word is reserved as a mode name. Effect commands are lowercase and
# ';'-terminated ('goto M ;', 'push M ;', 'pop ;', 'ignore ;',
# 'flush ;'); a mode name occurs only as the second argument of
# 'goto'/'push', hence mode names and commands cannot collide. Cause
# keywords are bracketed ('<entry>' etc., via RE_CAUSE_KEYWORD) and
# cannot collide with identifiers either. Semantic traps beyond
# grammatical collision are the script author's business.
RE_ARROW  = re.compile(r"=>\s*(.*)$")
RE_EFFECT = re.compile(
    r"^(?:(\{)"
    r"|goto\s+([A-Za-z_]\w*)\s*;"
    r"|push\s+([A-Za-z_]\w*)\s*;"
    r"|(pop)\s*;"
    r"|(ignore)\s*;"
    r"|(flush)\s*;)$")

RE_TOKEN_CONST  = re.compile(r'"((?:[^"\\]|\\.)*)"')
RE_TOKEN_BIND   = re.compile(
    r"<\s*(?:([A-Za-z_]\w*)"
    r"(?:\s*\[\s*([A-Za-z_]\w*)((?:\s*[-+]\s*\d+)*)\s*\])?"
    r"\s*=\s*)?"
    r"(number|int|\"((?:[^\"\\]|\\.)*)\")"
    r"\s*>")
RE_TOKEN_ANCHOR = re.compile(r"<\s*(bol|eol)\s*>")
RE_REPEAT_OPEN  = re.compile(r"\+\(\s*([A-Za-z_]\w*)\s*:")
RE_RANGE        = re.compile(r"^(\d+)?\s*(\.\.)?\s*(\d+)?$")

REGEX_NUMBER = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?"
REGEX_INT    = r"[-+]?\d+"

def parse(source_txt, file_name, search_dir_list=None, source_db=None):
    """RETURN: (dict, str), the mode map (name -> Mode) and the name of the
                            start mode if success.
               Raises PypeError, else.

    The start mode is the default mode (bare 'on:' handlers) when the
    script has one, otherwise the first-defined named mode. 'source_txt'
    is the complete script text; 'file_name' labels error messages and
    compiled block tracebacks.

    'import: "FILE-PATH"' lines pull in further pype files. The quoted
    path may contain environment variables ('$HOME/...'), expanded
    before resolution. A relative path is resolved against the
    importing file's directory, then against each entry of
    'search_dir_list' in order; an absolute path stands alone. A file already imported is
    entered once; an import cycle is an error. If the caller passes a
    dictionary as 'source_db', it is filled with file name -> source
    line list for every parsed file (feeding the tracer).
    """
    import os as _os
    mode_db         = {}
    first_mode_name = None
    seen_files      = set()
    search_dir_list = search_dir_list if search_dir_list is not None else []
    if source_db is None: source_db = {}

    def resolve_import(path_txt, importer_file, where):
        """RETURN: str, the resolved path of an imported file if success.
                   Raises PypeError, else.
        """
        candidate_list = [
            _os.path.join(_os.path.dirname(_os.path.abspath(importer_file)),
                          path_txt)]
        candidate_list += [_os.path.join(d, path_txt)
                           for d in search_dir_list]
        if _os.path.isabs(path_txt): candidate_list = [path_txt]
        for candidate in candidate_list:
            if _os.path.isfile(candidate): return candidate
        raise PypeError("%s: cannot find import '%s' (searched: %s)"
                        % (where, path_txt,
                           ", ".join(candidate_list)))

    def _parse_one(source_txt, file_name, import_stack):
        nonlocal first_mode_name
        source_db[file_name] = source_txt.splitlines()
        line_list       = source_db[file_name]
        current_handler = None
        i               = 0

        def get_mode(name):
            if name not in mode_db: mode_db[name] = Mode(name)
            return mode_db[name]

        def read_block(start_i):
            """RETURN: (code, int), the compiled Python block and the index of
                                    the line after the closing '}' if success.
                       Raises PypeError, else.
            """
            body = []
            j    = start_i
            while j < len(line_list):
                if line_list[j].strip() == "}":
                    code_txt = textwrap.dedent("\n".join(body)) or "pass"
                    padded   = "\n" * start_i + code_txt   # align tracebacks
                    return compile(padded, file_name, "exec"), j + 1
                body.append(line_list[j])
                j += 1
            raise PypeError("%s:%d: block opened here is never closed by '}'"
                            % (file_name, start_i))

        while i < len(line_list):
            raw   = line_list[i]
            where = "%s:%d" % (file_name, i + 1)
            text  = raw.strip()
            if not text or text.startswith("#"):
                i += 1
                continue

            match_import = RE_IMPORT_HEAD.match(text)
            if match_import is not None:
                match_path = RE_IMPORT_PATH.match(
                    match_import.group(1).strip())
                if match_path is None:
                    raise PypeError('%s: import path must be a quoted '
                                    'string: import: "PATH"' % where)
                path_txt = _os.path.expandvars(match_path.group(1))
                imported = resolve_import(path_txt, file_name, where)
                key = _os.path.abspath(imported)
                if key in import_stack:
                    raise PypeError("%s: import cycle via '%s'"
                                    % (where, imported))
                if key not in seen_files:
                    seen_files.add(key)
                    with open(imported, "r") as fh:
                        _parse_one(fh.read(), imported,
                                   import_stack + [key])
                current_handler = None
                i += 1
                continue

            match_and  = RE_AND_HEAD.match(text)
            match_on   = RE_HANDLER_HEAD.match(text)
            match_bare = RE_DEFAULT_HEAD.match(text)
            match_is   = RE_IS_HEAD.match(text) or RE_IS_DEFAULT.match(text)
            if match_is:
                if match_is.re is RE_IS_HEAD:
                    left_name, right_txt = match_is.group(1), match_is.group(2)
                else:
                    left_name, right_txt = DEFAULT_MODE, match_is.group(1)
                right_name_list = [n.strip() for n in right_txt.split(",")]
                for right_name in right_name_list:
                    get_mode(left_name).base_name_list.append((right_name, where))
                if left_name != DEFAULT_MODE and first_mode_name is None:
                    first_mode_name = left_name
                current_handler = None
                i += 1
                continue
            if match_and:
                if current_handler is None:
                    raise PypeError("%s: 'and:' without preceding handler" % where)
                rest = match_and.group(1)
            elif match_on:
                mode_name, rest = match_on.group(1), match_on.group(2)
                mode = get_mode(mode_name)
                if first_mode_name is None: first_mode_name = mode_name
            elif match_bare:
                rest = match_bare.group(1)
                mode = get_mode(DEFAULT_MODE)
            else:
                raise PypeError("%s: expected 'MODE/on:', 'on:', "
                                "'MODE is:' or 'and:'" % where)

            if match_and:
                effect_txt = rest.strip()
                if not effect_txt:
                    raise PypeError("%s: missing EFFECT after 'and:'" % where)
                head_txt = ""
            else:
                arrow = RE_ARROW.search(rest)
                if arrow is None:
                    raise PypeError("%s: missing '=> EFFECT'" % where)
                head_txt   = rest[:arrow.start()].strip()
                effect_txt = arrow.group(1).strip()

            if match_and:
                pass
            else:
                owner = mode.name
                match_keyword = RE_CAUSE_KEYWORD.match(head_txt)
                if match_keyword is not None:
                    kind = match_keyword.group(1)
                    current_handler = Handler(kind, owner_name=owner,
                                              where=where,
                                              cause_txt="<%s>" % kind)
                elif RE_IF_CAUSE.match(head_txt):
                    condition_txt = RE_IF_CAUSE.match(head_txt).group(1)
                    try:
                        condition = compile(condition_txt.strip(), where, "eval")
                    except SyntaxError as error:
                        raise PypeError("%s: cannot compile 'if' condition: %s"
                                        % (where, error)) from None
                    current_handler = Handler("match", owner_name=owner,
                                              where=where, condition=condition,
                                              cause_txt=head_txt)
                else:
                    matcher, token_list = compile_pattern(head_txt, where)
                    current_handler = Handler("match", matcher,
                                              owner_name=owner, where=where,
                                              token_list=token_list,
                                              cause_txt=head_txt)
                mode.handler_list.append(current_handler)

            match_effect = RE_EFFECT.match(effect_txt)
            if match_effect is None:
                raise PypeError("%s: cannot read EFFECT '%s'"
                                % (where, effect_txt))
            block_f, goto_name, push_name, pop_w, ignore_w, flush_w = \
                match_effect.groups()
            if block_f is not None:
                code, i = read_block(i + 1)
                current_handler.action_list.append(Action(code=code))
                continue
            if   goto_name is not None:
                current_handler.action_list.append(
                    Action(next_mode=goto_name))
            elif push_name is not None:
                current_handler.action_list.append(
                    Action(push_mode=push_name))
            elif pop_w is not None:
                current_handler.action_list.append(Action(pop_f=True))
            elif flush_w is not None:
                current_handler.action_list.append(Action(flush_f=True))
            else:                                        # ignore
                current_handler.action_list.append(Action())
            i += 1


    _parse_one(source_txt, file_name,
               [_os.path.abspath(file_name)])
    seen_files.add(_os.path.abspath(file_name))

    _resolve_inheritance(mode_db, file_name)

    if DEFAULT_MODE in mode_db:  start_mode_name = DEFAULT_MODE
    elif first_mode_name is None:
        raise PypeError("%s: script defines no mode" % file_name)
    else:                        start_mode_name = first_mode_name

    _check_else_present(mode_db, start_mode_name, file_name)
    return mode_db, start_mode_name



def parse_glob(glob_txt):
    """RETURN: list, of glob elements:
                     ('star',)                '*': run of non-space chars
                     ('any',)                 '?': one non-space char
                     ('char', c)              literal character
                     ('set', negate_f, chars) '[seq]'/'[!seq]': one char
                                              of/outside the frozenset

    Character classes follow fnmatch: '[!...]' negates, a ']' first in
    the sequence is literal, 'a-b' expands to the character range (empty
    when reversed). An unclosed '[' is a literal character. Whitespace
    never matches inside any glob element -- a glob stays within one
    token; whitespace characters are dropped from positive sets.
    """
    element_list = []
    i = 0
    while i < len(glob_txt):
        char = glob_txt[i]
        if   char == "*": element_list.append(("star",)); i += 1
        elif char == "?": element_list.append(("any",));  i += 1
        elif char == "[":
            j = i + 1
            negate_f = j < len(glob_txt) and glob_txt[j] == "!"
            if negate_f: j += 1
            k = j + 1 if j < len(glob_txt) and glob_txt[j] == "]" else j
            k = glob_txt.find("]", k)
            if k < 0:
                element_list.append(("char", "["))
                i += 1
                continue
            content = glob_txt[j:k]
            char_set = set()
            p = 0
            while p < len(content):
                if p + 2 < len(content) and content[p + 1] == "-":
                    for o in range(ord(content[p]), ord(content[p + 2]) + 1):
                        char_set.add(chr(o))
                    p += 3
                else:
                    char_set.add(content[p])
                    p += 1
            if not negate_f:
                char_set -= WS_CHARS
            element_list.append(("set", negate_f, frozenset(char_set)))
            i = k + 1
        else:
            element_list.append(("char", char))
            i += 1
    return element_list


def glob_to_regex(glob_txt):
    """RETURN: str, a regular expression fragment equivalent to 'glob_txt'
                    where '*' matches any run of non-space characters,
                    '?' one non-space character, and '[seq]'/'[!seq]'
                    one character of/outside the sequence.

    All other characters are matched literally. Globs apply to a single
    whitespace-delimited token, hence '\\S' rather than '.' and
    whitespace folded into every negated set.
    """
    def class_txt(char_set):
        return "".join("\\" + c if c in "\\^]-" else c
                       for c in sorted(char_set))
    out = []
    for element in parse_glob(glob_txt):
        if   element[0] == "star": out.append(r"\S*")
        elif element[0] == "any":  out.append(r"\S")
        elif element[0] == "char": out.append(re.escape(element[1]))
        elif element[1]:                             # negated set
            out.append("[^\\s%s]" % class_txt(element[2]))
        else:
            out.append("[%s]" % class_txt(element[2]))
    return "".join(out)


def _parse_token_list(txt, position, where, repeat_counter=None):
    """RETURN: (list, int), the token list and the position after it if
                            success. Parsing stops at end of text, or --
                            inside a repeat group -- at the closing ')'.
               Raises PypeError, else.

    Token list entries:
        ('const', text)
        ('number', name|None, offset|None)
        ('int',    name|None, offset|None)
        ('glob',   glob_txt, name|None, offset|None)
        ('bol',) / ('eol',)
        ('repeat', counter, sub_token_list)
    A repeat group matches its sub-pattern ONE OR MORE times. An indexed
    binding '<x[i] = ...>' or '<x[i + 2] = ...>' is lawful only inside a
    repeat group whose counter is 'i'; the offset is a chain of '+'/'-'
    integer terms; 'offset' None marks a plain binding. Repeat groups do
    not nest.
    """
    token_list = []
    while position < len(txt):
        if txt[position].isspace():
            position += 1
            continue
        if repeat_counter is not None and txt[position] == ")":
            return token_list, position + 1
        match = RE_REPEAT_OPEN.match(txt, position)
        if match:
            if repeat_counter is not None:
                raise PypeError("%s: repeat groups do not nest" % where)
            counter = match.group(1)
            sub_list, position = _parse_token_list(
                txt, match.end(), where, repeat_counter=counter)
            if not sub_list:
                raise PypeError("%s: empty repeat group" % where)
            token_list.append(("repeat", counter, sub_list))
            continue
        match = RE_TOKEN_ANCHOR.match(txt, position)
        if match:
            token_list.append((match.group(1),))
            position = match.end()
            continue
        match = RE_TOKEN_CONST.match(txt, position)
        if match:
            literal = match.group(1).replace(r'\"', '"').replace("\\\\", "\\")
            token_list.append(("const", literal))
            position = match.end()
            continue
        match = RE_TOKEN_BIND.match(txt, position)
        if match:
            name, index, offset_txt, kind, glob_txt = (
                match.group(1), match.group(2), match.group(3),
                match.group(4), match.group(5))
            if index is None:
                offset = None
            else:
                if repeat_counter is None:
                    raise PypeError("%s: indexed binding '%s[%s...]' "
                                    "outside a repeat group"
                                    % (where, name, index))
                if index != repeat_counter:
                    raise PypeError("%s: index '%s' does not name the "
                                    "repeat counter '%s'"
                                    % (where, index, repeat_counter))
                offset = sum(int(term.replace(" ", ""))
                             for term in re.findall(r"[-+]\s*\d+",
                                                    offset_txt or ""))
            if   kind == "number":
                token_list.append(("number", name, offset))
            elif kind == "int":
                token_list.append(("int", name, offset))
            else:
                token_list.append(("glob", glob_txt, name, offset))
            position = match.end()
            continue
        raise PypeError("%s: cannot read pattern at '%s'"
                        % (where, txt[position:]))
    if repeat_counter is not None:
        raise PypeError("%s: repeat group is never closed by ')'" % where)
    return token_list, position


def _token_plain_src(token):
    """RETURN: str, a regular-expression source (free of capturing
                    groups) matching the single variable-width or
                    constant 'token'; None for anchors and repeats.
    """
    if   token[0] == "const":  return re.escape(token[1])
    elif token[0] == "number": return REGEX_NUMBER
    elif token[0] == "int":    return REGEX_INT
    elif token[0] == "glob":   return glob_to_regex(token[1])
    return None


def _collect_const_list(token_list):
    """RETURN: list, the constant texts required by any match of
                     'token_list'. Constants inside a repeat group count:
                     one repetition is mandatory.
    """
    result = []
    for token in token_list:
        if   token[0] == "const":  result.append(token[1])
        elif token[0] == "repeat": result += _collect_const_list(token[2])
    return result


class Matcher:
    """RETURN: --. Matches one pattern token list against input lines.

    The pattern matches anywhere in the line (leftmost occurrence);
    tokens are separated by arbitrary whitespace. '<bol>'/'<eol>' demand
    line start/end at their position. A repeat group matches its
    sub-pattern ONE OR MORE times, greedily, without backtracking into
    the count once the group is left.

    Two execution paths, semantically identical:

    FAST PATH (no repeat group): the whole pattern compiles to ONE
    regular expression; each variable-width token and each inter-token
    whitespace run is wrapped in the atomic-group emulation
    '(?=(X))\\N' -- the lookahead captures the greedy match, the
    backreference commits to it -- reproducing the walk's
    no-backtracking-between-tokens law exactly. One C-level 'search'
    per line replaces the Python element walk.

    WALK PATH (repeat groups present): the structured element walk.

    Either path is preceded by the REQUIRED-LITERAL test: the longest
    constant of the pattern must occur in the line at all (a C-level
    substring test), or the pattern cannot match.
    """
    def __init__(self, token_list):
        self.token_list = token_list
        self.element_list = self._compile(token_list)
        const_list = _collect_const_list(token_list)
        self.required_literal = max(const_list, key=len) \
                                if const_list else None
        self.fast_regex  = None
        self.fast_groups = None
        self._build_fast(token_list)

    def _build_fast(self, token_list):
        """RETURN: None, setting 'fast_regex' (compiled) and
                         'fast_groups' ([(group_n, name, convert)]) if
                         the pattern is free of repeat groups; both stay
                         None otherwise.
        """
        if any(t[0] == "repeat" for t in token_list): return
        part_list  = []
        group_list = []
        group_n    = 0
        def atomic(src):
            nonlocal group_n
            group_n += 1
            return "(?=(%s))\\%d" % (src, group_n), group_n
        for k, token in enumerate(token_list):
            if k > 0:
                part, _ = atomic(r"\s*")
                part_list.append(part)
            if   token[0] == "bol": part_list.append("^")
            elif token[0] == "eol": part_list.append("$")
            elif token[0] == "const":
                part_list.append("(?:%s)" % re.escape(token[1]))
            else:
                part, n = atomic(_token_plain_src(token))
                part_list.append(part)
                if   token[0] == "number":
                    group_list.append((n, token[1], float))
                elif token[0] == "int":
                    group_list.append((n, token[1], int))
                else:                                    # glob
                    group_list.append((n, token[2], str))
        self.fast_regex  = re.compile("".join(part_list))
        self.fast_groups = group_list

    def _compile(self, token_list):
        """RETURN: list, executable elements mirroring 'token_list'."""
        element_list = []
        for token in token_list:
            if token[0] == "const":
                element_list.append(
                    ("re", re.compile(re.escape(token[1])), None, None, str))
            elif token[0] == "number":
                element_list.append(
                    ("re", re.compile(REGEX_NUMBER), token[1], token[2],
                     float))
            elif token[0] == "int":
                element_list.append(
                    ("re", re.compile(REGEX_INT), token[1], token[2], int))
            elif token[0] == "glob":
                element_list.append(
                    ("re", re.compile(glob_to_regex(token[1])), token[2],
                     token[3], str))
            elif token[0] in ("bol", "eol"):
                element_list.append((token[0],))
            else:                                        # repeat
                element_list.append(
                    ("repeat", token[1], self._compile(token[2])))
        return element_list

    def search(self, line):
        """RETURN: dict, the bindings (names -> values; repeat counters ->
                         counts; indexed names -> dicts keyed by counter
                         value) of the leftmost match if success.
                   None, else.
        """
        if self.required_literal is not None \
           and self.required_literal not in line:
            return None
        if self.fast_regex is not None:
            match = self.fast_regex.search(line)
            if match is None: return None
            binding_db = {}
            for group_n, name, convert in self.fast_groups:
                if name is not None:
                    binding_db[name] = convert(match.group(group_n))
            return binding_db
        for start in range(len(line) + 1):
            result = self._match_at(line, start, self.element_list)
            if result is None: continue
            _, triple_list = result
            binding_db = {}
            for name, indexed_key, value in triple_list:
                if indexed_key is None:
                    binding_db[name] = value
                else:
                    binding_db.setdefault(name, {})[indexed_key] = value
            return binding_db
        return None

    def _match_at(self, line, pos, element_list):
        """RETURN: (int, list), end position and raw bindings of a match
                                of 'element_list' at 'pos' if success.
                                Raw bindings are (name, indexed_key,
                                value) triples; 'indexed_key' is None for
                                plain bindings.
                   None, else.
        """
        triple_list = []
        for k, element in enumerate(element_list):
            if k > 0:
                while pos < len(line) and line[pos].isspace(): pos += 1
            if element[0] == "bol":
                if pos != 0: return None
            elif element[0] == "eol":
                if pos != len(line): return None
            elif element[0] == "re":
                _, rx, name, offset, convert = element
                match = rx.match(line, pos)
                if match is None: return None
                if name is not None:
                    triple_list.append((name, None, convert(match.group(0))))
                pos = match.end()
            else:                                        # repeat
                _, counter, sub_list = element
                offset_db = self._offset_db(sub_list)
                count = 0
                while True:
                    save  = pos
                    probe = pos
                    while probe < len(line) and line[probe].isspace():
                        probe += 1
                    result = self._match_at(line, probe, sub_list)
                    if result is None:
                        break
                    new_pos, sub_triple_list = result
                    if new_pos == save:
                        break                            # zero-width guard
                    for name, _, value in sub_triple_list:
                        if name in offset_db:
                            triple_list.append(
                                (name, count + offset_db[name], value))
                        else:
                            triple_list.append((name, None, value))
                    pos = new_pos
                    count += 1
                if count < 1: return None
                triple_list.append((counter, None, count))
        return pos, triple_list

    def _offset_db(self, element_list):
        """RETURN: dict, name -> index offset for the bindings indexed
                         with the repeat counter in 'element_list'.
        """
        return dict((e[2], e[3]) for e in element_list
                    if e[0] == "re" and e[2] is not None
                    and e[3] is not None)


def compile_pattern(pattern_txt, where):
    """RETURN: (Matcher, list), the pattern matcher and its token list
                                (feeding interference detection and
                                example generation) if success.
               Raises PypeError, else.

    'pattern_txt' is the token sequence between 'on:' and '=>'.
    """
    token_list, _ = _parse_token_list(pattern_txt.strip(), 0, where)
    if not token_list:
        raise PypeError("%s: empty pattern" % where)
    return Matcher(token_list), token_list


class Action:
    """RETURN: --. One consequence of a handler firing: a compiled Python
                   block, a mode switch, a stack push or pop, the flush
                   effect (emit the input line unchanged on stdout), or
                   nothing (IGNORE).
    """
    def __init__(self, code=None, next_mode=None, flush_f=False,
                 push_mode=None, pop_f=False):
        self.code      = code        # compiled code object or None
        self.next_mode = next_mode   # str or None
        self.flush_f   = flush_f     # bool
        self.push_mode = push_mode   # str or None
        self.pop_f     = pop_f       # bool


# ---------------------------------------------------------------------------
# Pattern intersection (interference detection).
#
# A pattern's token list describes a regular language. Two patterns
# INTERSECT if some string belongs to both languages. Test: Thompson NFA
# per token list, then reachability of the joint accept pair on the
# product automaton. Character classes are (negated, char_set) pairs.

WS_CHARS  = frozenset(" \t\n\r\v\f")
CLS_WS    = (False, WS_CHARS)
CLS_NONWS = (True,  WS_CHARS)
CLS_DIGIT = (False, frozenset("0123456789"))
CLS_SIGN  = (False, frozenset("+-"))
CLS_EXP   = (False, frozenset("eE"))


def _cls_lit(char):
    """RETURN: tuple, the character class matching exactly 'char'."""
    return (False, frozenset((char,)))


def _cls_intersect(cls_a, cls_b):
    """RETURN: True, if some character belongs to both classes.
               False, else.
    """
    neg_a, set_a = cls_a
    neg_b, set_b = cls_b
    if not neg_a and not neg_b: return bool(set_a & set_b)
    if not neg_a and neg_b:     return bool(set_a - set_b)
    if neg_a and not neg_b:     return bool(set_b - set_a)
    return True   # complements of finite sets always share a character


class _Nfa:
    """RETURN: --. Thompson NFA over character classes.

    'eps[s]' lists epsilon successors of state s; 'sym[s]' lists
    (class, destination) transitions. Fragment constructors 'f_*' return
    (entry, exit) state pairs; fragments are single-use (fresh states per
    call).
    """
    def __init__(self):
        self.eps = []
        self.sym = []

    def new_state(self):
        """RETURN: int, a fresh state id."""
        self.eps.append([])
        self.sym.append([])
        return len(self.eps) - 1

    def f_eps(self):
        """RETURN: (int, int), fragment matching the empty string."""
        a, b = self.new_state(), self.new_state()
        self.eps[a].append(b)
        return a, b

    def f_sym(self, cls):
        """RETURN: (int, int), fragment matching one character of 'cls'."""
        a, b = self.new_state(), self.new_state()
        self.sym[a].append((cls, b))
        return a, b

    def f_seq(self, frag_list):
        """RETURN: (int, int), fragment matching the concatenation."""
        assert frag_list
        for (_, e1), (s2, _) in zip(frag_list, frag_list[1:], strict=False):
            self.eps[e1].append(s2)
        return frag_list[0][0], frag_list[-1][1]

    def f_alt(self, frag_list):
        """RETURN: (int, int), fragment matching any alternative."""
        a, b = self.new_state(), self.new_state()
        for s, e in frag_list:
            self.eps[a].append(s)
            self.eps[e].append(b)
        return a, b

    def f_star(self, frag):
        """RETURN: (int, int), fragment matching zero or more repetitions."""
        a, b = self.new_state(), self.new_state()
        s, e = frag
        self.eps[a].extend((s, b))
        self.eps[e].extend((s, b))
        return a, b

    def f_opt(self, frag):
        """RETURN: (int, int), fragment matching the inner or nothing."""
        return self.f_alt([frag, self.f_eps()])

    def f_plus(self, make_frag):
        """RETURN: (int, int), fragment matching one or more repetitions.

        'make_frag' is a factory; fragments are single-use.
        """
        return self.f_seq([make_frag(), self.f_star(make_frag())])


def _nfa_of_token_list(token_list):
    """RETURN: (_Nfa, int, int), the automaton with its start and accept
                                 state, accepting exactly the strings the
                                 pattern built from 'token_list' matches.

    '<bol>'/'<eol>' are position demands, not characters; they are
    transparent here (interference is decided on the pattern languages).
    A repeat group is one copy of its sub-pattern followed by a star of
    further copies (one or more).
    """
    nfa = _Nfa()

    def digits():
        return nfa.f_plus(lambda: nfa.f_sym(CLS_DIGIT))

    def token_fragment(token):
        if token[0] == "const":
            char_list = [nfa.f_sym(_cls_lit(c)) for c in token[1]]
            return nfa.f_seq(char_list) if char_list else nfa.f_eps()
        if token[0] == "int":
            return nfa.f_seq([nfa.f_opt(nfa.f_sym(CLS_SIGN)), digits()])
        if token[0] == "number":
            mantissa = nfa.f_alt([
                nfa.f_seq([digits(), nfa.f_sym(_cls_lit(".")),
                           nfa.f_star(nfa.f_sym(CLS_DIGIT))]),
                nfa.f_seq([nfa.f_sym(_cls_lit(".")), digits()]),
                digits(),
            ])
            exponent = nfa.f_opt(nfa.f_seq([
                nfa.f_sym(CLS_EXP),
                nfa.f_opt(nfa.f_sym(CLS_SIGN)),
                digits()]))
            return nfa.f_seq([nfa.f_opt(nfa.f_sym(CLS_SIGN)),
                              mantissa, exponent])
        if token[0] == "glob":
            frag_list = []
            for element in parse_glob(token[1]):
                if   element[0] == "star":
                    frag_list.append(nfa.f_star(nfa.f_sym(CLS_NONWS)))
                elif element[0] == "any":
                    frag_list.append(nfa.f_sym(CLS_NONWS))
                elif element[0] == "char":
                    frag_list.append(nfa.f_sym(_cls_lit(element[1])))
                elif element[1]:                     # negated set
                    frag_list.append(
                        nfa.f_sym((True, element[2] | WS_CHARS)))
                else:
                    frag_list.append(nfa.f_sym((False, element[2])))
            return nfa.f_seq(frag_list) if frag_list else nfa.f_eps()
        if token[0] in ("bol", "eol"):
            return nfa.f_eps()
        # repeat: one copy, then a star of further copies
        _, _, sub_list = token
        def one_copy(lead_ws_f):
            frag_list = []
            if lead_ws_f: frag_list.append(nfa.f_star(nfa.f_sym(CLS_WS)))
            frag_list.append(sequence_fragment(sub_list))
            return nfa.f_seq(frag_list)
        return nfa.f_seq([one_copy(lead_ws_f=False),
                          nfa.f_star(one_copy(lead_ws_f=True))])

    def sequence_fragment(token_list):
        frag_list = []
        for k, token in enumerate(token_list):
            if k > 0: frag_list.append(nfa.f_star(nfa.f_sym(CLS_WS)))
            frag_list.append(token_fragment(token))
        return nfa.f_seq(frag_list)

    start, accept = sequence_fragment(token_list)
    return nfa, start, accept


def _patterns_intersect(token_list_a, token_list_b):
    """RETURN: True, if some string is matched by both patterns.
               False, else.

    Reachability of (accept_a, accept_b) on the product automaton:
    epsilon moves advance either side alone; a joint symbol move exists
    where the two character classes intersect.
    """
    nfa_a, start_a, accept_a = _nfa_of_token_list(token_list_a)
    nfa_b, start_b, accept_b = _nfa_of_token_list(token_list_b)
    seen  = {(start_a, start_b)}
    stack = [(start_a, start_b)]
    while stack:
        a, b = stack.pop()
        if a == accept_a and b == accept_b:
            return True
        successor_list = [(a2, b) for a2 in nfa_a.eps[a]] \
                       + [(a, b2) for b2 in nfa_b.eps[b]] \
                       + [(a2, b2)
                          for cls_a, a2 in nfa_a.sym[a]
                          for cls_b, b2 in nfa_b.sym[b]
                          if _cls_intersect(cls_a, cls_b)]
        for pair in successor_list:
            if pair not in seen:
                seen.add(pair)
                stack.append(pair)
    return False


class Handler:
    """RETURN: --. A (pattern, actions) pair inside a mode.

    'kind' is one of 'match', 'entry', 'exit', 'bof', 'eof', 'else'. A
    'match' handler carries either a 'pattern' (a Matcher, with its
    'token_list') or a 'condition' (compiled Python expression of an
    'if(...)' cause). 'entry'/'exit' fire on mode transitions,
    'bof'/'eof' on the file boundaries. 'owner_name' and 'where' record
    the defining mode and script location for interference reports.
    """
    def __init__(self, kind, pattern=None, owner_name=None, where=None,
                 token_list=None, condition=None, cause_txt=""):
        self.kind         = kind
        self.pattern      = pattern
        self.condition    = condition
        self.action_list  = []
        self.owner_name   = owner_name
        self.where        = where
        self.cause_txt    = cause_txt
        self.token_list   = token_list if token_list is not None else []


class Mode:
    """RETURN: --. A named collection of handlers; one mode is active at a
                   time.

    'base_name_list' names the modes this mode inherits handlers from
    ('LEFT is: RIGHT'). 'resolved_list' is the effective handler list
    after inheritance resolution: own handlers first, then the bases'
    effective handlers in 'is:' declaration order.
    """
    def __init__(self, name):
        self.name           = name
        self.handler_list   = []
        self.base_name_list = []
        self.resolved_list  = None
        self.gate_regex     = None    # reject gate, see build_gate()
        self.gate_id_set    = frozenset()

    def build_gate(self):
        """RETURN: None, setting the mode's REJECT GATE: one alternation
                         of the plain (backtracking) pattern sources of
                         every repeat-free pattern handler.

        The gate is COMPLETE, never selective: a plain source matches a
        superset of its atomic counterpart, so a line the gate rejects
        matches none of the covered handlers -- their individual scans
        are skipped. A line the gate accepts is still dispatched by the
        per-handler scans in effective order (two handlers with
        disjoint pattern languages may still both match one line, at
        different positions; the gate never chooses).
        """
        src_list = []
        id_list  = []
        for handler in self.handlers("match"):
            if handler.condition is not None: continue
            if handler.pattern.fast_regex is None: continue
            part_list = []
            for k, token in enumerate(handler.pattern.token_list):
                if k > 0: part_list.append(r"\s*")
                if   token[0] == "bol": part_list.append("^")
                elif token[0] == "eol": part_list.append("$")
                else:
                    part_list.append("(?:%s)" % _token_plain_src(token))
            src_list.append("(?:%s)" % "".join(part_list))
            id_list.append(id(handler))
        if len(src_list) >= 2:
            self.gate_regex  = re.compile("|".join(src_list))
            self.gate_id_set = frozenset(id_list)

    def handlers(self, kind):
        """RETURN: list, the effective handlers of the given kind ('match',
                         'entry', 'exit', 'else') in resolution order: own
                         handlers first, then inherited.
        """
        source = self.resolved_list if self.resolved_list is not None \
                 else self.handler_list
        return [h for h in source if h.kind == kind]


def _check_else_present(mode_db, start_mode_name, file_name):
    """RETURN: None, if every ACTIVATABLE mode carries an 'else' handler
                     in its effective list.
               Raises PypeError, else.

    Activatable: the start mode and every mode named as a static switch
    or push target. Pure mixin modes (inherited from, never activated)
    are exempt. Modes reached only through 'mode()'/'push()' calls are
    checked at activation time by the interpreter.
    """
    activatable = {start_mode_name}
    for mode in mode_db.values():
        for handler in mode.handler_list:
            for action in handler.action_list:
                if action.next_mode is not None:
                    activatable.add(action.next_mode)
                if action.push_mode is not None:
                    activatable.add(action.push_mode)
    for name in sorted(activatable):
        if name not in mode_db: continue         # unknown: runtime error
        if not mode_db[name].handlers("else"):
            raise PypeError("%s: mode '%s' has no <else> handler in its "
                            "effective list; every activatable mode must "
                            "state what happens to unmatched lines"
                            % (file_name, name))


def _resolve_inheritance(mode_db, file_name):
    """RETURN: None, with every mode's 'resolved_list' set if success.
               Raises PypeError, else.

    'LEFT is: RIGHT1, RIGHT2, ...' gives LEFT all handlers of every named
    base, transitively. The effective list is: own handlers first, then
    each base's effective list in declaration order. A handler arriving
    twice over a diamond is entered once.

    INTERFERENCE is a hard error: any two DISTINCT pattern handlers of
    one effective list whose languages INTERSECT (some line matches
    both) -- SHADOWING IS FORBIDDEN, except for <else>; see
    _check_interference. A mode containing an 'if(...)' cause cannot be
    inherited from.
    """
    IN_PROGRESS = "in-progress"

    def resolve(mode, trail):
        if mode.resolved_list is IN_PROGRESS:
            raise PypeError("%s: inheritance cycle: %s"
                            % (file_name, " is: ".join(trail + [mode.name])))
        if mode.resolved_list is not None:
            return mode.resolved_list
        mode.resolved_list = IN_PROGRESS
        result  = []
        seen_id = set()
        for handler in mode.handler_list:
            result.append(handler)
            seen_id.add(id(handler))
        for base_name, where in mode.base_name_list:
            if base_name not in mode_db:
                raise PypeError("%s: 'is:' names unknown mode '%s'"
                                % (where, base_name))
            base = mode_db[base_name]
            if any(h.condition is not None for h in base.handler_list):
                raise PypeError(
                    "%s: mode '%s' contains an 'if' cause and cannot "
                    "be inherited from" % (where, base_name))
            for handler in resolve(base, trail + [mode.name]):
                if id(handler) in seen_id: continue      # diamond duplicate
                result.append(handler)
                seen_id.add(id(handler))
        _check_interference(mode, result, mode_db, file_name)
        mode.resolved_list = result
        mode.build_gate()
        return result

    for mode in mode_db.values():
        resolve(mode, [])


def _check_interference(mode, resolved_list, mode_db, file_name):
    """RETURN: None, if the mode's effective list is free of
                     interference: all pattern causes pairwise DISJOINT
                     and at most one <else> handler.
               Raises PypeError, else.

    SHADOWING IS FORBIDDEN. Any two distinct pattern handlers in one
    effective list -- own against own, own against inherited, inherited
    against inherited -- whose pattern languages intersect (some line
    matches both) are a hard error: no handler may pre-empt another by
    order. Consequently pattern dispatch is order-free; at most one
    pattern can match a line. <else> is THE ONE EXCEPTION: it can and
    must be shadowed -- the first <else> of the effective list fires,
    own before inherited. 'if(...)' causes are CONDITIONS, not
    patterns: they never inherit (a mode containing one cannot be a
    base) and fire in definition order. <entry>/<exit>/<bof>/<eof>
    handlers all fire and cannot interfere. A handler arriving twice
    over a diamond is one handler, not a pair.
    """
    pattern_list = [h for h in resolved_list
                    if h.kind == "match" and h.condition is None]
    for k, first in enumerate(pattern_list):
        for second in pattern_list[k + 1:]:
            if _patterns_intersect(first.token_list, second.token_list):
                raise PypeError(
                    "%s: interference in mode '%s': handlers from '%s' "
                    "(%s) and '%s' (%s) carry intersecting patterns; "
                    "shadowing is forbidden"
                    % (file_name, mode.name,
                       first.owner_name, first.where,
                       second.owner_name, second.where))


class PypeInfo:
    """RETURN: --. The 'pype' object visible in every Python block; the
                   one place for runtime information.

    pype.time()         seconds (float) since start of reading
    pype.file_name()    name of the running pype script
    pype.line()         current input line, trailing newline stripped
    pype.line_n()       current input line number, 1-based
    pype.mode_name()    name of the active mode
    pype.stack_depth()  depth of the PUSH/POP mode stack
    pype.bindings()     dictionary of the current line's pattern
                        bindings (empty for 'if'/ELSE/lifecycle fires)
    pype.goto(NAME)     request a mode switch
    pype.push(NAME)     request a stack push
    pype.pop()          request a stack pop
    """
    def __init__(self, interpreter):
        self._itp = interpreter

    def time(self):
        """RETURN: float, seconds since start of reading."""
        return _monotonic() - self._itp.start_time

    def file_name(self):
        """RETURN: str, name of the running pype script."""
        return self._itp.file_name

    def line(self):
        """RETURN: str, the current input line, newline stripped."""
        return self._itp.current_line

    def line_n(self):
        """RETURN: int, the current input line number, 1-based.
                        0 before the first line.
        """
        return self._itp.current_line_n

    def mode_name(self):
        """RETURN: str, the name of the active mode."""
        return self._itp.active.name

    def stack_depth(self):
        """RETURN: int, the depth of the PUSH/POP mode stack."""
        return len(self._itp.stack)

    def bindings(self):
        """RETURN: dict, the bindings established by the pattern match of
                          the current line: named captures, indexed
                          repeat dictionaries, repeat counters.
                          Empty if the current line fired an 'if' cause,
                          an ELSE handler, or no handler, and inside
                          ENTRY/EXIT/BOF/EOF handlers.
        """
        return dict(self._itp.current_bindings)

    def goto(self, mode_name):
        """RETURN: None. Requests a mode switch; applied after the
                         current handler's effects have completed.
        """
        self._itp.request_switch(mode_name)

    def push(self, mode_name):
        """RETURN: None. Requests a stack push; applied after the
                         current handler's effects have completed.
        """
        self._itp.request_push(mode_name)

    def pop(self):
        """RETURN: None. Requests a stack pop; applied after the
                         current handler's effects have completed.
        """
        self._itp.request_pop()


class Interpreter:
    """RETURN: --. Executes a parsed pype script against a line stream.

    All Python blocks run in the single shared namespace
    'self.namespace', which provides the pattern bindings, 'mode(name)',
    'push(name)', 'pop()' and the 'pype' information object (PypeInfo).
    """
    def __init__(self, mode_db, start_mode_name, file_name="<stream>",
                 trace_style=None, source_db=None, trace_filter=None):
        self.mode_db         = mode_db
        self.active          = None
        self.start_mode_name = start_mode_name
        self.file_name       = file_name
        self.trace_style     = trace_style   # None | "gcc" | "plain"
        self.source_db       = source_db if source_db is not None else {}
        self.trace_filter    = frozenset(trace_filter) \
                               if trace_filter else None
        self.request         = None      # ("switch"|"push", name) | ("pop",)
        self.stack           = []
        self.start_time      = _monotonic()
        self.current_line    = ""
        self.current_line_n  = 0
        self.input_name      = "<stdin>"
        self.input_line_n    = 0
        self.current_bindings = {}
        self.namespace       = {"pype": PypeInfo(self)}

    def trace(self, where, gcc_txt, plain_txt):
        """RETURN: None. Emits one trace line on stderr in trace mode.

        Two styles: 'gcc' (the default) prefixes every line with
        'file:line:' in compiler-diagnostic format, so editors can jump
        to the location; 'plain' prefixes 'TRACE|' and indents. Trace
        output goes to stderr so that stdout remains the clean,
        deterministic filter stream.
        """
        if self.trace_style is None: return
        if self.trace_filter is not None:
            if self.active is None: return
            if self.active.name not in self.trace_filter: return
        if self.trace_style == "plain":
            sys.stderr.write("TRACE| " + plain_txt + "\n")
        else:
            sys.stderr.write("%s: %s\n"
                             % (where if where is not None
                                else self.file_name, gcc_txt))

    def _python_tracer(self, frame, event, arg):
        """RETURN: function, this tracer, to continue line tracing.

        Emits the executed source line for frames compiled from the
        pype script (matching code filename); foreign frames -- library
        calls, user functions defined elsewhere -- pass silently.
        """
        code_file = frame.f_code.co_filename
        if event == "line" and code_file in self.source_db:
            line_list = self.source_db[code_file]
            index = frame.f_lineno - 1
            if 0 <= index < len(line_list):
                source = line_list[index].strip()
            else:
                source = "?"
            self.trace("%s:%d" % (code_file, frame.f_lineno),
                       "py: %s" % source,
                       "        py %d: %s" % (frame.f_lineno, source))
        return self._python_tracer

    def _check_mode_name(self, mode_name, verb):
        """RETURN: None, if 'mode_name' names an enterable mode.
                   Raises PypeError, else.
        """
        if mode_name == DEFAULT_MODE:
            raise PypeError("%s('%s'): the default mode cannot be entered"
                            % (verb, mode_name))
        if mode_name not in self.mode_db:
            raise PypeError("%s('%s'): no such mode" % (verb, mode_name))

    def request_switch(self, mode_name):
        """RETURN: None. Records a mode switch; applied after the current
                         handler's blocks have completed. The last
                         request wins.

        The default mode has no name; once left it cannot be entered
        again (a stacked return via 'pop' can).
        """
        self._check_mode_name(mode_name, "pype.goto")
        self.request = ("switch", mode_name)

    def request_push(self, mode_name):
        """RETURN: None. Records a stack push: the active mode is
                         remembered, 'mode_name' is activated; applied
                         after the current handler's blocks.
        """
        self._check_mode_name(mode_name, "pype.push")
        self.request = ("push", mode_name)

    def request_pop(self):
        """RETURN: None. Records a stack pop: the most recently pushed-
                         from mode is re-activated; applied after the
                         current handler's blocks.
        """
        self.request = ("pop",)

    def fire(self, handler):
        """RETURN: None. Runs the handler's actions in definition order.

        '=> MODE', '=> PUSH MODE' and '=> POP' record requests exactly
        like 'mode()', 'push()' and 'pop()'; the last request wins and
        is applied by the caller. '=> FLUSH' emits the current input
        line unchanged on stdout.
        """
        for action in handler.action_list:
            if action.code is not None:
                if self.trace_style is not None:
                    sys.settrace(self._python_tracer)
                    try:     exec(action.code, self.namespace)
                    finally: sys.settrace(None)
                else:
                    exec(action.code, self.namespace)
            if action.flush_f:
                self.trace(handler.where, "effect: flush ;",
                           "        effect: flush ;")
                print(self.current_line)
            if action.next_mode is not None:
                self.trace(handler.where,
                           "effect: goto %s ;" % action.next_mode,
                           "        effect: goto %s ;" % action.next_mode)
                self.request_switch(action.next_mode)
            if action.push_mode is not None:
                self.trace(handler.where,
                           "effect: push %s ;" % action.push_mode,
                           "        effect: push %s ;" % action.push_mode)
                self.request_push(action.push_mode)
            if action.pop_f:
                self.trace(handler.where, "effect: pop ;",
                           "        effect: pop ;")
                self.request_pop()

    def transition(self, new_mode_name):
        """RETURN: None. Deactivates the active mode (its 'EXIT' handlers
                         fire) and activates 'new_mode_name' (its 'ENTRY'
                         handlers fire). Activating a mode without an
                         'else' handler in its effective list is an
                         error.
        """
        if self.active is not None:
            for handler in self.active.handlers("exit"):
                self.trace(handler.where,
                           "fire: %s/on: <exit>" % self.active.name,
                           "    fire %s/on: <exit>   (%s)"
                           % (self.active.name, handler.where))
                self.fire(handler)
        self.active = self.mode_db.get(new_mode_name)
        if self.active is not None:
            self.trace(None, "mode active: %s" % self.active.name,
                       "mode active: %s" % self.active.name)
            if not self.active.handlers("else"):
                raise PypeError("mode '%s' cannot be activated: no <else> "
                                "handler in its effective list"
                                % self.active.name)
            for handler in self.active.handlers("entry"):
                self.trace(handler.where,
                           "fire: %s/on: <entry>" % self.active.name,
                           "    fire %s/on: <entry>   (%s)"
                           % (self.active.name, handler.where))
                self.fire(handler)

    def apply_pending_request(self):
        """RETURN: None. Performs a requested switch, push or pop, if
                         any. A switch to the already-active mode is a
                         no-operation; 'pop' with an empty stack is an
                         error.
        """
        request, self.request = self.request, None
        if request is None: return
        if request[0] == "switch":
            if request[1] != self.active.name:
                self.transition(request[1])
        elif request[0] == "push":
            self.stack.append(self.active.name)
            self.transition(request[1])
        else:                                            # pop
            if not self.stack:
                raise PypeError("pop with empty mode stack")
            self.transition(self.stack.pop())

    def feed(self, line):
        """RETURN: None. Dispatches one input line (without newline) to
                         the first matching handler of the active mode.

        A pattern cause fires on a matching line; an 'if(...)' cause
        fires when its condition evaluates true. If every match handler
        fails, the first 'else' handler of the effective list fires.
        """
        self.current_line     = line
        self.current_bindings = {}
        self.trace("%s:%d" % (self.input_name, self.input_line_n),
                   "input: %r" % line,
                   "[%d] %r" % (self.current_line_n, line))
        gate_verdict = None            # None: not evaluated; else bool
        gate_id_set  = self.active.gate_id_set
        for handler in self.active.handlers("match"):
            if handler.condition is not None:
                if not eval(handler.condition, self.namespace): continue
            else:
                if id(handler) in gate_id_set:
                    if gate_verdict is None:
                        gate_verdict = \
                            self.active.gate_regex.search(line) is not None
                    if not gate_verdict: continue
                binding_db = handler.pattern.search(line)
                if binding_db is None: continue
                self.current_bindings = binding_db
                self.namespace.update(binding_db)
                if binding_db:
                    self.trace(handler.where,
                               "bindings: %s" % sorted(binding_db.items()),
                               "    bindings: %s"
                               % sorted(binding_db.items()))
            self.trace(handler.where,
                       "fire: %s/on: %s"
                       % (self.active.name, handler.cause_txt),
                       "    fire %s/on: %s   (%s)"
                       % (self.active.name, handler.cause_txt,
                          handler.where))
            self.fire(handler)
            self.apply_pending_request()
            return
        for handler in self.active.handlers("else"):
            self.trace(handler.where,
                       "fire: %s/on: <else>" % self.active.name,
                       "    fire %s/on: <else>   (%s)"
                       % (self.active.name, handler.where))
            self.fire(handler)
            self.apply_pending_request()
            return
        self.trace("%s:%d" % (self.input_name, self.input_line_n),
                   "(no handler fired)", "    (no handler fired)")

    def run(self, line_iterable):
        """RETURN: None. Runs the whole stream: activates the start mode,
                         fires 'BOF' of the active mode, feeds every
                         line, fires 'EOF' of the active mode, and
                         deactivates.

        Runtime information is available through the 'pype' object:
        'pype.line()', 'pype.line_n()', 'pype.time()', and so on.
        """
        self.start_time = _monotonic()
        self.transition(self.start_mode_name)
        self.apply_pending_request()
        for handler in self.active.handlers("bof"):
            self.trace(handler.where, "fire: %s/on: <bof>" % self.active.name,
                       "    fire %s/on: <bof>   (%s)"
                       % (self.active.name, handler.where))
            self.fire(handler)
        self.apply_pending_request()
        for line in line_iterable:
            self.current_line_n += 1
            if self.input_name == "<stdin>":
                self.input_line_n = self.current_line_n
            self.feed(line.rstrip("\n"))
        for handler in self.active.handlers("eof"):
            self.trace(handler.where, "fire: %s/on: <eof>" % self.active.name,
                       "    fire %s/on: <eof>   (%s)"
                       % (self.active.name, handler.where))
            self.fire(handler)
        self.apply_pending_request()
        self.transition(None)


def _sample_of_token_list(token_list, counter_db):
    """RETURN: str, a line that matches the pattern built from
                    'token_list'.

    Deterministic sample values: integers count 1, 2, 3, ...; numbers
    count 1.5, 2.5, ...; in a glob '*' becomes 'sample' and '?' becomes
    'x'. '<bol>'/'<eol>' produce nothing. A repeat group is sampled with
    one repetition. 'counter_db' carries the counters across calls.
    """
    part_list = []
    for token in token_list:
        if token[0] == "const":
            part_list.append(token[1])
        elif token[0] == "int":
            counter_db["int"] += 1
            part_list.append(str(counter_db["int"]))
        elif token[0] == "number":
            counter_db["number"] += 1
            part_list.append("%.1f" % (counter_db["number"] + 0.5))
        elif token[0] == "glob":
            part = []
            for element in parse_glob(token[1]):
                if   element[0] == "star": part.append("sample")
                elif element[0] == "any":  part.append("x")
                elif element[0] == "char": part.append(element[1])
                elif element[1]:                     # negated set
                    part.append(next(
                        c for c in "abcdefghijklmnopqrstuvwxyz0123456789"
                        if c not in element[2]))
                else:
                    part.append(min(element[2]))
            part_list.append("".join(part))
        elif token[0] in ("bol", "eol"):
            pass
        else:                                            # repeat
            part_list.append(_sample_of_token_list(token[2], counter_db))
    return " ".join(p for p in part_list if p)


def generate_example_input(mode_db, start_mode_name):
    """RETURN: list, input lines that trigger the script's handlers when
                     fed on stdin.

    Walks the modes along statically visible switch actions ('=> MODE',
    'and: MODE'), starting at the start mode. Per mode it emits one
    sample line for every not-yet-sampled non-switching match handler,
    then one line for a switching handler leading to an unvisited mode,
    and continues there. Handlers whose only action is IGNORE produce no
    line. Switches requested by 'mode()' calls inside Python blocks are
    invisible to this walk; modes reachable only that way are not
    visited.
    """
    line_list  = []
    sampled_id = set()
    visited    = set()
    counter_db = {"int": 0, "number": 0}
    current    = start_mode_name

    def static_target(handler):
        """RETURN: str, the last statically visible switch or push target
                        of the handler's actions.
                   None, if the handler has neither.
        """
        target = None
        for action in handler.action_list:
            if action.next_mode is not None: target = action.next_mode
            if action.push_mode is not None: target = action.push_mode
        return target

    while current is not None:
        visited.add(current)
        switch_handler = None
        for handler in mode_db[current].handlers("match"):
            target = static_target(handler)
            if target is not None:
                if switch_handler is None and target not in visited:
                    switch_handler = handler
                continue                       # switching: not mid-section
            if id(handler) in sampled_id:
                continue                       # inherited, already sampled
            sampled_id.add(id(handler))
            if handler.condition is not None:
                continue                       # 'if' cause: no pattern
            if all(a.code is None for a in handler.action_list):
                continue                       # pure IGNORE: nothing to see
            line_list.append(_sample_of_token_list(handler.token_list,
                                                   counter_db))
        if switch_handler is None:
            current = None
        else:
            sampled_id.add(id(switch_handler))
            line_list.append(_sample_of_token_list(switch_handler.token_list,
                                                   counter_db))
            current = static_target(switch_handler)
    return line_list


def main(argv=None, stream=None):
    """RETURN: int, 0 if the script ran to completion.
                    1, else.

    'argv[1]' names the pype script; 'stream' (default: stdin) provides the
    input lines. Suitable as a she-bang interpreter: the kernel passes the
    script path as first argument, the piped data arrives on stdin.

    'hwut.pype --example SCRIPT' prints a generated example input for the
    script on stdout instead of running it. 'hwut.pype --dry-run SCRIPT'
    parses and checks the script (syntax, inheritance, interference,
    mandatory ELSE) without reading any input. '--pype-dir DIR' (may
    appear multiple times) adds import search directories. Bare
    arguments before the final SCRIPT argument are trace mode-name
    filters for '--trace'/'--trace-plain'. 'sys.exit(n)' inside a
    Python block terminates immediately with exit status n.
    """
    argv      = argv if argv is not None else sys.argv
    stream    = stream if stream is not None else sys.stdin
    flag_db   = {"--example": False, "--dry-run": False,
                 "--trace": False, "--trace-plain": False}
    search_dir_list = []
    rest = []
    k = 1
    while k < len(argv):
        if argv[k] in flag_db:
            flag_db[argv[k]] = True
        elif argv[k] == "--pype-dir":
            if k + 1 >= len(argv):
                print("pype: --pype-dir requires a directory",
                      file=sys.stderr)
                return 1
            search_dir_list.append(argv[k + 1])
            k += 1
        else:
            rest.append(argv[k])
        k += 1
    script_index = next((k for k, a in enumerate(rest)
                         if os.path.isfile(a)), len(rest) - 1)
    trace_filter    = rest[:script_index]
    input_path_list = rest[script_index + 1:]
    argv = argv[:1] + rest[script_index:script_index + 1]
    example_f   = flag_db["--example"]
    dry_run_f   = flag_db["--dry-run"]
    if   flag_db["--trace-plain"]: trace_style = "plain"
    elif flag_db["--trace"]:       trace_style = "gcc"
    else:                          trace_style = None
    if trace_filter and trace_style is None:
        print("pype: mode-name filters require --trace or --trace-plain",
              file=sys.stderr)
        return 1
    trace_filter = [DEFAULT_MODE if name == "default" else name
                    for name in trace_filter]
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("usage: hwut.pype [--trace] SCRIPT < input\n"
              "       hwut.pype --example SCRIPT   "
              "(print generated example input)\n"
              "       hwut.pype --dry-run SCRIPT   "
              "(check the script, read no input)\n"
              "       --trace: show, on stderr, input lines against the\n"
              "                handlers they trigger, and the executed\n"
              "                lines inside python blocks; gcc-style\n"
              "                'file:line:' prefixes\n"
              "       --trace-plain: the same trace with a plain\n"
              "                'TRACE|' line starter instead\n"
              "       SCRIPT may be followed by INPUT-FILE arguments,\n"
              "       read in order as one stream instead of stdin",
              file=sys.stderr)
        return 1
    file_name = argv[1]
    try:
        with open(file_name, "r") as fh:
            source_txt = fh.read()
        source_db = {}
        mode_db, start_mode_name = parse(source_txt, file_name,
                                         search_dir_list=search_dir_list,
                                         source_db=source_db)
        if dry_run_f:
            handler_n = sum(len(m.handler_list) for m in mode_db.values())
            print("dry run ok: %d mode(s), %d handler(s)"
                  % (len(mode_db), handler_n))
        elif example_f:
            for line in generate_example_input(mode_db, start_mode_name):
                print(line)
        else:
            interpreter = Interpreter(mode_db, start_mode_name, file_name,
                                      trace_style=trace_style,
                                      source_db=source_db,
                                      trace_filter=trace_filter)
            if input_path_list:
                def file_lines(itp, path_list):
                    """RETURN: iterator over the lines of the files of
                                'path_list', in order, as one stream;
                                'itp.input_name'/'itp.input_line_n'
                                follow the per-file position.
                    """
                    for path in path_list:
                        itp.input_name   = path
                        itp.input_line_n = 0
                        with open(path, "r") as fh:
                            for line in fh:
                                itp.input_line_n += 1
                                yield line
                interpreter.run(file_lines(interpreter, input_path_list))
            else:
                interpreter.run(stream)
    except PypeError as error:
        print("pype: %s" % error, file=sys.stderr)
        return 1
    except OSError as error:
        print("pype: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
