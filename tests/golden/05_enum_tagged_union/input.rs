enum Shape {
    Circle,
    Square,
}

fn describe(s: Shape) {
    match s {
        Shape::Circle => println!("Circle"),
        Shape::Square => println!("Square"),
    }
}

fn main() {
    describe(Shape::Circle);
}
