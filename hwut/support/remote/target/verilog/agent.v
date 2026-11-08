// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// ____________________________________________________________________________
//
// PURPOSE: THE AGENT, in Verilog-2001: the map of MAP.txt and the verbs of
//          PROTOCOL.txt in front of a UUT, behind a phy (phy_uart.v on a
//          board, phy_stdio.v under simulation).
//
//              +------------------------ agent -------------------------+
//    phy ----->| line > CRC > parser > map ---+-- stim[SW*8] -----------+-> UUT
//    phy <-----| line < CRC <------------------+   apply, uut_rst -------+->
//              |  wait counter (clk)           +<- done, report[RW*8] ---+--
//              +--------------------------------------------------------+
//
// PARAMETERS   SW, RW            stimulus and report bytes, 1..32
//              IMAGE_ID          the image id (TMP/image_id.vh)
//              CLOCK_HZ          the clock shared with the UUT
//              TIMEOUT           counts a wait for 'done' may take, at start;
//                                0: none -- the wait is ended by 'k' alone
//              LATENCY           0: wait for done to rise; 1..63: sample the
//                                report LATENCY cycles after apply (mode 1)
//              RESET_CYCLES      uut_rst high this long on the reset write
//
// Out of range at synthesis: an instance of a module that does not exist,
// named after the fault. Every reply is the content of a read: the reply to
// 'w' is map[19], to 'x' map[19 .. 19+RW]. A duplicate 'w' or 'x' (its token
// equals 'last') does not act. A line arriving while an 'x' or the reset
// write is pending is answered '! busy' -- except 'k', the termination
// request: it aborts the wait, resets the UUT and replies the status; it
// does not touch 'last' or 'fresh' (on a UART; under stdio no byte is read
// while a command is pending, and the host ends the simulator instead).
// The bus (100 and above) is not built: '! limit'.
// ____________________________________________________________________________
module hwut_agent #(
    parameter        SW           = 2,
    parameter        RW           = 2,
    parameter [31:0] IMAGE_ID     = 32'h0,
    parameter [31:0] CLOCK_HZ     = 32'd50_000_000,
    parameter [31:0] TIMEOUT      = 32'd0,
    parameter        LATENCY      = 1,
    parameter        RESET_CYCLES = 4
) (
    input  wire            clk,
    input  wire            rst,           // agent start, active high
    // the phy
    input  wire            rx_valid,
    input  wire [7:0]      rx_byte,
    output wire            rx_ready,
    output wire            rx_idle,
    output reg             tx_valid,
    output reg  [7:0]      tx_byte,
    input  wire            tx_ready,
    // the UUT
    output reg  [SW*8-1:0] stim,
    output reg             apply,
    output reg             uut_rst,
    input  wire            done,
    input  wire [RW*8-1:0] report
);
    // ------------------------------------------------ synthesis refusals --
    generate
        if (SW < 1 || SW > 32)       begin : f1 SW_must_be_1_to_32      fault(); end
        if (RW < 1 || RW > 32)       begin : f2 RW_must_be_1_to_32      fault(); end
        if (LATENCY < 0 || LATENCY > 63)
                                     begin : f3 LATENCY_must_be_0_to_63 fault(); end
        if (TIMEOUT != 0 && (TIMEOUT < LATENCY || TIMEOUT < RESET_CYCLES))
                                     begin : f4 TIMEOUT_below_a_wait    fault(); end
    endgenerate

    localparam [7:0] MODE    = {7'b0, (LATENCY != 0)};
    localparam [7:0] A_LAST  = 8'h18, A_STATUS = 8'h19, A_REPORT = 8'h1a;
    localparam [7:0] A_RESET = 8'h3f, A_STIM   = 8'h40;

    // ----------------------------------------------------- characters --
    function is_hex;    input [7:0] c;
        is_hex = (c >= "0" && c <= "9") || (c >= "a" && c <= "f");
    endfunction
    function [3:0] hex_val; input [7:0] c;
        hex_val = (c <= "9") ? c - "0" : c - "a" + 4'd10;
    endfunction
    function [7:0] hex_chr; input [3:0] v;
        hex_chr = (v < 10) ? "0" + v : "a" + v - 4'd10;
    endfunction
    function in_alphabet; input [7:0] c;
        in_alphabet = (c >= "a" && c <= "z") || (c >= "0" && c <= "9")
                   || c == " " || c == "!" || c == "*";
    endfunction
    function [15:0] crc_step; input [15:0] crc; input [7:0] b;
        integer k; reg [15:0] x;
        begin
            x = crc ^ {b, 8'h00};
            for (k = 0; k < 8; k = k + 1)
                x = x[15] ? ((x << 1) ^ 16'h1021) : (x << 1);
            crc_step = x;
        end
    endfunction
    //  The refusal words, 'unknown', 'syntax', 'limit', 'busy', one char at
    //  a time; 0 past the end.
    localparam [1:0] W_UNKNOWN = 0, W_SYNTAX = 1, W_LIMIT = 2, W_BUSY = 3;
    function [7:0] word_chr; input [1:0] w; input [3:0] i;
        reg [8*7-1:0] s; reg [3:0] n;
        begin
            case (w)
                W_UNKNOWN: begin s = "unknown"; n = 7; end
                W_SYNTAX:  begin s = "syntax "; n = 6; end
                W_LIMIT:   begin s = "limit  "; n = 5; end
                default:   begin s = "busy   "; n = 4; end
            endcase
            word_chr = (i < n) ? s[8*(6-i) +: 8] : 8'h00;
        end
    endfunction

    // ------------------------------------------------------- the state --
    reg  [7:0]  rbuf [0:79];
    reg  [6:0]  rlen;
    reg         rbad;
    reg  [7:0]  last;
    reg         fresh;
    reg  [1:0]  outcome;
    reg  [7:0]  discard;
    reg  [31:0] timeout;
    reg  [RW*8-1:0] report_q;
    wire [7:0]  status = {fresh, 5'b0, outcome};

    // ----------------------------------------------------------- the map --
    reg  [15:0] ma;                       // the address a reply reads
    reg  [7:0]  mbyte;
    always @* begin
        mbyte = 8'h00;
        if      (ma <= 16'h03) mbyte = (ma == 0) ? "h" : (ma == 1) ? "w"
                                     : (ma == 2) ? "u" : "t";
        else if (ma == 16'h04) mbyte = 8'h01;
        else if (ma <= 16'h07) mbyte = 8'h00;
        else if (ma <= 16'h0b) mbyte = IMAGE_ID[8*(ma - 8) +: 8];
        else if (ma == 16'h0c) mbyte = SW;
        else if (ma == 16'h0d) mbyte = RW;
        else if (ma == 16'h0e) mbyte = MODE;
        else if (ma == 16'h0f) mbyte = discard;
        else if (ma <= 16'h13) mbyte = CLOCK_HZ[8*(ma - 16'h10) +: 8];
        else if (ma <= 16'h17) mbyte = timeout[8*(ma - 16'h14) +: 8];
        else if (ma == 16'h18) mbyte = last;
        else if (ma == 16'h19) mbyte = status;
        else if (ma <  A_REPORT + RW) mbyte = report_q[8*(ma - A_REPORT) +: 8];
        else if (ma >= A_STIM && ma < A_STIM + SW)
                               mbyte = stim[8*(ma - A_STIM) +: 8];
    end

    function readable;    input [16:0] a; input [16:0] n;
        readable = (a + n <= A_REPORT + RW)
                || (a >= A_STIM && a + n <= A_STIM + SW);
    endfunction

    // ------------------------------------------------------ the executor --
    //  'x' and the reset write: the apply strobe and the wait, or uut_rst
    //  for RESET_CYCLES. 'ex_busy' while it runs.
    localparam [1:0] X_IDLE = 0, X_APPLY = 1, X_WAIT = 2, X_RESET = 3;
    reg  [1:0]  xstate;
    reg  [31:0] xcount;
    reg         start_x, start_reset, start_kill;
    reg         kill_f;                   // the reset is 'k''s: fresh stays
    reg         done_q;
    wire        ex_busy = (xstate != X_IDLE) || start_x || start_reset
                       || start_kill;

    always @(posedge clk) begin
        apply  <= 1'b0;
        done_q <= done;
        if (rst) begin
            xstate   <= X_IDLE;
            uut_rst  <= 1'b0;
            outcome  <= 2'b00;
            fresh    <= 1'b1;
            report_q <= {RW*8{1'b0}};
            kill_f   <= 1'b0;
        end
        else if (start_kill) begin                // 'k': abort, reset the UUT
            uut_rst <= 1'b1;
            xcount  <= 0;
            kill_f  <= 1'b1;
            xstate  <= X_RESET;
        end
        else case (xstate)
            X_IDLE:
                if (start_x) begin
                    apply  <= 1'b1;
                    xcount <= 0;
                    xstate <= X_APPLY;
                end
                else if (start_reset) begin
                    uut_rst <= 1'b1;
                    xcount  <= 0;
                    kill_f  <= 1'b0;
                    xstate  <= X_RESET;
                end
            X_APPLY:                              // the strobe is out
                xstate <= X_WAIT;
            X_WAIT: begin
                xcount <= xcount + 1;
                if (LATENCY != 0 && xcount + 1 == LATENCY) begin
                    report_q <= report;           // sampled
                    outcome  <= 2'b01;
                    xstate   <= X_IDLE;
                end
                else if (LATENCY == 0 && done && !done_q) begin
                    report_q <= report;           // done rose
                    outcome  <= 2'b01;
                    xstate   <= X_IDLE;
                end
                else if (LATENCY == 0 && timeout != 0
                         && xcount + 1 >= timeout) begin
                    report_q <= report;           // no done: data
                    outcome  <= 2'b10;
                    xstate   <= X_IDLE;
                end
            end
            X_RESET: begin
                xcount <= xcount + 1;
                if (xcount + 1 >= RESET_CYCLES) begin
                    uut_rst <= 1'b0;
                    outcome <= 2'b00;
                    if (!kill_f) fresh <= 1'b0;
                    xstate  <= X_IDLE;
                end
            end
        endcase
    end

    // ------------------------------------------------------- the parser --
    localparam [3:0] S_RX = 0, S_CRC = 1, S_TRAIL = 2, S_NOISE = 3,
                     S_VERB = 4, S_WORD = 5, S_EXEC = 6, S_SEND = 7,
                     S_PEND = 8;
    reg  [3:0]  state;
    reg  [6:0]  i, hend;                  // hend: the last byte of the body
    reg  [15:0] crc;
    reg         prev_space, body_bad;
    reg  [3:0]  token;
    reg  [7:0]  verb;
    reg  [1:0]  nword;                    // argument words seen
    reg  [6:0]  ndig;                     // digits of the word being read
    reg  [31:0] wval;                     // its value (low 8 digits)
    reg  [31:0] arg0, arg1;
    reg  [6:0]  dig0, dig1;
    reg  [7:0]  abyte [0:35];             // the byte pairs of the last word
    reg  [5:0]  nb;
    reg         syntax;
    reg         pending, pend_x;
    reg  [3:0]  pend_token;
    integer     k;

    //  The reply: token, ' ', a body, ' *', CRC, '\n'. The body is a read of
    //  the map (rd_base, rd_n bytes) or '! ' and a refusal word.
    reg  [3:0]  rp_token;
    reg         rp_refuse;
    reg  [1:0]  rp_word;
    reg  [15:0] rd_base;
    reg  [5:0]  rd_n;
    reg  [2:0]  phase;                    // 0 token, 1 ' ', 2 body, 3 trailer
    reg  [6:0]  j;
    reg         tx_wait;

    assign rx_idle  = (state == S_RX) && !pending;
    assign rx_ready = (state == S_RX) && !(pending && !ex_busy && rlen == 0);

    //  The character the reply emits at (phase, j); 0 ends a phase.
    reg  [7:0]  rp_chr;
    always @* begin
        ma     = rd_base + (j >> 1);
        rp_chr = 8'h00;
        case (phase)
            3'd0: rp_chr = (j == 0) ? hex_chr(rp_token) : 8'h00;
            3'd1: rp_chr = (j == 0) ? " " : 8'h00;
            3'd2: if (rp_refuse)
                      rp_chr = (j == 0) ? "!" : (j == 1) ? " "
                             : word_chr(rp_word, j - 2);
                  else if (j < 2 * rd_n)
                      rp_chr = j[0] ? hex_chr(mbyte[3:0]) : hex_chr(mbyte[7:4]);
            3'd3: rp_chr = (j == 0) ? " " : (j == 1) ? "*"
                         : (j == 2) ? hex_chr(crc[15:12])
                         : (j == 3) ? hex_chr(crc[11:8])
                         : (j == 4) ? hex_chr(crc[7:4])
                         : (j == 5) ? hex_chr(crc[3:0]) : 8'h0a;
            default: ;
        endcase
    end

    task reply_read; input [3:0] t; input [15:0] base; input [5:0] n;
        begin
            rp_token <= t; rp_refuse <= 1'b0; rd_base <= base; rd_n <= n;
            phase <= 0; j <= 0; crc <= 16'hffff; tx_wait <= 1'b0;
            state <= S_SEND;
        end
    endtask
    task reply_refuse; input [3:0] t; input [1:0] w;
        begin
            rp_token <= t; rp_refuse <= 1'b1; rp_word <= w; rd_base <= 0;
            rd_n <= 0; phase <= 0; j <= 0; crc <= 16'hffff; tx_wait <= 1'b0;
            state <= S_SEND;
        end
    endtask

    always @(posedge clk) begin
        tx_valid    <= 1'b0;
        start_x     <= 1'b0;
        start_reset <= 1'b0;
        start_kill  <= 1'b0;
        if (rst) begin
            state   <= S_RX;
            rlen    <= 0;
            rbad    <= 1'b0;
            last    <= 8'hff;
            discard <= 8'h00;
            timeout <= TIMEOUT;
            stim    <= {SW*8{1'b0}};
            pending <= 1'b0;
        end
        else case (state)
        // ------------------------------------------------ receive a line --
        S_RX:
            if (pending && !ex_busy && rlen == 0) begin
                pending <= 1'b0;
                reply_read(pend_token, {8'h00, A_STATUS}, pend_x ? 1 + RW : 1);
            end
            else if (rx_valid) begin
                if (rx_byte == 8'h0a) begin
                    if (rlen != 0) begin
                        state      <= S_CRC;
                        i          <= 0;
                        crc        <= 16'hffff;
                        hend       <= rlen - 7;
                        prev_space <= 1'b0;
                        body_bad   <= 1'b0;
                    end
                end
                else if (rlen == 79) rbad <= 1'b1;      // over 80 bytes
                else begin
                    rbuf[rlen] <= rx_byte;
                    rlen       <= rlen + 1;
                    if (!in_alphabet(rx_byte)) rbad <= 1'b1;
                end
            end
        // -------------------------------------------------- verify it --
        S_CRC:
            if (rbad || rlen < 9) state <= S_NOISE;
            else if (i <= hend) begin
                crc <= crc_step(crc, rbuf[i]);
                if (i >= 2) begin
                    if (rbuf[i] == " ") begin
                        if (i == 2 || i == hend || prev_space) body_bad <= 1'b1;
                    end
                    else if (rbuf[i] == "*") body_bad <= 1'b1;
                    else if (rbuf[i] == "!" && !(i == 2 && rbuf[3] == " "))
                        body_bad <= 1'b1;
                    prev_space <= (rbuf[i] == " ");
                end
                i <= i + 1;
            end
            else state <= S_TRAIL;
        S_TRAIL:
            if (!body_bad && is_hex(rbuf[0]) && rbuf[1] == " "
                && rbuf[rlen - 6] == " " && rbuf[rlen - 5] == "*"
                && is_hex(rbuf[rlen - 4]) && is_hex(rbuf[rlen - 3])
                && is_hex(rbuf[rlen - 2]) && is_hex(rbuf[rlen - 1])
                && crc == {hex_val(rbuf[rlen - 4]), hex_val(rbuf[rlen - 3]),
                           hex_val(rbuf[rlen - 2]), hex_val(rbuf[rlen - 1])})
            begin
                token <= hex_val(rbuf[0]);
                verb  <= rbuf[2];
                state <= S_VERB;
            end
            else state <= S_NOISE;
        S_NOISE: begin
            if (discard != 8'hff) discard <= discard + 1;
            rlen  <= 0;
            rbad  <= 1'b0;
            state <= S_RX;
        end
        // ------------------------------------------------- read the body --
        S_VERB:
            if (verb == "k" && hend == 2) begin          // the termination
                rlen        <= 0;                        // request
                start_kill  <= 1'b1;
                pending     <= 1'b1;
                pend_x      <= 1'b0;
                pend_token  <= token;
                state       <= S_RX;
            end
            else if (pending)                           reply_refuse(token, W_BUSY);
            else if (hend >= 3 && rbuf[3] != " ")       reply_refuse(token, W_UNKNOWN);
            else if (verb == "r" || verb == "w" || verb == "x") begin
                i      <= 4;
                nword  <= 0;
                ndig   <= 0;
                wval   <= 0;
                nb     <= 0;
                syntax <= (hend < 4);
                state  <= S_WORD;
            end
            else reply_refuse(token, W_UNKNOWN);
        S_WORD:
            if (i > hend || rbuf[i] == " ") begin       // a word ends
                if (nword == 0) begin arg0 <= wval; dig0 <= ndig; end
                if (nword == 1) begin arg1 <= wval; dig1 <= ndig; end
                if (nword == 3) syntax <= 1'b1;
                else            nword  <= nword + 1;
                if (i > hend) state <= S_EXEC;
                else begin
                    ndig <= 0; wval <= 0; nb <= 0;
                end
                i <= i + 1;
            end
            else begin
                if (!is_hex(rbuf[i])) syntax <= 1'b1;
                wval <= {wval[27:0], hex_val(rbuf[i])};
                ndig <= ndig + 1;
                if (ndig[0] && nb < 36) begin
                    abyte[nb] <= {wval[3:0], hex_val(rbuf[i])};
                    nb        <= nb + 1;
                end
                i <= i + 1;
            end
        // ------------------------------------------------------ act --
        S_EXEC: begin
            rlen <= 0;
            if (syntax) reply_refuse(token, W_SYNTAX);
            else if (verb == "r") begin
                if (nword != 2 || dig0 > 8 || dig1 > 8)  reply_refuse(token, W_SYNTAX);
                else if (arg1 == 0 || arg1 > 35 || arg0 > 32'hffff
                         || !readable(arg0[16:0], arg1[16:0]))
                                                          reply_refuse(token, W_LIMIT);
                else reply_read(token, arg0[15:0], arg1[5:0]);
            end
            else if (verb == "w") begin
                if (nword != 2 || dig0 > 8 || dig1[0] || dig1 == 0)
                    reply_refuse(token, W_SYNTAX);
                else if ({4'h0, token} == last)          // a duplicate
                    reply_read(token, {8'h00, A_STATUS}, 1);
                else if (arg0 == A_RESET && nb == 1) begin
                    last        <= {4'h0, token};
                    start_reset <= 1'b1;
                    pending     <= 1'b1;
                    pend_x      <= 1'b0;
                    pend_token  <= token;
                    state       <= S_RX;
                end
                else if (arg0 >= 8'h14 && arg0 + nb <= 8'h18) begin
                    begin : tw
                        reg [31:0] t;
                        t = timeout;
                        for (k = 0; k < 4; k = k + 1)
                            if (k >= arg0 - 8'h14 && k < arg0 - 8'h14 + nb)
                                t[8*k +: 8] = abyte[k - (arg0 - 8'h14)];
                        if (t != 0 && (t < LATENCY || t < RESET_CYCLES))
                            reply_refuse(token, W_LIMIT);
                        else begin
                            timeout <= t;
                            last    <= {4'h0, token};
                            reply_read(token, {8'h00, A_STATUS}, 1);
                        end
                    end
                end
                else if (arg0 >= A_STIM && arg0 + nb <= A_STIM + SW) begin
                    for (k = 0; k < SW; k = k + 1)
                        if (k >= arg0 - A_STIM && k < arg0 - A_STIM + nb)
                            stim[8*k +: 8] <= abyte[k - (arg0 - A_STIM)];
                    last <= {4'h0, token};
                    reply_read(token, {8'h00, A_STATUS}, 1);
                end
                else reply_refuse(token, W_LIMIT);
            end
            else begin                                   // 'x'
                if (nword != 1 || dig0[0] || dig0 == 0)  reply_refuse(token, W_SYNTAX);
                else if (nb != SW)                       reply_refuse(token, W_LIMIT);
                else if ({4'h0, token} == last)          // a duplicate
                    reply_read(token, {8'h00, A_STATUS}, 1 + RW);
                else begin
                    for (k = 0; k < SW; k = k + 1) stim[8*k +: 8] <= abyte[k];
                    last       <= {4'h0, token};
                    start_x    <= 1'b1;
                    pending    <= 1'b1;
                    pend_x     <= 1'b1;
                    pend_token <= token;
                    state      <= S_RX;
                end
            end
        end
        // ------------------------------------------------- send the reply --
        S_SEND:
            if (tx_wait) tx_wait <= 1'b0;                // one cycle per byte
            else if (tx_ready) begin
                if (rp_chr == 8'h00) begin               // a phase ends
                    phase <= phase + 1;
                    j     <= 0;
                end
                else begin
                    tx_valid <= 1'b1;
                    tx_byte  <= rp_chr;
                    tx_wait  <= 1'b1;
                    if (phase != 3) crc <= crc_step(crc, rp_chr);
                    if (rp_chr == 8'h0a) begin
                        state <= S_RX;
                        rlen  <= 0;
                    end
                    else j <= j + 1;
                end
            end
        default: state <= S_RX;
        endcase
    end
endmodule
