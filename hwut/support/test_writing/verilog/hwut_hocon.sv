// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: PARSE THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE INTO THE
//          ANNOTATED TREE -- the port of 'python/hwut_hocon.py'
//          (README-hwut_hocon.txt): every key, every value and every block
//          carries its file-relative position.
//
//     import hwut_hocon::*;
//     SourceLine line_list[$] = {};
//     Fault      fault_list[$] = {};
//     ObjectNode document;
//     line_list.push_back(SourceLine::make("a = 1", 1, 0));
//     document = parse(line_list, "f.hocon", fault_list);
//     ... ScalarNode'(document.get("a")).i ...
//
// THE PARSER IS THE C PORT'S ('../c/hwut_hocon.c', through DPI-C:
// 'hwut_hocon_dpi.c'): the subset, the recovery and the fault messages are
// Python's, character for character. 'parse' copies the C tree into the
// classes below, so the tree is SystemVerilog's own -- objects, queues,
// typed values -- and the C tree is freed at once.
//
// THE TREE:
//     Node         'position'; 'kind' SCALAR, LIST or OBJECT
//     ScalarNode   'value_kind' (NULL, BOOL, INT, FLOAT, STR), the value in
//                  'b', 'i', 'f' or 's'; 'value_repr()' is Python's '%r',
//                  'type_name()' Python's 'type(value).__name__'
//     ListNode     'item_list'
//     ObjectNode   'entry_list' of Entry ('key', 'key_position', 'node')
// The parser never fails: it accumulates faults (SYNTAX, REFUSED) and goes
// on at the next line.
// _____________________________________________________________________________
package hwut_hocon;

    import hwut_pytext::*;

    typedef enum { SCALAR, LIST, OBJECT } node_kind_t;
    typedef enum { NULL_, BOOL, INT, FLOAT, STR, NOT_A_TOKEN } value_kind_t;

    import "DPI-C" function void    hwut_sv_hocon_lines_clear();
    import "DPI-C" function void    hwut_sv_hocon_lines_add(string text, int line, int column_offset);
    import "DPI-C" function chandle hwut_sv_hocon_parse(string file, int bound_us);
    import "DPI-C" function void    hwut_sv_hocon_parse_free(chandle parse);
    import "DPI-C" function chandle hwut_sv_hocon_document(chandle parse);
    import "DPI-C" function int     hwut_sv_hocon_fault_n(chandle parse);
    import "DPI-C" function string  hwut_sv_hocon_fault_field(chandle parse, int i, output int kind,
                                                              output int line, output int column);
    import "DPI-C" function int     hwut_sv_hocon_node(chandle node, output int line, output int column,
                                                       output int value_kind);
    import "DPI-C" function int     hwut_sv_hocon_bool(chandle node);
    import "DPI-C" function longint hwut_sv_hocon_int(chandle node);
    import "DPI-C" function real    hwut_sv_hocon_float(chandle node);
    import "DPI-C" function string  hwut_sv_hocon_str(chandle node);
    import "DPI-C" function int     hwut_sv_hocon_item_n(chandle node);
    import "DPI-C" function chandle hwut_sv_hocon_item(chandle node, int i);
    import "DPI-C" function int     hwut_sv_hocon_entry_n(chandle node);
    import "DPI-C" function string  hwut_sv_hocon_entry(chandle node, int i, output int line,
                                                        output int column, output chandle value);

    class Position;
        int line;
        int column;

        function new(int line = 0, int column = 0);
            // RETURN: the place 'line':'column' of a file.
            this.line   = line;
            this.column = column;
        endfunction

        function string to_string();
            // RETURN: 'line:column'.
            return $sformatf("%0d:%0d", line, column);
        endfunction
    endclass

    class SourceLine;
        // One line handed to the parser: its text without the newline, its
        // number, and what was removed before the text (an unwrapped header).
        string text;
        int    line;
        int    column_offset;

        static function SourceLine make(string text, int line, int column_offset = 0);
            // RETURN: the source line 'text', number 'line'.
            SourceLine self = new();
            self.text          = text;
            self.line          = line;
            self.column_offset = column_offset;
            return self;
        endfunction
    endclass

    class Fault;
        string   kind;              // 'SYNTAX' or 'REFUSED'
        string   file;
        Position position;
        string   message;

        function string to_string();
            // RETURN: 'file:line:column: KIND: message'.
            return $sformatf("%s:%0d:%0d: %s: %s", file, position.line, position.column, kind, message);
        endfunction
    endclass

    typedef class Entry;

    class Node;
        node_kind_t kind;
        Position    position;
    endclass

    class ScalarNode extends Node;
        value_kind_t value_kind;
        bit          b;
        longint      i;
        real         f;
        string       s;

        function string value_repr();
            // RETURN: the value as Python's '%r' prints it: 'None', 'True',
            //         '42', '-3.14', "'text'".
            case (value_kind)
                NULL_:   return "None";
                BOOL:    return bool_repr(b);
                INT:     return $sformatf("%0d", i);
                FLOAT:   return float_repr(f);
                STR:     return str_repr(s);
                default: return "<object object>";
            endcase
        endfunction

        function string type_name();
            // RETURN: the name Python's 'type(value).__name__' gives the
            //         value: 'NoneType', 'bool', 'int', 'float', 'str'.
            case (value_kind)
                NULL_:   return "NoneType";
                BOOL:    return "bool";
                INT:     return "int";
                FLOAT:   return "float";
                STR:     return "str";
                default: return "object";
            endcase
        endfunction
    endclass

    class ListNode extends Node;
        Node item_list[$];
    endclass

    class ObjectNode extends Node;
        Entry entry_list[$];

        function Node get(string key);
            // RETURN: the node of the first entry 'key'; null where none.
            foreach (entry_list[i]) if (entry_list[i].key == key) return entry_list[i].node;
            return null;
        endfunction
    endclass

    class Entry;
        string   key;
        Position key_position;
        Node     node;
    endclass

    class Copier;
        // Copies a C tree into the classes above (a class: Verilator 5.020
        // recurses in methods, not in package functions).
        static function Node copied(chandle handle);
            // RETURN: the SystemVerilog tree of the C node 'handle'.
            int line, column, value_kind;
            int kind = hwut_sv_hocon_node(handle, line, column, value_kind);
            Position position = new(line, column);
            if (kind == 0) begin
                ScalarNode node = new();
                node.kind       = SCALAR;
                node.position   = position;
                node.value_kind = value_kind_t'(value_kind);
                case (node.value_kind)
                    BOOL:  node.b = hwut_sv_hocon_bool(handle);
                    INT:   node.i = hwut_sv_hocon_int(handle);
                    FLOAT: node.f = hwut_sv_hocon_float(handle);
                    STR:   node.s = hwut_sv_hocon_str(handle);
                    default: ;
                endcase
                return node;
            end
            if (kind == 1) begin
                ListNode node = new();
                node.kind      = LIST;
                node.position  = position;
                node.item_list = {};
                for (int i = 0; i < hwut_sv_hocon_item_n(handle); i++) node.item_list.push_back(copied(hwut_sv_hocon_item(handle, i)));
                return node;
            end
            begin
                ObjectNode node = new();
                node.kind       = OBJECT;
                node.position   = position;
                node.entry_list = {};
                for (int i = 0; i < hwut_sv_hocon_entry_n(handle); i++) begin
                    Entry   entry = new();
                    chandle value;
                    entry.key          = hwut_sv_hocon_entry(handle, i, line, column, value);
                    entry.key_position = new(line, column);
                    entry.node         = copied(value);
                    node.entry_list.push_back(entry);
                end
                return node;
            end
        endfunction
    endclass

    function automatic ObjectNode parse_bounded(SourceLine line_list[$], string file, ref Fault fault_list[$],
                                                input int bound_us, output bit hang_f);
        // RETURN: the document, the outermost object, of 'line_list';
        //         'fault_list' holds every fault, in order, 'file' named in
        //         each. With 'bound_us' > 0 a parse that outlasts it is
        //         abandoned: null, and 'hang_f' 1.
        chandle    parse;
        ObjectNode document;
        fault_list = {};
        hang_f     = 0;
        hwut_sv_hocon_lines_clear();
        foreach (line_list[i]) hwut_sv_hocon_lines_add(line_list[i].text, line_list[i].line, line_list[i].column_offset);
        parse = hwut_sv_hocon_parse(file, bound_us);
        hwut_sv_hocon_lines_clear();
        if (parse == null) begin
            hang_f = 1;
            return null;
        end
        $cast(document, Copier::copied(hwut_sv_hocon_document(parse)));
        for (int i = 0; i < hwut_sv_hocon_fault_n(parse); i++) begin
            Fault fault = new();
            int   kind, line, column;
            fault.message  = hwut_sv_hocon_fault_field(parse, i, kind, line, column);
            fault.kind     = kind == 0 ? string'("SYNTAX") : string'("REFUSED");
            fault.file     = file;
            fault.position = new(line, column);
            fault_list.push_back(fault);
        end
        hwut_sv_hocon_parse_free(parse);
        return document;
    endfunction

    function automatic ObjectNode parse(SourceLine line_list[$], string file, ref Fault fault_list[$]);
        // RETURN: the document, the outermost object, of 'line_list';
        //         'fault_list' holds every fault, in order, 'file' named in
        //         each -- Python's '(document, fault_list) = parse(...)'.
        bit hang_f;
        return parse_bounded(line_list, file, fault_list, 0, hang_f);
    endfunction

endpackage
