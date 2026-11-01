// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
//          'python/space_iterator.py' ('do(basis)'): the cartesian product,
//          the RIGHTMOST dimension changing fastest.
//
//     import space_iterator::*;
//     dimension_t   x = '{"0", "2", "4"}, name = '{"otto", "heinz"};
//     basis_t       basis = {};
//     basis.push_back(x); basis.push_back(name);   -- a nested '{...} Verilator 5.020 refuses
//     SpaceIterator it = SpaceIterator::do_(basis);  -- 'do' is a keyword
//     string        point[$] = {};
//     while (it.next_point(point)) run_test(point[0].atoi(), point[1]);
//
// A basis of other values is given by its SIZES; the iterator then yields
// INDICES, one per dimension, into the caller's own lists:
//
//     SpaceIterator it = new('{3, 2});
//     int           at[$];
//     while (it.next(at)) run_test(x[at[0]], name[at[1]]);
//
// An empty basis yields exactly one point, the empty one; a basis with an
// empty dimension yields nothing -- as 'itertools.product'. No generator in
// SystemVerilog: the iterator is an object, 'next' its step.
// _____________________________________________________________________________
package space_iterator;

    typedef string dimension_t[$];
    typedef dimension_t basis_t[$];

    class SpaceIterator;
        int     size_list[$];
        int     index[$];
        bit     done_f;
        basis_t basis;              // where the iterator was made of values

        function new(int size_list[$]);
            // RETURN: an iterator standing before the first point of the
            //         basis whose dimensions hold 'size_list' values each.
            this.size_list = size_list;
            index  = {};
            done_f = 0;
            foreach (size_list[i]) begin
                index.push_back(0);
                if (size_list[i] == 0) done_f = 1;           // an empty dimension
            end
        endfunction

        static function SpaceIterator do_(basis_t basis);
            // RETURN: an iterator over the values of 'basis' ('next_point'),
            //         standing before the first point.
            int           size_list[$] = {};
            SpaceIterator it;
            foreach (basis[i]) size_list.push_back(basis[i].size());
            it       = new(size_list);
            it.basis = basis;
            return it;
        endfunction

        function bit next(ref int at[$]);
            // RETURN: 1, 'at' holds the next point -- one index per
            //         dimension; 0, every point was given.
            if (done_f) return 0;
            at = index;
            // THE ODOMETER: the rightmost index steps; one that wraps carries left.
            for (int i = size_list.size(); i > 0; i--) begin
                index[i - 1] += 1;
                if (index[i - 1] < size_list[i - 1]) return 1;
                index[i - 1] = 0;
            end
            done_f = 1;
            return 1;
        endfunction

        function bit next_point(ref string point[$]);
            // RETURN: 1, 'point' holds the next point's values, one per
            //         dimension (an iterator made by 'do_'); 0, every point
            //         was given.
            int at[$] = {};
            point = {};
            if (!next(at)) return 0;
            foreach (at[i]) point.push_back(basis[i][at[i]]);
            return 1;
        endfunction
    endclass

endpackage
