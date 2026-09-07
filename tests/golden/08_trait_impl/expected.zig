const std = @import("std");

// Trait: Speaker
const Speaker = struct {};

const Dog = struct {
    fn speak(self: *const Dog) void {
        _ = self;
        std.debug.print("Woof\n", .{});
    }
};

pub fn main() !void {
    const d = Dog{};
    d.speak();
}
