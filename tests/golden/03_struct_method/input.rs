struct Point {
    x: i32,
    y: i32,
}

impl Point {
    fn area(&self) -> i32 {
        return self.x * self.y;
    }
}

fn main() {
    let p = Point { x: 3, y: 4 };
    let a = p.area();
    println!("Area: {}", a);
}
