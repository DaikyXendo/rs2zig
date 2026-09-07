use std::thread;

fn worker_task() {
    println!("Running background thread task");
}

fn main() {
    let handle = thread::spawn(worker_task);
    let _ = handle;
}
