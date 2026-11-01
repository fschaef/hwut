# grid_torus.awk -- the board wraps: row 0 is row H, column 0 is column W.
function alive(y, x) { return cell[(y - 1 + H) % H + 1, (x - 1 + W) % W + 1] }
