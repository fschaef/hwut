// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// ____________________________________________________________________________
//
// PURPOSE: THE TOP LEVEL of the prototype: the agent over stdio in front of
//          the adder. Stimulus a[15:8] b[7:0] (2 bytes), report sum[8:0]
//          (2 bytes), LATENCY 1. The clock is virtual: the simulation
//          stands still while the host thinks.
// ____________________________________________________________________________
`include "image_id.vh"

module top;
    reg clk = 1'b0;
    always #10 clk = ~clk;                         // 50 MHz
    reg rst = 1'b1;
    initial begin repeat (2) @(posedge clk); rst = 1'b0; end

    wire        rx_valid, rx_ready, rx_idle, tx_valid, tx_ready;
    wire  [7:0] rx_byte, tx_byte;
    wire [15:0] stim;
    wire        apply, uut_rst;
    wire  [8:0] sum;

    hwut_agent #(.SW(2), .RW(2), .IMAGE_ID(`IMAGE_ID), .CLOCK_HZ(50_000_000),
                 .TIMEOUT(10_000_000), .LATENCY(1), .RESET_CYCLES(4))
        agent (.clk(clk), .rst(rst),
               .rx_valid(rx_valid), .rx_byte(rx_byte), .rx_ready(rx_ready),
               .rx_idle(rx_idle), .tx_valid(tx_valid), .tx_byte(tx_byte),
               .tx_ready(tx_ready),
               .stim(stim), .apply(apply), .uut_rst(uut_rst), .done(1'b0),
               .report({7'h0, sum}));
    hwut_phy_stdio phy (.clk(clk), .rx_valid(rx_valid), .rx_byte(rx_byte),
                        .rx_ready(rx_ready), .rx_idle(rx_idle),
                        .tx_valid(tx_valid), .tx_byte(tx_byte),
                        .tx_ready(tx_ready));

    adder uut (.clk(clk), .rst(uut_rst || rst), .apply(apply),
               .a(stim[15:8]), .b(stim[7:0]), .sum(sum));
endmodule
