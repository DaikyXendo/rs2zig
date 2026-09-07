fn setup_system() {
    println!("Initializing Bevy ECS Startup System...");
}

fn update_system() {
    println!("Running Bevy ECS Update System...");
}

fn main() {
    App::new()
        .add_systems(Startup, setup_system)
        .add_systems(Update, update_system)
        .run();
}
