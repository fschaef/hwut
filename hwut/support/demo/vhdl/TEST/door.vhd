-- @hwut {
--     title   = "Demo: a door's state machine, watched by a pype"
--     build   { framework = "make", executable = "%.exe" }
--     pype    = "door.pype"
--     choices {
--         kept   { features = ["demo-passes-on-every-run", "fsm-law-kept"] }
--         broken { features = ["demo-passes-on-every-run", "fsm-law-broken"] }
--     }
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
-- A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
-- may do.
--
-- The application prints its log as it happens: noise, and a line 'door:
-- <event>' for each thing the door does. It prints no '<hwut-end>': the
-- header names 'door.pype', which stands between it and the comparison and
-- closes the stream at '<eof>'. 'door.pype' fires every event into a state
-- machine and reports on it; it reads the log, whatever language wrote it.
--
--     closed ---( open )---> open ---( close )---> closed
--     closed ---( lock )---> locked ---( unlock )---> closed
--     open   ---( slam )---> jammed          # forbidden
--
-- kept     the door does what the model allows.
-- broken   the controller locks an open door, slams it into a jam and
--          tries to unlock it: each surprise is ONE 'BREACH' line, and the
--          end outside the final states one more. The GOOD holds them.
-- _____________________________________________________________________________
use work.hwut_vhpi.all;
use work.hwut_pytext.all;

entity door is
    generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := ""; HERE : string := ".");
end entity;

architecture test of door is
    constant KEPT   : str_list := "open" & LF & "close" & LF & "lock" & LF & "unlock" & LF & "open" & LF
                                  & "close" & LF;
    constant BROKEN : str_list := "open" & LF & "lock" & LF & "slam" & LF & "unlock" & LF;

    procedure tell(story : str_list) is
        -- RETURN: nothing; the log of the door for 'story' is printed.
    begin
        print("controller 2.1 up");
        for i in 0 to item_n(story) - 1 loop
            print("tick " & integer'image(i + 1) & ": sensors read");
            print("door: " & item(story, i));
        end loop;
        print("controller down");
    end procedure;
begin
    main : process
    begin
        if    HWUT_ARGC = 1 and HWUT_ARGV1 = "kept"   then tell(KEPT);
        elsif HWUT_ARGC = 1 and HWUT_ARGV1 = "broken" then tell(BROKEN);
        else
            print("error: a choice is required: broken, kept");
            process_exit(1);
        end if;
        wait;
    end process;
end architecture;
