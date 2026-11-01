// counters_clearall.v -- the same sequencer with one line "simplified": a
// served cycle clears EVERY pending latch, not only the served counter's.
// While no two counters wait at once nothing changes; when they do, the
// lower-priority pulse is dropped without a trace.
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
            if (pend_time1)     begin slot <= 2'd1; time1 <= time1 + 15'd1; end
            else if (pend_cdut) begin slot <= 2'd2; cdut  <= cdut  + 15'd1; end
            else if (pend_cdus) begin slot <= 2'd3; cdus  <= cdus  + 15'd1; end
            else                      slot <= 2'd0;
            // "a cycle was served, start afresh": every latch takes only the
            // pulses of this cycle -- a pulse still waiting is forgotten
            pend_time1 <= p_time1;
            pend_cdut  <= p_cdut;
            pend_cdus  <= p_cdus;
        end
    end
endmodule
