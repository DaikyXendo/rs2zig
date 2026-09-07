const std = @import("std");

fn identity(comptime T: type, x: T) T {
    return x;
}

pub fn main() !void {
    const val = identity(i32, 42);
    std.debug.print("Val: {d}\n", .{val});
}
