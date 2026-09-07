const std = @import("std");

fn worker_task() void {
    std.debug.print("Running background thread task\n", .{});
}

pub fn main() !void {
    const handle = std.Thread.spawn(.{}, worker_task, .{});
    _ = handle;
}
