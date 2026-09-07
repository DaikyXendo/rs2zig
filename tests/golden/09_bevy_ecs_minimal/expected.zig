const std = @import("std");
const bevy_ecs = @import("/Users/levanthanh/Documents/code/python/rs2zig/src/rs2zig/runtime/bevy_ecs_runtime.zig");

fn setup_system() void {
    std.debug.print("Initializing Bevy ECS Startup System...\n", .{});
}

fn update_system() void {
    std.debug.print("Running Bevy ECS Update System...\n", .{});
}

pub fn main() !void {
    bevy_ecs.App.init(std.heap.page_allocator).add_system(setup_system).add_system(update_system).run();
}
