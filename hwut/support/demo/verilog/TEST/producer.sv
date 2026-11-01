// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE PRODUCER OF 'protocol.sh clean' -- no test, the program that feeds
// 'protocol.pype' live:
//
//     producer.exe | hwut.pype protocol.pype
//
// Five clients talk to a service at once: five PROCESSES of the simulation,
// each sending its request and receiving its response after delays drawn at
// random (seeded anew per run), in SIMULATED time. The order of the lines is
// the draw's. Every line is flushed as it is said; no '<hwut-end>': the
// pype's '<eof>' prints it.
// _____________________________________________________________________________
import hwut_runner::*;
import deterministic_random::*;

module producer;
    timeunit 1ms;
    timeprecision 1us;

    DeterministicStream stream;

    function automatic void say(string text);
        // RETURN: nothing; 'text' was printed and flushed.
        $display("%s", text);
        $fflush();
    endfunction

    task automatic client(int n);
        // RETURN: nothing; the client 'n' sent its request and got its
        //         response, each after a drawn delay of up to 20 ms.
        #(20.0 * stream.next_float());
        say($sformatf("request %0d", n));
        #(20.0 * stream.next_float());
        say($sformatf("response %0d", n));
    endtask

    initial begin
        longint seed = 0;
        int     fd;
        fd = $fopen("/dev/urandom", "rb");
        if (fd != 0) begin void'($fread(seed, fd)); $fclose(fd); end
        seed   = (seed ^ (seed >> 31)) & 'h7FFFFFFF;
        stream = new(seed == 0 ? 1 : seed);
        fork
            client(1);
            client(2);
            client(3);
            client(4);
            client(5);
        join
        say("shutdown");
        exit_(0);
    end
endmodule
