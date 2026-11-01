-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: PARSE THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE INTO THE
--          ANNOTATED TREE -- the port of 'python/hwut_hocon.py': every key,
--          every value and every block carries its file-relative position.
--          A THIN FACE over the C parser '../c/hwut_hocon.c' by VHPIDIRECT;
--          the tree it builds is handed over into VHDL's own records.
--
--     variable document : HoconNodeAccess;
--     variable faults   : HoconFaultVectorAccess;
--     parse("a = 1" & LF & "b = ""x""" & LF, "f.hocon", document, faults);
--     document.entry(0).key.all                  -- "a"
--     document.entry(0).node.value.all           -- "1"
--     for i in faults'range loop print(faults(i).text.all); end loop;
--     free(document); free(faults);
--
-- THE LINES are a str_list ('hwut_pytext'): every line ENDED by LF, line i
-- (from 0) numbered i + 1 + line_offset, every one 'column_offset' columns in
-- -- Python's list of SourceLine, the offsets applied uniformly.
--
-- THE SUBSET, word for word Python's: nested objects, lists, numbers in every
-- radix (with '_' as a visual helper, and roman '0rIV'), booleans
-- (true/false/yes/no), the spellings of nothing (null/nil/none/nihil), '#'
-- and '//' comments, '=' or ':' before a value, a brace directly after a key.
-- A STRING VALUE IS WRITTEN IN DOUBLE QUOTES; a text of several lines in
-- triple quotes. 'include', '${...}' and '+=' are refused by name. The parser
-- accumulates faults and recovers at the next line; it never fails.
--
-- A SCALAR'S VALUE is kept as Python prints it -- 'value_repr' (repr) and
-- 'type_name' ('str', 'int', 'float', 'bool', 'NoneType') -- and as a text,
-- 'value': a str as it stands, a number in its repr, 'True'/'False', 'None'.
-- VHDL's 32-bit integer holds no 0xDEAD_BEEF; the text holds every one.
-- A string of Python's str(fault) stands in 'text' -- a function cannot take
-- a record holding an access value, so it is made when the fault is.
-- _____________________________________________________________________________
use std.textio.all;
use work.hwut_vhpi.all;
use work.hwut_pytext.all;

package hwut_hocon is
    type HoconPosition is record
        line   : integer;
        column : integer;
    end record;
    function to_string(position : HoconPosition) return string;

    type HoconNodeKind is (HOCON_SCALAR, HOCON_LIST, HOCON_OBJECT);

    type HoconNode;
    type HoconNodeAccess is access HoconNode;
    type HoconNodeVector is array (natural range <>) of HoconNodeAccess;
    type HoconNodeVectorAccess is access HoconNodeVector;

    type HoconEntry is record
        key          : line;
        key_position : HoconPosition;
        node         : HoconNodeAccess;
    end record;
    type HoconEntryVector is array (natural range <>) of HoconEntry;
    type HoconEntryVectorAccess is access HoconEntryVector;

    type HoconNode is record
        kind       : HoconNodeKind;
        position   : HoconPosition;
        type_name  : line;                      -- Python's type of the value
        value_repr : line;                      -- a scalar's repr; "" else
        value      : line;                      -- a scalar's text;  "" else
        item       : HoconNodeVectorAccess;     -- a list's items
        entry      : HoconEntryVectorAccess;    -- an object's entries, in order
    end record;

    type HoconFaultKind is (HOCON_SYNTAX, HOCON_REFUSED);
    type HoconFault is record
        kind     : HoconFaultKind;
        file_name : line;
        position : HoconPosition;
        message  : line;
        text     : line;                        -- 'file:line:column: KIND: message'
    end record;
    type HoconFaultVector is array (natural range <>) of HoconFault;
    type HoconFaultVectorAccess is access HoconFaultVector;

    procedure parse(lines : str_list; file_name : string;
                    variable document : out HoconNodeAccess;
                    variable faults   : out HoconFaultVectorAccess;
                    line_offset   : integer := 0;
                    column_offset : integer := 0;
                    bound_us      : natural := 0);
    procedure get(variable node : inout HoconNodeAccess; key : string; variable found : out HoconNodeAccess);
    procedure free(variable node : inout HoconNodeAccess);
    procedure free(variable faults : inout HoconFaultVectorAccess);
    impure function cleandoc(text : string) return string;
end package;

package body hwut_hocon is
    impure function hwut_vhpi_hocon_parse(text : string; line_offset : integer; column_offset : integer;
                                          file_name : string; bound_us : integer) return integer;
    attribute foreign of hwut_vhpi_hocon_parse : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_parse";
    impure function hwut_vhpi_hocon_parse(text : string; line_offset : integer; column_offset : integer;
                                          file_name : string; bound_us : integer) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_hocon_root(h : integer) return integer;
    attribute foreign of hwut_vhpi_hocon_root : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_root";
    impure function hwut_vhpi_hocon_root(h : integer) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_hocon_free(h : integer);
    attribute foreign of hwut_vhpi_hocon_free : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_free";
    procedure hwut_vhpi_hocon_free(h : integer) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_hocon_fault_n(h : integer) return integer;
    attribute foreign of hwut_vhpi_hocon_fault_n : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_fault_n";
    impure function hwut_vhpi_hocon_fault_n(h : integer) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_hocon_fault(h : integer; i : integer);
    attribute foreign of hwut_vhpi_hocon_fault : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_fault";
    procedure hwut_vhpi_hocon_fault(h : integer; i : integer) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_hocon_node(h : integer);
    attribute foreign of hwut_vhpi_hocon_node : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_node";
    procedure hwut_vhpi_hocon_node(h : integer) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_hocon_item(h : integer; i : integer) return integer;
    attribute foreign of hwut_vhpi_hocon_item : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_item";
    impure function hwut_vhpi_hocon_item(h : integer; i : integer) return integer is
    begin assert false severity failure; return 0; end function;

    impure function hwut_vhpi_hocon_entry(h : integer; i : integer) return integer;
    attribute foreign of hwut_vhpi_hocon_entry : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_entry";
    impure function hwut_vhpi_hocon_entry(h : integer; i : integer) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_hocon_cleandoc(text : string);
    attribute foreign of hwut_vhpi_hocon_cleandoc : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_hocon_cleandoc";
    procedure hwut_vhpi_hocon_cleandoc(text : string) is begin assert false severity failure; end procedure;

    function to_string(position : HoconPosition) return string is
        -- RETURN: string, 'line:column' -- Python's str(Position).
    begin return integer'image(position.line) & ":" & integer'image(position.column); end function;

    function after_item(list : string; n : natural) return string is
        -- RETURN: string, what stands after the n-th LF of 'list' -- its
        --         last field, which may hold LFs of its own.
        variable k : natural := 0;
    begin
        for i in list'range loop
            if list(i) = LF then
                k := k + 1;
                if k = n then return list(i + 1 to list'right); end if;
            end if;
        end loop;
        return "";
    end function;

    procedure node_of(h : integer; variable node : out HoconNodeAccess) is
        -- RETURN: nothing; 'node' is a new VHDL tree of the C node 'h' and
        --         everything below it.
        variable n       : HoconNodeAccess;
        variable text    : line;
        variable count   : natural;
        variable child_h : integer;
    begin
        hwut_vhpi_hocon_node(h);
        text := new string'(result & LF);
        n    := new HoconNode;
        if    item(text.all, 0) = "object" then n.kind := HOCON_OBJECT;
        elsif item(text.all, 0) = "list"   then n.kind := HOCON_LIST;
        else                                     n.kind := HOCON_SCALAR;
        end if;
        n.position   := (integer'value(item(text.all, 1)), integer'value(item(text.all, 2)));
        count        := integer'value(item(text.all, 3));
        n.type_name  := new string'(item(text.all, 4));
        n.value_repr := new string'(item(text.all, 5));
        n.value      := new string'(after_item(text(text'left to text'right - 1), 6));
        if n.kind = HOCON_LIST then
            n.item := new HoconNodeVector(0 to count - 1);
            for i in 0 to count - 1 loop
                node_of(hwut_vhpi_hocon_item(h, i), n.item(i));
            end loop;
        elsif n.kind = HOCON_OBJECT then
            n.entry := new HoconEntryVector(0 to count - 1);
            for i in 0 to count - 1 loop
                child_h := hwut_vhpi_hocon_entry(h, i);
                deallocate(text);
                text := new string'(result & LF);
                n.entry(i).key_position := (integer'value(item(text.all, 0)), integer'value(item(text.all, 1)));
                n.entry(i).key          := new string'(after_item(text(text'left to text'right - 1), 2));
                node_of(child_h, n.entry(i).node);
            end loop;
        end if;
        deallocate(text);
        node := n;
    end procedure;

    procedure parse(lines : str_list; file_name : string;
                    variable document : out HoconNodeAccess;
                    variable faults   : out HoconFaultVectorAccess;
                    line_offset   : integer := 0;
                    column_offset : integer := 0;
                    bound_us      : natural := 0) is
        -- RETURN: nothing; 'document' is the annotated tree of 'lines' -- its
        --         root object -- and 'faults' every fault found, in order,
        --         'file_name' naming the file in them; the parse never fails.
        --         'bound_us' > 0 bounds the parse to that many microseconds:
        --         where it took longer, 'document' and 'faults' are null --
        --         the parse HUNG.
        variable h    : integer;
        variable f    : HoconFaultVectorAccess;
        variable text : line;
    begin
        if lines'length > 0 and lines(lines'right) = LF then
            h := hwut_vhpi_hocon_parse(lines(lines'left to lines'right - 1), line_offset, column_offset, file_name, bound_us);
        else
            h := hwut_vhpi_hocon_parse(lines, line_offset, column_offset, file_name, bound_us);
        end if;
        if h < 0 then document := null; faults := null; return; end if;
        node_of(hwut_vhpi_hocon_root(h), document);
        f := new HoconFaultVector(0 to hwut_vhpi_hocon_fault_n(h) - 1);
        for i in f'range loop
            hwut_vhpi_hocon_fault(h, i);
            text := new string'(result & LF);
            f(i).text := new string'(item(text.all, 0));
            if item(text.all, 1) = "syntax" then f(i).kind := HOCON_SYNTAX;
            else                                 f(i).kind := HOCON_REFUSED;
            end if;
            f(i).position := (integer'value(item(text.all, 2)), integer'value(item(text.all, 3)));
            f(i).message  := new string'(after_item(text(text'left to text'right - 1), 4));
            f(i).file_name := new string'(file_name);
            deallocate(text);
        end loop;
        faults := f;
        hwut_vhpi_hocon_free(h);
    end procedure;

    procedure get(variable node : inout HoconNodeAccess; key : string; variable found : out HoconNodeAccess) is
        -- RETURN: nothing; 'found' is the node the object 'node' binds 'key'
        --         to -- the last entry so keyed; null where none is.
    begin
        found := null;
        if node = null or node.kind /= HOCON_OBJECT then return; end if;
        for i in node.entry'range loop
            if node.entry(i).key.all = key then found := node.entry(i).node; end if;
        end loop;
    end procedure;

    procedure free(variable node : inout HoconNodeAccess) is
        -- RETURN: nothing; 'node' and everything below it are given back;
        --         'node' is null.
    begin
        if node = null then return; end if;
        if node.item /= null then
            for i in node.item'range loop free(node.item(i)); end loop;
            deallocate(node.item);
        end if;
        if node.entry /= null then
            for i in node.entry'range loop
                deallocate(node.entry(i).key);
                free(node.entry(i).node);
            end loop;
            deallocate(node.entry);
        end if;
        deallocate(node.type_name); deallocate(node.value_repr); deallocate(node.value);
        deallocate(node);
    end procedure;

    procedure free(variable faults : inout HoconFaultVectorAccess) is
        -- RETURN: nothing; every fault is given back; 'faults' is null.
    begin
        if faults = null then return; end if;
        for i in faults'range loop
            deallocate(faults(i).file_name); deallocate(faults(i).message); deallocate(faults(i).text);
        end loop;
        deallocate(faults);
    end procedure;

    impure function cleandoc(text : string) return string is
        -- RETURN: string, 'text' laid out as Python's 'inspect.cleandoc' lays
        --         it out -- the common indentation and the blank lines at
        --         both ends removed; what a triple-quoted value holds.
    begin hwut_vhpi_hocon_cleandoc(text); return result; end function;
end package body;
