// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// ____________________________________________________________________________
//
// PURPOSE: The agent over phy_uart.v, its UART driven by a behavioural
//          bridge from the simulator's stdio: stdin bytes become rx bit
//          waveforms, the tx waveform becomes stdout bytes (test-agent.py
//          'uart'). 50 MHz, BAUD 5 Mbit/s: ten clocks a bit.
//
// The bridge reads stdin only while the agent is idle and its UART quiet:
// '$fgetc' blocks the simulation, so it must never block a pending reply.
// ____________________________________________________________________________
module top;
    localparam integer BIT = 10;                   // clocks per bit
    reg clk = 1'b0;
    always #10 clk = ~clk;
    reg rst = 1'b1;
    initial begin repeat (2) @(posedge clk); rst = 1'b0; end

    wire        rx_valid, rx_ready, rx_idle, tx_valid, tx_ready;
    wire  [7:0] rx_byte, tx_byte;
    wire [15:0] stim;
    wire        apply, uut_rst, uart_tx;
    reg         uart_rx = 1'b1;
    reg  [15:0] report = 16'h0;

    hwut_agent #(.SW(2), .RW(2), .IMAGE_ID(32'h3f9a07c1), .LATENCY(1),
                 .TIMEOUT(32'd10000000), .RESET_CYCLES(4))
        agent (.clk(clk), .rst(rst),
               .rx_valid(rx_valid), .rx_byte(rx_byte), .rx_ready(rx_ready),
               .rx_idle(rx_idle), .tx_valid(tx_valid), .tx_byte(tx_byte),
               .tx_ready(tx_ready),
               .stim(stim), .apply(apply), .uut_rst(uut_rst), .done(1'b0),
               .report(report));
    hwut_phy_uart #(.CLOCK_HZ(50_000_000), .BAUD(5_000_000))
        phy (.clk(clk), .uart_rx(uart_rx), .uart_tx(uart_tx),
             .rx_valid(rx_valid), .rx_byte(rx_byte), .rx_ready(rx_ready),
             .rx_idle(rx_idle), .tx_valid(tx_valid), .tx_byte(tx_byte),
             .tx_ready(tx_ready));

    always @(posedge clk)                          // the adder
        if (uut_rst) report <= 16'h0;
        else if (apply) report <= {7'h0, {1'b0, stim[15:8]} + {1'b0, stim[7:0]}};

    // ------------------------------------------- stdin -> rx waveform --
    integer c, b, quiet;
    initial begin
        quiet = 0;
        @(negedge rst);
        forever begin
            //  idle: the agent waits for a byte, its UART sends nothing
            while (!(rx_idle && tx_ready && quiet > 2 * BIT)) @(posedge clk);
            c = $fgetc(32'h8000_0000);
            if (c == -1) $finish(0);
            uart_rx = 1'b0; repeat (BIT) @(posedge clk);
            for (b = 0; b < 8; b = b + 1) begin
                uart_rx = c[b]; repeat (BIT) @(posedge clk);
            end
            uart_rx = 1'b1; repeat (BIT) @(posedge clk);
            //  two idle bits: the phy hands the byte over before the
            //  bridge looks at 'rx_idle' again
            repeat (2 * BIT) @(posedge clk);
        end
    end
    always @(posedge clk) quiet <= uart_tx ? quiet + 1 : 0;

    // ------------------------------------------ tx waveform -> stdout --
    integer t;
    reg [7:0] byte_out;
    initial forever begin
        @(negedge uart_tx);
        repeat (BIT + BIT / 2) @(posedge clk);
        for (t = 0; t < 8; t = t + 1) begin
            byte_out[t] = uart_tx; repeat (BIT) @(posedge clk);
        end
        $fwrite(32'h8000_0001, "%c", byte_out);
        if (byte_out == 8'h0a) $fflush(32'h8000_0001);
    end
endmodule
