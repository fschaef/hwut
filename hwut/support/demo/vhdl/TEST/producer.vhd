-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: THE PRODUCER OF 'protocol.sh clean' -- no test, the service it
--          feeds to 'protocol.pype'. Five clients talk to the service at
--          once: each sends its request and gets its response, a drawn time
--          apart; when all five are done, the service shuts down. Every
--          line is flushed as it is said -- the pype is fed live.
--
-- THE CLIENTS ARE PROCESSES, waiting drawn times of the SIMULATION: the
-- simulator wakes them in the order of their times, which is the draw's --
-- as the scheduler's is for Python's threads.
-- _____________________________________________________________________________
use work.hwut_vhpi.all;
use work.hwut_pytext.all;
use work.demo_vhpi.all;

entity producer is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture service of producer is
    type Counter is protected
        procedure count;
        impure function value return natural;
    end protected;
    type Counter is protected body
        variable n : natural := 0;
        procedure count is
            -- RETURN: nothing; one more client is done.
        begin n := n + 1; end procedure;
        impure function value return natural is
            -- RETURN: natural, the number of clients done.
        begin return n; end function;
    end protected body;

    shared variable rng  : ClockRandom;
    shared variable done : Counter;
    signal go : boolean := false;

    procedure say(text : string) is
        -- RETURN: nothing; 'text' stands on stdout, flushed.
    begin print(text); flush; end procedure;
begin
    main : process
    begin
        rng.init;
        go <= true;
        wait for 0 ns;
        while done.value < 5 loop wait for 1 ms; end loop;
        say("shutdown");
        wait;
    end process;

    clients : for n in 1 to 5 generate
        client : process
        begin
            wait until go;
            wait for rng.uniform(0.0, 20.0) * 1 ms;
            say("request " & integer'image(n));
            wait for rng.uniform(0.0, 20.0) * 1 ms;
            say("response " & integer'image(n));
            done.count;
            wait;
        end process;
    end generate;
end architecture;
