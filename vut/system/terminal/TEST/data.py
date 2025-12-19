from     vut.system.terminal.core import LEFT, RIGHT, FIXED, CellFormat

l00 = LEFT(0,    "Gw", 0)
l01 = LEFT(0,    "Gw", 1)
l10 = LEFT(1,    "Gw", 1)
l11 = LEFT(1,    "Gw", 0)

r00 = RIGHT(0,   "Rw", 0)
r01 = RIGHT(0,   "Rw", 1)
r10 = RIGHT(1,   "Rw", 1)
r11 = RIGHT(1,   "Rw", 0)

## c00 = CENTER(0,  "Bw", 0)
## c01 = CENTER(0,  "Bw", 1)
## c11 = CENTER(1,  "Bw", 1)
## c10 = CENTER(1,  "Bw", 0)

f0  = FIXED("",  "By", 0)
fa0 = FIXED("a", "By", 0)
fa1 = FIXED("a", "By", 1)

## g0  = GLUE("-",  "Ry", 0)
## g1  = GLUE("-.", "Ry", 1)

## fe_non_fix_list = [ l00, l01, l10, l11, r00, r01, r10, r11 ]
## fe_fix_list     = [ c00, c01, c10, c11, f0,  fa0, fa1, g0, g1 ]
fe_non_fix_list = [ l00, l01, l10, l11, r00, r01, r10, r11 ]
fe_fix_list     = [ f0,  fa0, fa1 ]
fe_list         = fe_non_fix_list + fe_fix_list

width_list      = [ 0, 1, 2 ]
content_list    = [ "", "a", "ab" ]
