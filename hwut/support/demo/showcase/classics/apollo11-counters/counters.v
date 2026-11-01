// counters.v -- the counter-increment logic of the Apollo Guidance Computer
// (Block II), reduced to three counters: TIME1, CDUT and CDUS.
//
// An external pulse does not interrupt the program. It sets a PENDING latch;
// at the next memory cycle (MCT, 11.72 us) the sequencer STEALS that cycle
// from the program and increments the counter cell (PINC). One counter per
// memory cycle, by fixed priority: TIME1 > CDUT > CDUS. A pending latch
// holds one pulse; it is cleared when ITS counter is served, and only then.
//
// clk is one memory cycle. p_* are the pulses that arrived during it.
// slot tells what the cycle did: 0 program, 1 TIME1, 2 CDUT, 3 CDUS.
module counters (
    input  wire        clk,
    input  wire        rst,
    input  wire        p_time1,
    input  wire        p_cdut,
    input  wire        p_cdus,
    output reg  [1:0]  slot,
    output reg  [14:0] time1,
    output reg  [14:0] cdut,
    output reg  [14:0] cdus
);
    reg pend_time1, pend_cdut, pend_cdus;

    always @(posedge clk) begin
        if (rst) begin
            {pend_time1, pend_cdut, pend_cdus} <= 3'b000;
            slot <= 2'd0; time1 <= 15'd0; cdut <= 15'd0; cdus <= 15'd0;
        end else begin
            // serve the highest-priority pending counter; clear ITS latch only
            if (pend_time1) begin
                slot <= 2'd1; time1 <= time1 + 15'd1;
                pend_time1 <= p_time1;
                pend_cdut  <= pend_cdut | p_cdut;
                pend_cdus  <= pend_cdus | p_cdus;
            end else if (pend_cdut) begin
                slot <= 2'd2; cdut <= cdut + 15'd1;
                pend_time1 <= p_time1;
                pend_cdut  <= p_cdut;
                pend_cdus  <= pend_cdus | p_cdus;
            end else if (pend_cdus) begin
                slot <= 2'd3; cdus <= cdus + 15'd1;
                pend_time1 <= p_time1;
                pend_cdut  <= p_cdut;
                pend_cdus  <= p_cdus;
            end else begin
                slot <= 2'd0;
                pend_time1 <= p_time1;
                pend_cdut  <= p_cdut;
                pend_cdus  <= p_cdus;
            end
        end
    end
endmodule
