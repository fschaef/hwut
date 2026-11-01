-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: WHAT VHDL CANNOT DO ITSELF, FROM 'hwut_vhpi.c' BY VHPIDIRECT: the
--          text a C call leaves behind, the process (flush, exit, the
--          environment) and the runner's plumbing for '--interactive'
--          (descriptors, fork). Every other package of this directory that
--          calls C declares its own foreign subprograms in its body; this
--          one gives them the RESULT channel:
--
--              hwut_vhpi_fsm_to_string(handle);     -- C leaves a text ...
--              text := new string'(result);          -- ... VHDL takes it
--
--          For a test author: 'getenv', 'setenv' (Python's os.environ) and
--          'process_exit'.
--
-- THE LIBRARY is 'libhwut_vhdl.so', built per test by 'TEST/Makefile' from
-- 'hwut_vhpi.c' and the C modules of '../c'; the launcher puts its directory
-- on LD_LIBRARY_PATH, where GHDL finds it at elaboration.
-- _____________________________________________________________________________
package hwut_vhpi is
    impure function result return string;

    procedure flush;
    procedure process_exit(status : integer);
    impure function getenv(name : string) return string;
    impure function getenv_f(name : string) return boolean;
    procedure setenv(name : string; value : string);

    procedure interactive_begin;
    procedure up(message : string);
    impure function run_into_sinks(sink_out : string; sink_err : string) return integer;
    constant RUN_IN_CHILD : integer := -1000;
end package;

package body hwut_vhpi is
    impure function hwut_vhpi_result_n return integer;
    attribute foreign of hwut_vhpi_result_n : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_result_n";
    impure function hwut_vhpi_result_n return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_result_get(text : inout string);
    attribute foreign of hwut_vhpi_result_get : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_result_get";
    procedure hwut_vhpi_result_get(text : inout string) is
    begin assert false severity failure; end procedure;

    procedure hwut_vhpi_flush;
    attribute foreign of hwut_vhpi_flush : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_flush";
    procedure hwut_vhpi_flush is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_exit(status : integer);
    attribute foreign of hwut_vhpi_exit : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_exit";
    procedure hwut_vhpi_exit(status : integer) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_getenv(name : string) return integer;
    attribute foreign of hwut_vhpi_getenv : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_getenv";
    impure function hwut_vhpi_getenv(name : string) return integer is
    begin assert false severity failure; return 0; end function;

    procedure hwut_vhpi_setenv(name : string; value : string);
    attribute foreign of hwut_vhpi_setenv : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_setenv";
    procedure hwut_vhpi_setenv(name : string; value : string) is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_interactive_begin;
    attribute foreign of hwut_vhpi_interactive_begin : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_interactive_begin";
    procedure hwut_vhpi_interactive_begin is begin assert false severity failure; end procedure;

    procedure hwut_vhpi_up(message : string);
    attribute foreign of hwut_vhpi_up : procedure is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_up";
    procedure hwut_vhpi_up(message : string) is begin assert false severity failure; end procedure;

    impure function hwut_vhpi_run_into_sinks(sink_out : string; sink_err : string) return integer;
    attribute foreign of hwut_vhpi_run_into_sinks : function is "VHPIDIRECT libhwut_vhdl.so hwut_vhpi_run_into_sinks";
    impure function hwut_vhpi_run_into_sinks(sink_out : string; sink_err : string) return integer is
    begin assert false severity failure; return 0; end function;

    impure function result return string is
        -- RETURN: string, the text the last C call left as its result -- of
        --         its own length, "" for none.
        variable text : string(1 to hwut_vhpi_result_n);
    begin
        hwut_vhpi_result_get(text);
        return text;
    end function;

    procedure flush is
        -- RETURN: nothing; what was written to 'output' (and by C to stdout,
        --         stderr) stands in the file.
    begin hwut_vhpi_flush; end procedure;

    procedure process_exit(status : integer) is
        -- RETURN: never; the process ends with 'status', its streams flushed.
        --         ('exit' is a reserved word in VHDL.)
    begin hwut_vhpi_exit(status); end procedure;

    impure function getenv(name : string) return string is
        -- RETURN: string, the value of the environment variable 'name', if
        --         it is set; "", else.
    begin
        if hwut_vhpi_getenv(name) = 0 then return ""; end if;
        return result;
    end function;

    impure function getenv_f(name : string) return boolean is
        -- RETURN: true, the environment variable 'name' is set (to anything,
        --         "" too); false, else.
    begin return hwut_vhpi_getenv(name) /= 0; end function;

    procedure setenv(name : string; value : string) is
        -- RETURN: nothing; the environment variable 'name' holds 'value' --
        --         Python's 'os.environ[name] = value'.
    begin hwut_vhpi_setenv(name, value); end procedure;

    procedure interactive_begin is
        -- RETURN: nothing; the original stdout is the UP channel of the
        --         interactive protocol, stdout and stderr a stray sink.
    begin hwut_vhpi_interactive_begin; end procedure;

    procedure up(message : string) is
        -- RETURN: nothing; 'message' and a newline went up the UP channel.
    begin hwut_vhpi_up(message); end procedure;

    impure function run_into_sinks(sink_out : string; sink_err : string) return integer is
        -- RETURN: RUN_IN_CHILD in the child process made for one choice, its
        --         stdout and stderr the two sink files -- the caller runs
        --         the choice there and exits;
        --         the child's exit status in the parent, once it ended
        --         (minus the signal that ended it); 1, no child was made.
    begin return hwut_vhpi_run_into_sinks(sink_out, sink_err); end function;
end package body;
