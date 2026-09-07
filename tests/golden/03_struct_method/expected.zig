const std = @import("std");

const Point = struct {
    x: i32,
    y: i32,

    fn area(self: *const Point) i32 {
        return self.x * self.y;
    }
};

pub fn main() !void {
    const p = Point{ .x = 3, .y = 4 };
    const a = p.area();
    std.debug.print("Area: {d}\n", .{a});
}
