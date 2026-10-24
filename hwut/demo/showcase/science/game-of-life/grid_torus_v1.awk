# grid_torus_v1.awk -- the first torus: '% W' wraps the right edge to the
# left; but awk's % keeps the sign, so column 0 maps to -1 + 1 = 0 -- a cell
# that does not exist (dead). The left and top edges do not wrap.
function alive(y, x) { return cell[(y - 1) % H + 1, (x - 1) % W + 1] }
