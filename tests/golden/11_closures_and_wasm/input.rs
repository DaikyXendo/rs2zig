fn main() {
    let closure = |x: i32| x + 1;
    let res = closure(10);
    println!("Result: {}", res);
}
