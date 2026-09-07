// Bevy ECS Minimal Runtime in Native Zig for rs2zig
const std = @import("std");

pub const Entity = u64;

pub const Startup = struct {};
pub const Update = struct {};

pub const SystemFn = *const fn () void;

pub const App = struct {
    allocator: std.mem.Allocator,
    systems: std.ArrayList(SystemFn),

    pub fn init(allocator: std.mem.Allocator) App {
        return App{
            .allocator = allocator,
            .systems = std.ArrayList(SystemFn).empty,
        };
    }

    pub fn add_system(self: App, system_fn: SystemFn) App {
        var copy = self;
        _ = copy.systems.append(copy.allocator, system_fn) catch {};
        return copy;
    }

    pub fn run(self: App) void {
        std.debug.print("[rs2zig Bevy ECS] Initializing ECS World & System Scheduler...\n", .{});
        for (self.systems.items) |sys| {
            sys();
        }
        std.debug.print("[rs2zig Bevy ECS] Engine execution completed successfully.\n", .{});
    }
};
