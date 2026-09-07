fn check_num(val: i32) -> Option<i32> {
    if val > 0 {
        return Some(val);
    }
    return None;
}

fn main() {
    let opt = check_num(5);
    println!("Val: {}", opt.unwrap());
}
