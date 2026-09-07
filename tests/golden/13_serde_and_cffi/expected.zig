const std = @import("std");

pub const User = struct {
    id: u64,
};

fn process_ptr(ptr: [*c]const u8, mut_ptr: [*c]u8) void {
    _ = ptr;
    _ = mut_ptr;
}

pub fn main() !void {
    std.debug.print("Serde and CFFI test\n", .{});
}
