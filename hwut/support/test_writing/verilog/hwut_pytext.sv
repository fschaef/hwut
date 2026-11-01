// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: TEXT AS PYTHON PRINTS IT -- so a SystemVerilog test and a Python
//          test of the same module print the same bytes and share one GOOD
//          file by a '.link' (bookkeeper B-32). The twin of
//          '../c/hwut_pytext.h' and '../perl/Hwut/PyText.pm'.
//
//     hwut_pytext::float_repr(0.1)          "0.1"      shortest text that
//     hwut_pytext::float_repr(1e-05)        "1e-05"    reads back
//     hwut_pytext::str_repr("it's")         "\"it's\"" Python's quotes
//     hwut_pytext::bytes_repr("\x1b[A")     "b'\\x1b[A'"
//     hwut_pytext::bool_repr(1)             "True"
//     hwut_pytext::list_repr('{"a", "b"})   "['a', 'b']"
//     hwut_pytext::tuple_repr('{"1"}, 0)    "(1,)"     items as written
//
// A double's shortest text and the literals' escapes are the C port's
// ('../c/hwut_pytext.c', through DPI-C: 'hwut_pytext_dpi.c'): the rule is
// written once. Joining is done here.
// _____________________________________________________________________________
package hwut_pytext;

    typedef string string_list_t[$];

    import "DPI-C" function string hwut_sv_pytext_float_repr(real x);
    import "DPI-C" function string hwut_sv_pytext_str_repr(string text);
    import "DPI-C" function string hwut_sv_pytext_bytes_repr(string data);

    function automatic string float_repr(real x);
        // RETURN: Python's 'repr(x)': the shortest text that reads back as
        //         'x'; fixed for a decimal point in (-4, 16], else
        //         exponential ('1e-05', '1e+16'); 'inf', 'nan'.
        return hwut_sv_pytext_float_repr(x);
    endfunction

    function automatic string str_repr(string text);
        // RETURN: Python's 'repr()' of the str whose UTF-8 bytes 'text'
        //         holds: single quotes, unless the text holds one and no
        //         double quote; escapes as Python writes them.
        return hwut_sv_pytext_str_repr(text);
    endfunction

    function automatic string bytes_repr(string data);
        // RETURN: Python's 'repr()' of the bytes 'data' holds: "b'...'",
        //         every byte outside printable ASCII as '\xhh' ('\n', '\r',
        //         '\t' by name).
        return hwut_sv_pytext_bytes_repr(data);
    endfunction

    function automatic string bool_repr(bit value);
        // RETURN: 'True' where 'value' is 1; 'False' else.
        return value ? string'("True") : string'("False");
    endfunction

    function automatic string join_text(string item_list[$], string separator = ", ");
        // RETURN: the items, 'separator' between each two; '' where none.
        string result = "";
        foreach (item_list[i]) result = {result, (i ? separator : ""), item_list[i]};
        return result;
    endfunction

    function automatic string list_repr(string item_list[$]);
        // RETURN: Python's 'repr()' of a list of str: "['a', 'b']", "[]".
        string quoted[$] = {};
        foreach (item_list[i]) quoted.push_back(str_repr(item_list[i]));
        return {"[", join_text(quoted), "]"};
    endfunction

    function automatic string tuple_repr(string item_list[$], bit quote_f = 1);
        // RETURN: Python's 'repr()' of a tuple: "('a', 'b')", "('a',)",
        //         "()"; with 'quote_f' 0 the items stand as written -- a
        //         tuple of numbers: "(1, 2)".
        string quoted[$] = {};
        foreach (item_list[i]) quoted.push_back(quote_f ? str_repr(item_list[i]) : item_list[i]);
        return {"(", join_text(quoted), (quoted.size() == 1 ? string'(",)") : string'(")"))};
    endfunction

    function automatic string padded(string text, int width);
        // RETURN: 'text' filled with blanks to 'width' CHARACTERS -- as
        //         Python's '%-6s' counts them, not bytes: a UTF-8
        //         continuation byte counts nothing.
        int n = 0;
        string result = text;
        for (int i = 0; i < text.len(); i++) if ((text[i] & 8'hC0) != 8'h80) n++;
        for (int i = n; i < width; i++) result = {result, " "};
        return result;
    endfunction

endpackage
