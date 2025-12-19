from  dataclasses import dataclass
from  typing      import Iterable, List, Optional
from  typeguard   import typechecked
from  enum        import Enum, auto
from  collections import namedtuple

RESET_BG  = "\033[49m"
RESET_ALL = "\033[0m"

class E_Alignment(Enum):
    LEFT  = auto()
    RIGHT = auto()

# Format Expression: 'FE'
CellFormat = namedtuple("CellFormat", ("alignment", "color_code", "width", "string", "text_offset"))

@dataclass(frozen=True)
class ColorText:
    color: Optional[str]   # foreground ANSI code, None = default
    text:  str

    def __post_init__(self):
        assert type(self.text) is str
        assert self.color is None or type(self.color) is str

    def __len__(self) -> int:
        return len(self.text)


class ColorTextList:
    """
    Semantic container for colored text fragments.
    No layout, no padding, no ANSI state leakage.
    """
    @typechecked
    def __init__(self, items: Iterable[ColorText]):
        self._items: List[ColorText] = [ct for ct in items if ct.text]

    @classmethod
    def from_str_list(cls, str_list: Iterable[str]):
        return cls(ColorText(None, s) for s in str_list)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return sum(len(ct) for ct in self._items)

    @typechecked
    def padding(self, fe: CellFormat, total_length):
        add_n = fe.width - total_length
        if add_n <= 0: return self

        if fe.alignment == E_Alignment.RIGHT: return self.with_padding_left(add_n)
        else:                                 return self.with_padding_right(add_n)

    def with_padding_left(self, n: int) -> "ColorTextList":
        if n <= 0:
            return self
        return ColorTextList([ColorText(None, " " * n), *self._items])

    def with_padding_right(self, n: int) -> "ColorTextList":
        if n <= 0:
            return self
        return ColorTextList([*self._items, ColorText(None, " " * n)])

    def prune(self, total_length, width, alignment):
        cut_n = total_length - width
        if   cut_n <= 0:                     return self
        elif alignment == E_Alignment.RIGHT: return self.prune_begin(cut_n)
        else:                                return self.prune_end(total_length - cut_n)

    def prune_begin(self, cut_n):
        """YIELDS: Colored text.

        Considers list of tuples (color, text) and cuts of 'cut_n' characters
        from the front of the text.
        """
        assert cut_n > 0

        def _iter(cut_n):
            flush_f = False
            for ct in self:
                if flush_f:
                    yield ct
                elif len(ct.text) >= cut_n:
                    yield ColorText(ct.color, ct.text[cut_n:])
                    flush_f = True
                else:
                    cut_n -= len(ct.text)

        return ColorTextList(_ for _ in _iter(cut_n))

    def prune_end(self, remaining_n):
        """YIELDS: Colored text.

        Considers list of tuples (color, text) and cuts of 'cut_n' characters
        from the back of the text.
        """
        def _iter(remaining_n):
            for ct in self:
                if len(ct.text) >= remaining_n:
                    yield ColorText(ct.color, ct.text[:remaining_n])
                    break
                remaining_n -= len(ct.text)
                yield ct

        return ColorTextList(_ for _ in _iter(remaining_n))

    def _prepare_offset(self, text_offset):
        """RETURNS: list of (color, string)

        where the string is adapted such that the text offset is prepared.
        """
        if text_offset > 0:
            return ColorTextList(self.prune_begin(text_offset))
        elif text_offset < 0:
            return ColorTextList([ColorText(None, " " * -text_offset), *ctl])
        else:
            return ctl

    def render(self, default_fg: str="") -> str:
        """
        Render safely to ANSI string.
        Background is always reset before content.
        """
        return "".join(
            part
            for ct in self._items
            for part in (RESET_BG, ct.color or default_fg, ct.text)
        ) + RESET_ALL
