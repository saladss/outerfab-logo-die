// SPDX-FileCopyrightText: © 2026 outerfab logo die authors
// SPDX-License-Identifier: Apache-2.0
//
// Core logic: drives the Tiny VGA Pmod from the hardened screensaver macro.
//
// Pad map (1x0.5 slot):
//   input_PAD[0]   tile          repeat the logo across the screen
//   input_PAD[1]   solid_color   solid colour instead of animated gradient
//   bidir_PAD[7:0] vga_out       Tiny VGA Pmod {hsync, B0, G0, R0, vsync, B1, G1, R1}
//   bidir_PAD[8]   gamepad_latch (input)
//   bidir_PAD[9]   gamepad_clk   (input)
//   bidir_PAD[10]  gamepad_data  (input)
//   remaining bidir pads: outputs driven low

`default_nettype none

module chip_core #(
    parameter NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS
    )(
    `ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
    `endif

    input  wire clk,       // clock
    input  wire rst_n,     // reset (active low)

    input  wire [NUM_INPUT_PADS-1:0] input_in,   // Input value
    output wire [NUM_INPUT_PADS-1:0] input_pu,   // Pull-up
    output wire [NUM_INPUT_PADS-1:0] input_pd,   // Pull-down

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,   // Input value
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,  // Output value
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,   // Output enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,   // Input type (0=CMOS Buffer, 1=Schmitt Trigger)
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,   // Slew rate (0=fast, 1=slow)
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,   // Input enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,   // Pull-up
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd,   // Pull-down

    inout  wire [NUM_ANALOG_PADS-1:0] analog  // Analog
);

    localparam [NUM_BIDIR_PADS-1:0] GAMEPAD_MASK = {{(NUM_BIDIR_PADS-11){1'b0}}, 3'b111, 8'b0};

    // Inputs: pull-down so unconnected config pins read 0
    assign input_pu = '0;
    assign input_pd = '1;

    // Bidir pads: gamepad pins are inputs with pull-up, everything else is an output
    assign bidir_oe = ~GAMEPAD_MASK;
    assign bidir_ie = GAMEPAD_MASK;
    assign bidir_pu = GAMEPAD_MASK;
    assign bidir_pd = '0;
    assign bidir_cs = '0;
    assign bidir_sl = '0;

    wire [7:0] vga_out;
    assign bidir_out = {{(NUM_BIDIR_PADS-8){1'b0}}, vga_out};

    (* keep *)
    wrapped_vga vga (
        `ifdef USE_POWER_PINS
        .VDD           (VDD),
        .VSS           (VSS),
        `endif
        .clk_i         (clk),
        .rst_n         (rst_n),
        .tile          (input_in[0]),
        .solid_color   (input_in[1]),
        .gamepad_latch (bidir_in[8]),
        .gamepad_clk   (bidir_in[9]),
        .gamepad_data  (bidir_in[10]),
        .vga_out       (vga_out)
    );

    logic _unused;
    assign _unused = &{bidir_in, input_in[NUM_INPUT_PADS-1:2], analog};

endmodule

`default_nettype wire
