use bevy::prelude::*;

pub fn setup(mut commands: Commands) {
    commands.spawn((
        Transform::from_xyz(0.0, 0.0, 0.0),
        Velocity { x: 10.0, y: 5.0 },
    ));
}

pub fn movement_system(mut query: Query<(&mut Transform, &Velocity)>, time: Res<Time>) {
    for (mut transform, velocity) in query.iter_mut() {
        transform.x += velocity.x * time.delta_seconds();
        transform.y += velocity.y * time.delta_seconds();
    }
}

fn main() {
    App::new()
        .add_systems(Startup, setup)
        .add_systems(Update, movement_system)
        .run();
}
