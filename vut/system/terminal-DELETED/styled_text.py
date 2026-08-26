from  dataclasses import dataclass
from  typing      import Iterable, List, Optional
from  typeguard   import typechecked
from  enum        import Enum, auto

RESET_BG  = "\033[49m"
RESET_ALL = "\033[0m"

class E_Alignment(Enum):
    LEFT  = auto()
    RIGHT = auto()
    ## CENTER = auto()

@dataclass(frozen=True)
class CellFormat:
    """Layout Specification of a Cell.

    A CellFormat describes *how* content is rendered. It defines width, 
    alignment, default foreground color, and a logical text offset.
    """

    width: int
    """Target width of the cell in character columns.

    Width is enforced after applying text_offset and before alignment padding.
    A width of zero produces an empty cell.
    """

    alignment: E_Alignment
    """Horizontal alignment of the content within the cell.

    Alignment is applied after width truncation and determines how padding
    is distributed when the content is shorter than the target width.
    """

    color_code: str
    """Default ANSI foreground color code for the cell content.

    This color is applied to all text fragments that do not explicitly
    override their foreground color. Background colors must not be encoded
    here, as background handling is controlled by the layout phase.
    """

    text_offset: int = 0
    """Logical horizontal offset applied to the content before layout.

    Positive values skip characters from the beginning of the content
    (left-side clipping / horizontal scrolling).

    Negative values shift the content to the right by inserting leading
    space.

    The offset is applied before width truncation, alignment, and padding.
    """


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
    def from_str_list(cls, str_list: Iterable[str]) -> "ColorTextList":
        return cls(ColorText(None, s) for s in str_list)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return sum(len(ct) for ct in self._items)


    def prepare_offset(self, text_offset: int) -> "ColorTextList":
        if text_offset > 0:
            return self.prune_begin(text_offset)
        elif text_offset < 0:
            return ColorTextList([ColorText(None, " " * -text_offset), *self._items])
        else:
            return self

    def prune(self, total_length, width, alignment):
        cut_n = total_length - width
        if   cut_n <= 0:                     return self
        elif alignment == E_Alignment.RIGHT: return self.prune_begin(cut_n)
        else:                                return self.prune_end(total_length - cut_n)

    def prune_begin(self, cut_n: int) -> "ColorTextList":
        assert cut_n > 0

        def _iter(cut_n):
            remaining = cut_n
            for ct in self:
                if remaining <= 0:
                    yield ct
                elif len(ct.text) > remaining:
                    yield ColorText(ct.color, ct.text[remaining:])
                    remaining = 0
                else:
                    remaining -= len(ct.text)

        return ColorTextList(_iter(cut_n))

    def prune_end(self, remaining_n: int) -> "ColorTextList":
        """YIELDS: Colored text.

        Considers list of tuples (color, text) and cuts of 'cut_n' characters
        from the back of the text.
        """
        def _iter(remaining):
            for ct in self:
                if remaining <= 0:
                    break
                elif len(ct.text) <= remaining:
                    yield ct
                    remaining -= len(ct.text)
                else:
                    yield ColorText(ct.color, ct.text[:remaining])
                    break

        return ColorTextList(_iter(remaining_n))

    @typechecked
    def padding(self, cf: CellFormat, total_length: int) -> "ColorTextList":
        add_n = cf.width - total_length
        if add_n <= 0: return self

        pad = ColorText(None, " " * add_n)
        if cf.alignment == E_Alignment.RIGHT: return ColorTextList([pad, *self._items])
        else:                                 return ColorTextList([*self._items, pad])

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

    def format(self, cf: CellFormat):
        """RETURNS: Colored, formatted text.
            
        Formats cell according to format expression and the text provided as tuples
        (color, text). Right aligned text is pruned from left, and vice versa.
        """
        result       = self.prepare_offset(cf.text_offset)
        total_length = sum(len(ct.text) for ct in result)
        result       = result.prune(total_length, cf.width, cf.alignment)
        total_length = sum(len(ct.text) for ct in result)

        return result.padding(cf, total_length)

