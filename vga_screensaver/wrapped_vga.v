// SPDX-License-Identifier: Apache-2.0
// Wraps the Tiny Tapeout VGA screensaver (bouncing outerfab mark) as a
// hardened macro with a plain port list for the wafer.space chip top.
`default_nettype none

module wrapped_vga (
`ifdef USE_POWER_PINS
    inout wire VDD,
    inout wire VSS,
`endif
    input  wire       clk_i,     // 25.175 MHz VGA pixel clock
    input  wire       rst_n,
    input  wire       tile,        // repeat the logo across the screen
    input  wire       solid_color, // solid colour instead of animated gradient
    input  wire       gamepad_latch,
    input  wire       gamepad_clk,
    input  wire       gamepad_data,
    output wire [7:0] vga_out      // Tiny VGA Pmod: {hsync, B0, G0, R0, vsync, B1, G1, R1}
);

    tt_um_outerfab_vga_screensaver screensaver (
        .ui_in  ({1'b0, gamepad_data, gamepad_clk, gamepad_latch, 2'b00, solid_color, tile}),
        .uo_out (vga_out),
        .uio_in (8'h00),
        .uio_out(),
        .uio_oe (),
        .ena    (1'b1),
        .clk    (clk_i),
        .rst_n  (rst_n)
    );

endmodule

`default_nettype wire
