const std = @import("std");

fn check_num(val: i32) ?i32 {
    if ((val > 0)) {
        return val;
    }
    return null;
}

pub fn main() !void {
    const opt = check_num(5);
    std.debug.print("Val: {d}\n", .{(opt orelse unreachable)});
}
