module top(
    input  wire clk,
    input  wire rst,
    input  wire go
);
    wire [1:0] state_a, state_b;
    wire [3:0] count_a, count_b;

    blinker a(.clk(clk), .rst(rst), .enable(go),
              .state(state_a), .count(count_a));
    blinker b(.clk(clk), .rst(rst), .enable(1'b0),
              .state(state_b), .count(count_b));
    blinker_cov cov(.clk(clk), .state(state_a));
endmodule
