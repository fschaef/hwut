# grid_bounded.awk -- the board ends at its edge: outside is dead.
function alive(y, x) { return y >= 1 && y <= H && x >= 1 && x <= W ? cell[y, x] : 0 }
