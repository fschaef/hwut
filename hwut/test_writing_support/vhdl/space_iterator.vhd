-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
--          'python/space_iterator.py', in VHDL alone: the cartesian product,
--          the RIGHTMOST dimension changing fastest. A VHDL vector holds one
--          type, a basis of mixed values none: the iterator yields INDICES,
--          one per dimension, into the caller's own value arrays.
--
--     constant x    : integer_vector := (0, 2, 4);
--     constant name : str_list       := "otto" & LF & "heinz" & LF;
--     variable it   : SpaceIterator;
--     it.do((3, 2));                               -- the lengths of the basis
--     while it.next_point loop
--         run_test(x(it.point(0)), item(name, it.point(1)));
--     end loop;
--
-- An empty basis ('do' given a null vector) yields exactly one point, the
-- empty one; a basis with an empty dimension yields nothing -- as
-- 'itertools.product'.
-- _____________________________________________________________________________
package space_iterator is
    constant SPACE_ITERATOR_DIMENSION_MAX : positive := 32;

    type SpaceIterator is protected
        procedure do(size : integer_vector);
        impure function next_point return boolean;
        impure function point return integer_vector;
    end protected;
end package;

package body space_iterator is
    type SpaceIterator is protected body
        variable dimension_size : integer_vector(0 to SPACE_ITERATOR_DIMENSION_MAX - 1);
        variable index          : integer_vector(0 to SPACE_ITERATOR_DIMENSION_MAX - 1);
        variable dimension_n    : natural := 0;
        variable started_f      : boolean := false;
        variable done_f         : boolean := true;

        procedure do(size : integer_vector) is
            -- RETURN: nothing; the iterator stands before the first point of
            --         the basis whose dimensions have the lengths 'size'.
        begin
            assert size'length <= SPACE_ITERATOR_DIMENSION_MAX severity failure;
            dimension_n := size'length;
            for i in 0 to size'length - 1 loop
                dimension_size(i) := size(size'left + i);
                index(i)          := 0;
            end loop;
            started_f := false;
            done_f    := false;
        end procedure;

        impure function next_point return boolean is
            -- RETURN: true, 'point' is the next point of the product; false,
            --         every point was yielded (or none is: a dimension is
            --         empty).
        begin
            if done_f then return false; end if;
            if not started_f then
                started_f := true;
                for i in 0 to dimension_n - 1 loop
                    if dimension_size(i) = 0 then done_f := true; return false; end if;
                end loop;
                return true;
            end if;
            for i in dimension_n - 1 downto 0 loop
                index(i) := index(i) + 1;
                if index(i) < dimension_size(i) then return true; end if;
                index(i) := 0;
            end loop;
            done_f := true;
            return false;
        end function;

        impure function point return integer_vector is
            -- RETURN: integer_vector, the point 'next_point' stepped to -- one
            --         index per dimension, (0 to dimension_n - 1).
            variable result : integer_vector(0 to dimension_n - 1);
        begin
            for i in result'range loop result(i) := index(i); end loop;
            return result;
        end function;
    end protected body;
end package body;
