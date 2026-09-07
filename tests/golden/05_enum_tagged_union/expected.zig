const std = @import("std");

const Shape = enum {
    Circle,
    Square,
};

fn describe(s: Shape) void {
    switch (s) {
        .Circle => std.debug.print("Circle\n", .{}),
        .Square => std.debug.print("Square\n", .{}),
    }
}

pub fn main() !void {
    describe(.Circle);
}
