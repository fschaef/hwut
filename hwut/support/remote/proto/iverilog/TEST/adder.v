// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// ____________________________________________________________________________
//
// PURPOSE: THE UUT of the prototype -- Chapter 11's adder: an 8-bit adder,
//          registered, its sum one cycle after 'apply' (LATENCY 1). A writer
//          who copies the prototype replaces this file.
// ____________________________________________________________________________
module adder (
    input  wire       clk,
    input  wire       rst,
    input  wire       apply,
    input  wire [7:0] a,
    input  wire [7:0] b,
    output reg  [8:0] sum
);
    always @(posedge clk)
        if (rst)        sum <= 9'h0;
        else if (apply) sum <= {1'b0, a} + {1'b0, b};
endmodule
