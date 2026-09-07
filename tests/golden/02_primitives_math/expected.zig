const std = @import("std");

fn add(a: i32, b: i32) i32 {
    var sum: i32 = (a + b);
    if ((sum > 10)) {
        sum = (sum * 2);
    }
    return sum;
}

pub fn main() !void {
    const result = add(5, 7);
    std.debug.print("Result: {d}\n", .{result});
}
