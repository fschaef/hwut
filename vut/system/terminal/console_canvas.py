from   .cell                     import Cell
import vut.external.colorama     as     colorama
import vut.system.terminal_size  as     terminal_size
from   typeguard                 import typechecked

class ConsoleCanvas:
   """Base class for color-rending text on the console.
   """
   def __init__(self):
       self.height, self.width = terminal_size.get()
       self.height = int(self.height)
       self.width  = int(self.width)
       colorama.init()

   def print_line(self, line, newline_f=True):
       if newline_f: print(line + _color_reset_all)
       else:         print(line + _color_reset_all, end="", flush=True)

   @typechecked
   def render(self, cell_list=list[Cell]) -> str:
       """RETURNS: (possibly colored) string ready to be displayed on 
                   ASCII terminal.
       """
       return "".join(cell.render() for cell in cell_list)

