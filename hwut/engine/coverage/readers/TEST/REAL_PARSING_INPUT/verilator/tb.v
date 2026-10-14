// Testbench: reset, then enable long enough for a's FSM to reach DONE.
module tb;
    reg clk = 0, rst = 1, go = 0;

    top dut(.clk(clk), .rst(rst), .go(go));

    always #5 clk = ~clk;

    initial begin
        #12 rst = 0;
        #10 go  = 1;
        #100 $finish;
    end
endmodule
