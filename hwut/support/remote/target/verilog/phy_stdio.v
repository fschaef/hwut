// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// ____________________________________________________________________________
//
// PURPOSE: The agent's byte interface under simulation: stdin and stdout of
//          the simulator are the link (MAP.txt 4; transport 'launch').
//
// A byte is read only while the agent is idle and ready: '$fgetc' blocks the
// simulation until the host sends, so simulated time stands still while the
// host thinks -- time = virtual. At end of file the simulation ends. Every
// '\n' written is flushed.
// ____________________________________________________________________________
module hwut_phy_stdio (
    input  wire       clk,
    // to the agent
    output reg        rx_valid,
    output reg  [7:0] rx_byte,
    input  wire       rx_ready,
    input  wire       rx_idle,
    input  wire       tx_valid,
    input  wire [7:0] tx_byte,
    output wire       tx_ready
);
    integer c;

    assign tx_ready = 1'b1;

    initial rx_valid = 1'b0;

    always @(posedge clk) begin
        rx_valid <= 1'b0;
        if (tx_valid) begin
            $fwrite(32'h8000_0001, "%c", tx_byte);
            if (tx_byte == 8'h0a) $fflush(32'h8000_0001);
        end
        else if (rx_ready && rx_idle && !rx_valid) begin
            c = $fgetc(32'h8000_0000);
            if (c == -1) $finish(0);
            rx_byte  <= c[7:0];
            rx_valid <= 1'b1;
        end
    end
endmodule
