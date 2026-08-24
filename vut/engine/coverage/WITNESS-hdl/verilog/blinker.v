// A tiny FSM: IDLE -> RUN -> DONE, advanced by 'enable'.
module blinker(
    input  wire       clk,
    input  wire       rst,
    input  wire       enable,
    output reg  [1:0] state,
    output reg  [3:0] count
);
    localparam IDLE = 2'd0, RUN = 2'd1, DONE = 2'd2;

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            count <= 4'd0;
        end else begin
            case (state)
                IDLE: if (enable) state <= RUN;
                RUN:  begin
                    count <= count + 4'd1;
                    if (count == 4'd3) state <= DONE;
                end
                DONE: state <= DONE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule

// Functional cover points (Verilator emits these as 'user' coverage).
module blinker_cov(input wire clk, input wire [1:0] state);
    cover property (@(posedge clk) state == 2'd2);  // reached DONE
    cover property (@(posedge clk) state == 2'd3);  // impossible state
endmodule
