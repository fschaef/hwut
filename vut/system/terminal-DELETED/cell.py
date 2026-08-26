from   vut.system.terminal.styled_text import ColorText, ColorTextList, E_Alignment, CellFormat

from   dataclasses import dataclass
from   typeguard   import typechecked
from   abc         import ABC, abstractmethod

@dataclass
class Cell(ABC):
    format: CellFormat

    def render(self):
        ct_list   = self._color_text_list()
        formatted = ct_list.format(self.format)
        return formatted.render(self.format.color_code)

    @abstractmethod
    def _color_text_list(self):
        raise NotImplementedError

@dataclass
class StaticCell(Cell):
    """
    Cell whose appearance is fully defined by intrinsic text.
    """
    content: str

    def _color_text_list(self) -> ColorTextList:
        return ColorTextList([ColorText(None, self.content)])

@dataclass
class ContentCell(Cell):
    """
    Cell whose content is supplied dynamically.
    """
    ct_list: ColorTextList

    def _color_text_list(self) -> ColorTextList:
        return ct_list
