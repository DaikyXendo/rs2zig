fn identity<T>(x: T) -> T {
    return x;
}

fn main() {
    let val = identity(42);
    println!("Val: {}", val);
}
