// Bevy ECS Native Runtime in Zig for rs2zig
const std = @import("std");

pub const Entity = u64;

pub const Transform = struct {
    x: f32 = 0.0,
    y: f32 = 0.0,
    z: f32 = 0.0,

    pub fn from_xyz(x: f32, y: f32, z: f32) Transform {
        return Transform{ .x = x, .y = y, .z = z };
    }
};

pub const Velocity = struct {
    x: f32 = 0.0,
    y: f32 = 0.0,
};

pub const Time = struct {
    delta_sec: f32 = 0.016,

    pub fn delta_seconds(self: Time) f32 {
        return self.delta_sec;
    }
};

pub var GLOBAL_TIME: Time = Time{ .delta_sec = 0.016 };

pub const EntityStorage = struct {
    transform: Transform,
    velocity: Velocity,
    active: bool,
};

pub var ENTITY_COUNT: usize = 0;
pub var ENTITIES: [100]EntityStorage = undefined;

pub const Commands = struct {
    pub fn spawn(self: *Commands, bundle: anytype) void {
        _ = self;
        if (ENTITY_COUNT < 100) {
            ENTITIES[ENTITY_COUNT] = EntityStorage{
                .transform = bundle.@"0",
                .velocity = bundle.@"1",
                .active = true,
            };
            ENTITY_COUNT += 1;
        }
    }
};

pub var GLOBAL_COMMANDS: Commands = Commands{};

pub const QueryTransformVelocity = struct {
    pub const Item = struct {
        transform: *Transform,
        velocity: *const Velocity,
    };

    index: usize = 0,

    pub fn next(self: *QueryTransformVelocity) ?Item {
        while (self.index < ENTITY_COUNT) {
            const idx = self.index;
            self.index += 1;
            if (ENTITIES[idx].active) {
                return Item{
                    .transform = &ENTITIES[idx].transform,
                    .velocity = &ENTITIES[idx].velocity,
                };
            }
        }
        return null;
    }
};

pub const Startup = struct {};
pub const Update = struct {};

pub const SystemFn = *const fn () void;

pub fn wrapSystem(comptime sys: anytype) SystemFn {
    const info = @typeInfo(@TypeOf(sys));
    const fn_info = info.@"fn";
    return struct {
        fn runner() void {
            if (fn_info.params.len == 0) {
                sys();
            } else if (fn_info.params.len == 1) {
                sys(&GLOBAL_COMMANDS);
            } else if (fn_info.params.len == 2) {
                var query = QueryTransformVelocity{};
                sys(&query, &GLOBAL_TIME);
            }
        }
    }.runner;
}

pub const App = struct {
    allocator: std.mem.Allocator,
    systems: std.ArrayList(SystemFn),

    pub fn init(allocator: std.mem.Allocator) App {
        return App{
            .allocator = allocator,
            .systems = std.ArrayList(SystemFn).empty,
        };
    }

    pub fn add_system(self: App, comptime system_fn: anytype) App {
        var copy = self;
        const wrapped = wrapSystem(system_fn);
        _ = copy.systems.append(copy.allocator, wrapped) catch {};
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
