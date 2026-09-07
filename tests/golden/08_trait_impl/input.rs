trait Speaker {
    fn speak(&self);
}

struct Dog {}

impl Speaker for Dog {
    fn speak(&self) {
        println!("Woof");
    }
}

fn main() {
    let d = Dog {};
    d.speak();
}
