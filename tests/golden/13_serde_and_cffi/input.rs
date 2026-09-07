use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
pub struct User {
    pub id: u64,
}

fn process_ptr(ptr: *const u8, mut_ptr: *mut u8) {
    let _ = ptr;
    let _ = mut_ptr;
}

fn main() {
    println!("Serde and CFFI test");
}
