const std = @import("std");

fn process_vec(allocator: std.mem.Allocator) !void {
    var numbers = std.ArrayList(i32).empty;
    try numbers.append(allocator, 10);
    try numbers.append(allocator, 20);
}

pub fn main() !void {
    try process_vec(std.heap.page_allocator);
}
