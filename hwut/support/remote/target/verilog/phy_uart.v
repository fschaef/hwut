// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// ____________________________________________________________________________
//
// PURPOSE: The agent's byte interface on a board: a UART, 8N1, at BAUD from
//          CLOCK_HZ (MAP.txt 4; transport 'serial').
//
// The receiver samples mid-bit after a two-flop synchroniser and holds one
// byte until the agent takes it; a byte arriving while one is held is lost
// (the line it belongs to then fails its CRC: noise). The transmitter sends
// one byte per 'tx_valid' while 'tx_ready'.
// ____________________________________________________________________________
module hwut_phy_uart #(
    parameter CLOCK_HZ = 50_000_000,
    parameter BAUD     = 115_200
) (
    input  wire       clk,
    input  wire       uart_rx,
    output reg        uart_tx,
    // to the agent
    output reg        rx_valid,
    output reg  [7:0] rx_byte,
    input  wire       rx_ready,
    input  wire       rx_idle,
    input  wire       tx_valid,
    input  wire [7:0] tx_byte,
    output wire       tx_ready
);
    localparam integer DIV = CLOCK_HZ / BAUD;

    // ---------------------------------------------------------------- rx --
    reg        s1 = 1'b1, s2 = 1'b1;
    reg        rx_busy = 1'b0;
    reg [15:0] rx_count = 0;
    reg  [3:0] rx_bit = 0;
    reg  [7:0] rx_shift = 0;
    reg        held = 1'b0;

    initial begin rx_valid = 1'b0; uart_tx = 1'b1; end

    always @(posedge clk) begin
        s1 <= uart_rx;
        s2 <= s1;
        rx_valid <= 1'b0;
        if (held && rx_ready) begin
            rx_valid <= 1'b1;
            held     <= 1'b0;
        end
        if (!rx_busy) begin
            if (!s2) begin                          // a start bit
                rx_busy  <= 1'b1;
                rx_count <= DIV / 2;
                rx_bit   <= 0;
            end
        end
        else if (rx_count != 0)
            rx_count <= rx_count - 1;
        else begin
            rx_count <= DIV - 1;
            rx_bit   <= rx_bit + 1;
            if (rx_bit == 0) begin
                if (s2) rx_busy <= 1'b0;            // a glitch, not a start
            end
            else if (rx_bit <= 8)
                rx_shift <= {s2, rx_shift[7:1]};
            else begin                              // the stop bit
                rx_busy <= 1'b0;
                if (s2 && !held) begin
                    rx_byte <= rx_shift;
                    held    <= 1'b1;
                end
            end
        end
    end

    // ---------------------------------------------------------------- tx --
    reg        tx_busy = 1'b0;
    reg [15:0] tx_count = 0;
    reg  [3:0] tx_bit = 0;
    reg  [9:0] tx_shift = 10'h3ff;

    assign tx_ready = !tx_busy;

    always @(posedge clk) begin
        if (!tx_busy) begin
            if (tx_valid) begin
                tx_shift <= {1'b1, tx_byte, 1'b0};
                tx_busy  <= 1'b1;
                tx_count <= DIV - 1;
                tx_bit   <= 0;
                uart_tx  <= 1'b0;
            end
        end
        else if (tx_count != 0)
            tx_count <= tx_count - 1;
        else if (tx_bit == 9) begin
            tx_busy <= 1'b0;
            uart_tx <= 1'b1;
        end
        else begin
            tx_count <= DIV - 1;
            tx_bit   <= tx_bit + 1;
            tx_shift <= {1'b1, tx_shift[9:1]};
            uart_tx  <= tx_shift[1];
        end
    end
endmodule
