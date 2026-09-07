const std = @import("std");
const bevy_ecs = @import("/Users/levanthanh/Documents/code/python/rs2zig/src/rs2zig/runtime/bevy_ecs_runtime.zig");

pub fn setup(commands: *bevy_ecs.Commands) void {
    commands.spawn(.{ bevy_ecs.Transform.from_xyz(0.0, 0.0, 0.0), bevy_ecs.Velocity{ .x = 10.0, .y = 5.0 } });
}

pub fn movement_system(query: *bevy_ecs.QueryTransformVelocity, time: *const bevy_ecs.Time) void {
    while (query.next()) |item| {
        const transform = item.transform;
        const velocity = item.velocity;
        transform.x += velocity.x * time.delta_seconds();
        transform.y += velocity.y * time.delta_seconds();
    }
}

pub fn main() !void {
    bevy_ecs.App.init(std.heap.page_allocator).add_system(setup).add_system(movement_system).run();
}
