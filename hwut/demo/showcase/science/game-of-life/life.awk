# life.awk -- Conway's Game of Life, any rule 'Bxx/Sxx', or 'xx/yy' in the
# older survival/birth notation ('23/3' = B3/S23).
# usage: awk -v rule=B3/S23 -v gens=4 -f grid_torus.awk -f life.awk start.txt
#   the grid file defines alive(r, c), the topology of the board.
# input: rows of '.' (dead) and 'O' (alive); output: 'gen k' and the rows, k = 0..gens.
BEGIN {
    r = rule
    if (r ~ /^[0-9]*\/[0-9]*$/) { split(r, part, "/"); r = "B" part[2] "/S" part[1] }   # '23/3' -> 'B3/S23'
    split(r, part, "/")
    for (i = 2; i <= length(part[1]); ++i) born[substr(part[1], i, 1)] = 1
    for (i = 2; i <= length(part[2]); ++i) stay[substr(part[2], i, 1)] = 1
}
{ H = NR; W = length($0); for (c = 1; c <= W; ++c) cell[NR, c] = substr($0, c, 1) == "O" }
END {
    for (g = 0; g <= gens; ++g) {
        print "gen " g
        for (y = 1; y <= H; ++y) { row = ""; for (x = 1; x <= W; ++x) row = row (cell[y, x] ? "O" : "."); print row }
        for (y = 1; y <= H; ++y) for (x = 1; x <= W; ++x) {
            n = 0
            for (dy = -1; dy <= 1; ++dy) for (dx = -1; dx <= 1; ++dx) if (dy || dx) n += alive(y + dy, x + dx)
            next_cell[y, x] = cell[y, x] ? (n in stay) : (n in born)
        }
        for (y = 1; y <= H; ++y) for (x = 1; x <= W; ++x) cell[y, x] = next_cell[y, x]
    }
}
