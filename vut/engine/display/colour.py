"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE COLOUR VOCABULARY -- a colour as a person writes it, turned
         into what a terminal or 'prompt_toolkit' draws (services E-78).

DESCRIPTION
       A COLOUR is a string of words, applied left to right:

           red green yellow blue magenta cyan white black
                                     the foreground; 'bright-' before any
           bg-<name>                 the background; 'bg-bright-<name>'
           c256:N  bg256:N           a 256-colour palette entry
           #rrggbb bg#rrggbb         a true colour
           bold dim italic underline reverse
           none                      nothing at all (also: an empty string)

       WHO READS A PREFERENCE FILE is 'services/lib/preferences.py';
       this module knows no file. The engine's own ink paints its
       defaults through it, a face paints the person's choice through
       it: one vocabulary, whoever chose the word (services E-82).
______________________________________________________________________________
"""
#  compare's element kinds (E_ToleranceId names) -> their colour role.
ELEMENT_ROLE_DB = {
    "STRING":              "element.string",
    "SEPERATOR":           "element.separator",
    "NUMERIC":             "element.numeric",
    "ANALOGY":             "element.analogy",
    "EQUIVALENCE_PATTERN": "element.pattern",
    "CONSTRAINT_BINDING":  "element.binding",
    "VISIBLE_NOTHING":     "element.nothing",
}

_BASIC_TUPLE = ("black", "red", "green", "yellow", "blue", "magenta",
                "cyan", "white")
_ATTRIBUTE_DB = {"bold": "1", "dim": "2", "italic": "3", "underline": "4",
                 "reverse": "7"}


def word_list_valid(text):
    """RETURN: str, the first word of colour 'text' that the vocabulary
               does not know.
               None, where every word is known."""
    for word in _words(text):
        if _sgr_of_word(word) is None: return word
    return None


def sgr(color):
    """RETURN: str, colour 'color' as an ANSI SGR parameter string, e.g.
               '1;36' -- ready for '\\x1b[%sm'.
               '', where the colour says nothing ('none', empty)."""
    return ";".join(code for code in (_sgr_of_word(w) for w in _words(color))
                    if code)


def paint(text, color):
    """RETURN: str, 'text' wrapped in the SGR of 'color' and a reset.
               'text' unchanged, where the colour says nothing."""
    code = sgr(color)
    return "\x1b[%sm%s\x1b[0m" % (code, text) if code else text


def toolkit_style(color):
    """RETURN: str, colour 'color' as a 'prompt_toolkit' style string,
               e.g. 'bg:#2e3b32 #a9b8ad italic'.
               '', where the colour says nothing."""
    piece_list = []
    for word in _words(color):
        kind, bg_f, value = _parsed(word)
        if kind is None: continue
        if kind == "attribute":
            #  'prompt_toolkit' knows no 'dim': a grey pen says the same.
            piece_list.append("#888888" if value == "dim" else value)
            continue
        if   kind == "hex":    name = value
        elif kind == "c256":   name = _hex_of_256(value)
        elif kind == "bright":
            #  'prompt_toolkit' spells the bright white 'ansiwhite' and
            #  the plain one 'ansigray' -- MEASURED: 'ansibrightwhite'
            #  is refused as no colour at all.
            name = "ansiwhite" if value == "white" else "ansibright" + value
        else:
            name = "ansigray" if value == "white" else "ansi" + value
        piece_list.append(("bg:" + name) if bg_f else name)
    return " ".join(piece_list)


def _words(color):
    """RETURN: list[str], the words of colour 'color'; 'none' says
               nothing and yields none."""
    return [w for w in (color or "").split() if w != "none"]


def _sgr_of_word(word):
    """RETURN: str, the SGR parameter(s) of one colour word.
               None, where the word is not in the vocabulary."""
    kind, bg_f, value = _parsed(word)
    if kind is None:        return None
    if kind == "attribute": return _ATTRIBUTE_DB[value]
    if kind == "hex":
        r, g, b = (int(value[i:i+2], 16) for i in (1, 3, 5))
        return "%i;2;%i;%i;%i" % (48 if bg_f else 38, r, g, b)
    if kind == "c256":      return "%i;5;%i" % (48 if bg_f else 38, value)
    base = 40 if bg_f else 30
    if kind == "bright":    base += 60
    return str(base + _BASIC_TUPLE.index(value))


def _parsed(word):
    """RETURN: (kind, bg_f, value), one colour word read:
                   ('attribute', False, 'bold')
                   ('basic',     bg_f,  'red')
                   ('bright',    bg_f,  'red')
                   ('c256',      bg_f,  208)
                   ('hex',       bg_f,  '#rrggbb')
               (None, False, None), where the word is not in the
               vocabulary."""
    unknown = (None, False, None)
    if word in _ATTRIBUTE_DB: return ("attribute", False, word)
    bg_f, name = False, word
    if   word.startswith("bg-"):  bg_f, name = True, word[3:]
    elif word.startswith("bg#"):  bg_f, name = True, word[2:]
    elif word.startswith("bg256:"): bg_f, name = True, "c" + word[2:]
    if name.startswith("#"):
        if len(name) != 7: return unknown
        try:               int(name[1:], 16)
        except ValueError: return unknown
        return ("hex", bg_f, name.lower())
    if name.startswith("c256:"):
        try:               n = int(name[5:])
        except ValueError: return unknown
        return ("c256", bg_f, n) if 0 <= n <= 255 else unknown
    if name.startswith("bright-") and name[7:] in _BASIC_TUPLE:
        return ("bright", bg_f, name[7:])
    if name in _BASIC_TUPLE: return ("basic", bg_f, name)
    return unknown


def _hex_of_256(n):
    """RETURN: str, '#rrggbb' of xterm palette entry 'n'."""
    basic = ("000000", "800000", "008000", "808000", "000080", "800080",
             "008080", "c0c0c0", "808080", "ff0000", "00ff00", "ffff00",
             "0000ff", "ff00ff", "00ffff", "ffffff")
    if n < 16: return "#" + basic[n]
    if n < 232:
        n -= 16
        level = (0, 95, 135, 175, 215, 255)
        return "#%02x%02x%02x" % (level[n // 36], level[(n // 6) % 6],
                                  level[n % 6])
    grey = 8 + 10 * (n - 232)
    return "#%02x%02x%02x" % (grey, grey, grey)
