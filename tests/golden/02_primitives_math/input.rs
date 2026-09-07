fn add(a: i32, b: i32) -> i32 {
    let mut sum: i32 = a + b;
    if sum > 10 {
        sum = sum * 2;
    }
    return sum;
}

fn main() {
    let result = add(5, 7);
    println!("Result: {}", result);
}
