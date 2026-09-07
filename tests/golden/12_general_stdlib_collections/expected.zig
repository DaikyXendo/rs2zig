const std = @import("std");

pub fn main() !void {
    const map: std.StringHashMap(i32) = .init(std.heap.page_allocator);
    _ = map;
    std.debug.print("Map initialized\n", .{});
}
