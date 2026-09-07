const std = @import("std");
const bevy_ecs = @import("bevy_ecs_runtime.zig");
const channel = bevy_ecs.channel;
const stdin = bevy_ecs.stdin;
const String = []u8;
const IpAddr = []u8;
const UdpSocket = bevy_ecs.UdpSocket;
const aok_core = @import("aok_core");
const create_app = aok_core.create_app;

fn setup_system() void {
    std.debug.print("Initializing Bevy ECS Startup System...\n", .{});
}

fn update_system() void {
    std.debug.print("Running Bevy ECS Update System...\n", .{});
}

pub fn main() !void {
    bevy_ecs.App.init(std.heap.page_allocator).add_system(setup_system).add_system(update_system).run();
}
