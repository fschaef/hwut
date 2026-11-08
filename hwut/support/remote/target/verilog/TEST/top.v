// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// ____________________________________________________________________________
//
// PURPOSE: The simulation tops of test-agent.py: the agent over stdio in
//          front of one of three UUTs, chosen by the define UUT:
//
//    adder     8-bit registered adder, LATENCY 1 (sample mode)
//    counter   counts its applies: shows a duplicate 'x' does not act
//    slow      'done' rises DONE_AFTER cycles after apply (wait mode, 0)
//              -- set above 'timeout' it gives outcome 02
// ____________________________________________________________________________
module top;
    reg clk = 1'b0;
    always #10 clk = ~clk;                         // 50 MHz
    reg rst = 1'b1;
    initial begin repeat (2) @(posedge clk); rst = 1'b0; end

    wire        rx_valid, rx_ready, rx_idle, tx_valid, tx_ready;
    wire  [7:0] rx_byte, tx_byte;
    wire [15:0] stim;
    wire        apply, uut_rst;
    reg         done = 1'b0;
    reg  [15:0] report = 16'h0;

`ifdef SLOW
    localparam LATENCY = 0;
`else
    localparam LATENCY = 1;
`endif
`ifndef DONE_AFTER
  `define DONE_AFTER 5
`endif

    hwut_agent #(.SW(2), .RW(2), .IMAGE_ID(32'h3f9a07c1), .LATENCY(LATENCY),
                 .TIMEOUT(32'd`TIMEOUT), .RESET_CYCLES(4))
        agent (.clk(clk), .rst(rst),
               .rx_valid(rx_valid), .rx_byte(rx_byte), .rx_ready(rx_ready),
               .rx_idle(rx_idle), .tx_valid(tx_valid), .tx_byte(tx_byte),
               .tx_ready(tx_ready),
               .stim(stim), .apply(apply), .uut_rst(uut_rst), .done(done),
               .report(report));
    hwut_phy_stdio phy (.clk(clk), .rx_valid(rx_valid), .rx_byte(rx_byte),
                        .rx_ready(rx_ready), .rx_idle(rx_idle),
                        .tx_valid(tx_valid), .tx_byte(tx_byte),
                        .tx_ready(tx_ready));

    // ------------------------------------------------------------ UUTs --
`ifdef COUNTER
    always @(posedge clk)
        if (uut_rst) report <= 16'h0;
        else if (apply) report <= report + 1;
`elsif SLOW
    integer n = -1;
    always @(posedge clk)
        if (uut_rst) begin done <= 1'b0; n <= -1; end
        else if (apply) begin done <= 1'b0; n <= 0; end
        else if (n >= 0) begin
            n <= n + 1;
            if (n + 1 == `DONE_AFTER) begin
                done   <= 1'b1;
                report <= {8'h00, stim[15:8]} + {8'h00, stim[7:0]};
                n      <= -1;
            end
        end
`else
    always @(posedge clk)                          // the adder of Chapter 11
        if (uut_rst) report <= 16'h0;
        else if (apply) report <= {7'h0, {1'b0, stim[15:8]} + {1'b0, stim[7:0]}};
`endif
endmodule
