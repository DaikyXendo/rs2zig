const std = @import("std");

pub fn main() !void {
    const closure = (struct {
        fn run(x: i32) i32 {
            return (x + 1);
        }
    }.run);
    const res = closure(10);
    std.debug.print("Result: {d}\n", .{res});
}
