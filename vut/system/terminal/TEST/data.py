from vut.system.terminal.core        import LEFT, RIGHT, FIXED
from vut.system.terminal.styled_text import CellFormat

l00 = LEFT(0, "Gw", 0)
l01 = LEFT(0, "Gw", 1)
l10 = LEFT(1, "Gw", 1)
l11 = LEFT(1, "Gw", 0)

r00 = RIGHT(0, "Rw", 0)
r01 = RIGHT(0, "Rw", 1)
r10 = RIGHT(1, "Rw", 1)
r11 = RIGHT(1, "Rw", 0)

format_list = [l00, l01, l10, l11, r00, r01, r10, r11]

# ---- static cells -------------------------------------------------------

f0  = FIXED("",  "By", 0)
fa0 = FIXED("a", "By", 0)
fa1 = FIXED("a", "By", 1)

cell_list = [f0, fa0, fa1]

# ---- generic test data --------------------------------------------------

width_list   = [0, 1, 2]
content_list = ["", "a", "ab"]
