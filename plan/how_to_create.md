# Plan chi tiết: Xây dựng công cụ chuyển đổi Rust → Zig bằng Python (mục tiêu: chạy được dự án Bevy)

## 0. Đánh giá thực tế trước khi bắt đầu (quan trọng)

Cần nói thẳng: **chuyển đổi tự động 100% một dự án Bevy sang Zig là bài toán cực kỳ khó**, tương đương độ khó với việc viết một phần trình biên dịch Rust. Lý do:

- Bevy dùng rất nhiều **proc-macro** (`#[derive(Component)]`, `#[derive(Resource)]`, `#[system]`-style API, `bevy_reflect`...) sinh code tại compile-time.
- Rust có **generics + trait bound + trait object (`dyn Trait`)**, Zig không có khái niệm tương đương 1:1 (Zig dùng `comptime` duck-typing).
- Rust có **borrow checker/lifetime**, Zig không kiểm tra ownership — cần chiến lược cấp phát bộ nhớ thủ công (allocator).
- Hệ sinh thái crate (winit, wgpu, wgpu-hal, naga...) không có bản Zig tương đương → cần re-implement hoặc FFI.

→ Chiến lược đúng đắn: **xây tool theo hướng "mở rộng dần tập con Rust được hỗ trợ" (progressive subset)**, có **milestone thực tế đầu tiên là một Bevy "hello world" ECS đơn giản, headless (không render)**, chứ không nhắm thẳng vào toàn bộ engine đồ họa. Plan dưới đây phản ánh đúng cách tiếp cận đó.

---

## 1. Kiến trúc tổng thể (pipeline)

```
Rust source (.rs)
   │
   ▼
[0] Macro Expansion Pass  ──(gọi `cargo expand` / rustc)──► Rust "vanilla" (đã expand macro)
   │
   ▼
[1] Parser (tree-sitter-rust qua Python binding)  ──► Concrete Syntax Tree (CST)
   │
   ▼
[2] AST Builder (Python)  ──► AST nội bộ (dataclass-based)
   │
   ▼
[3] Semantic Analyzer / Type Resolver (Python)  ──► Typed IR (có thông tin kiểu, ownership, lifetime đã "xóa")
   │
   ▼
[4] Lowering Passes (Rust idioms → Zig idioms)
      - Option/Result → ?T / error union
      - Vec/HashMap/String → std.ArrayList / std.HashMap / []u8
      - Box/Rc/Arc → allocator + con trỏ
      - trait → comptime interface / vtable struct
      - enum có data → tagged union
   │
   ▼
[5] Zig Codegen (Python, dùng AST → string builder có format)
   │
   ▼
[6] Post-process: chạy `zig fmt`, `zig build-obj` để validate cú pháp
   │
   ▼
Zig source (.zig) + build.zig
   │
   ▼
[7] Differential Test Runner: build & run cả bản Rust lẫn Zig, so sánh output
```

**Nguyên tắc thiết kế cốt lõi:** mỗi pass là 1 module Python độc lập, có thể test riêng bằng golden-file test (input .rs cụ thể → expected .zig cụ thể).

---

## 2. Quyết định công nghệ then chốt

| Vấn đề | Lựa chọn khuyến nghị | Lý do |
|---|---|---|
| Parse Rust | `tree-sitter` + grammar `tree-sitter-rust`, gọi qua Python binding `py-tree-sitter` | Viết lại grammar Rust bằng tay trong Python là bất khả thi để đạt độ chính xác cao; tree-sitter là parser CST đã được kiểm chứng, nhanh, lỗi-khoan-dung |
| Macro expansion | Gọi subprocess `cargo expand` (yêu cầu máy có toolchain Rust cài sẵn) | Đây là "cửa sau" bắt buộc — không ai viết lại proc-macro expander cho Bevy trong thời gian ngắn. Sau khi expand, ta chỉ còn Rust thuần, dễ convert hơn nhiều |
| Semantic/type info | Tự viết type inference engine đơn giản (Hindley-Milner rút gọn) bằng Python | Cần biết kiểu để chọn đúng phép ánh xạ Zig (vd `i32` vs generic `T`) |
| Codegen | String-builder AST → Zig source, không dùng template thô | Đảm bảo format nhất quán, dễ debug qua từng pass |
| Validate | Gọi `zig build-obj`/`zig ast-check` sau mỗi lần sinh code | Bắt lỗi cú pháp Zig ngay, feedback loop nhanh cho agent |
| Build system | Sinh `build.zig` song song với Cargo.toml dependency graph | Ánh xạ crate → package Zig (thủ công, từng crate một) |

---

## 3. Cấu trúc thư mục dự án

```
rust2zig/
├── rust2zig/
│   ├── frontend/
│   │   ├── macro_expand.py     # gọi cargo expand
│   │   ├── ts_parser.py        # wrap tree-sitter
│   │   └── ast_builder.py      # CST -> AST nội bộ
│   ├── ir/
│   │   ├── nodes.py            # dataclass AST node definitions
│   │   ├── type_resolver.py
│   │   └── ownership_pass.py   # xử lý move/borrow -> memory strategy
│   ├── lowering/
│   │   ├── stdlib_map.py       # Vec->ArrayList, String->[]u8, ...
│   │   ├── trait_lowering.py
│   │   ├── enum_lowering.py
│   │   └── error_lowering.py   # Result/Option -> error union/optional
│   ├── backend/
│   │   ├── zig_emitter.py
│   │   └── build_zig_gen.py
│   ├── validate/
│   │   ├── zig_fmt_check.py
│   │   └── diff_test_runner.py
│   └── cli.py
├── tests/
│   ├── golden/                 # input.rs -> expected.zig, chạy theo cấp độ
│   │   ├── 01_hello_world/
│   │   ├── 02_structs/
│   │   ├── ...
│   │   └── 99_bevy_minimal/
│   └── e2e/
├── corpus/                     # kho các file rust thật để test dần lên
└── docs/mapping_table.md       # bảng ánh xạ ngữ nghĩa Rust<->Zig, cập nhật liên tục
```

---

## 4. Roadmap theo Phase (từ đơn giản → phức tạp)

### Phase 0 — Nền móng (1-2 tuần công việc agent)
- Dựng pipeline rỗng (parse → in lại AST dạng JSON, chưa sinh Zig).
- Viết bộ test harness: mỗi test case là 1 thư mục `input.rs`, `expected.zig`, `notes.md`.
- Định nghĩa **Rust Feature Support Matrix** (xem bảng mục 5) — agent tick dần khi hỗ trợ.

**Exit criteria:** parser đọc được file `.rs` bất kỳ, xuất ra cây cú pháp, không crash trên corpus mẫu.

### Phase 1 — Core ngôn ngữ (functions, kiểu nguyên thủy, control flow)
Hỗ trợ:
- `fn`, tham số, kiểu trả về, `let`, `mut`
- Kiểu số (`i32,u32,f64,bool,char,usize`...) → Zig tương ứng (`i32,u32,f64,bool,u21,usize`)
- `if/else`, `while`, `loop`, `for x in range`, `match` đơn giản (không pattern phức tạp)
- Toán tử số học, so sánh, logic
- `struct` không generic, method impl không trait

**Exit criteria:** convert & build thành công 20-30 hàm Rust thuần thuật toán (fibonacci, sort, struct point 2D...) và output runtime giống hệt bản Rust.

### Phase 2 — Sở hữu & bộ nhớ (ownership → allocator model)
- Rust `String`, `Vec<T>`, `&T`, `&mut T`, `Box<T>` →
  - `String` → `[]u8` (owned) + cần allocator
  - `Vec<T>` → `std.ArrayList(T)`
  - `&T`/`&mut T` → con trỏ Zig `*const T` / `*T`
  - `Box<T>` → cấp phát qua allocator, trả về `*T`
- Quyết định **chiến lược allocator toàn cục**: dùng `std.heap.GeneralPurposeAllocator` mặc định, truyền `allocator` qua tham số hàm khi cần cấp phát (giống convention chuẩn của Zig).
- Xử lý `drop`/`Drop trait` → gọi `deinit()` tương ứng ở cuối scope (agent cần tự chèn defer).

**Exit criteria:** convert được các hàm thao tác `Vec`, `String`, cấu trúc dữ liệu linked-list đơn giản, không leak memory (kiểm bằng GPA leak detector của Zig).

### Phase 3 — Enum & Pattern Matching
- `enum` có data (giống Rust ADT) → Zig **tagged union** (`union(enum)`)
- `match` đầy đủ pattern (destructure, guard, `_`) → Zig `switch`
- `Option<T>` → `?T`
- `Result<T,E>` → Zig error union `E!T` (cần ánh xạ error type Rust sang Zig `error{...}` set)

**Exit criteria:** convert code dùng `Option`/`Result`/`match` phức tạp, propagate lỗi bằng `?` operator → Zig `try`.

### Phase 4 — Trait & Generics (phần khó nhất trước macro)
- Generic function `fn foo<T>(x: T)` → Zig generic qua `comptime T: type`
- Trait đơn giản (không object-safety phức tạp) → chuyển thành **Zig interface pattern**: struct chứa function pointer hoặc dùng `comptime` duck-typing (nếu chỉ dùng static dispatch)
- `dyn Trait` (dynamic dispatch) → dựng **vtable struct thủ công** trong Zig (đây là phần rủi ro cao, cần thư viện hỗ trợ runtime riêng: `rust2zig_runtime.zig`)
- `impl Trait for Type` → gắn method trực tiếp vào struct tương ứng, kiểm tra trùng tên.

**Exit criteria:** convert được ví dụ có 1 trait, 2-3 struct implement, dùng cả static và dynamic dispatch cơ bản.

### Phase 5 — Macro Expansion Integration (bắt buộc cho Bevy)
- Tích hợp bước gọi `cargo expand` **trước** khi đưa vào tree-sitter.
- Xử lý các macro derive phổ biến của Bevy: `Component`, `Resource`, `Event`, `Reflect` → sau khi expand sẽ chỉ còn `impl Trait for Struct { ... }` thuần, Phase 4 xử lý được.
- Cảnh báo: một số macro sinh code dùng cơ chế mà Zig không có tương đương (vd `bevy_reflect` dùng runtime type info nâng cao) → **loại các macro này ra khỏi milestone đầu, đánh dấu "unsupported – cần stub thủ công"**.

**Exit criteria:** một crate nhỏ dùng `#[derive(Component)]` build thành công bằng Zig.

### Phase 6 — Xây "Bevy ECS Minimal" thủ công song song
Đây là bước khác biệt quan trọng: **không cố convert toàn bộ `bevy_ecs` crate**, mà:
1. Viết tay một **runtime ECS tối giản bằng Zig** (`rust2zig_ecs_runtime.zig`) mô phỏng đúng API bề mặt của `bevy_ecs` (World, Entity, Component storage, System scheduler đơn giản, Query).
2. Cấu hình tool coi `bevy_ecs::*`, `bevy_app::*` là **"known library"** — thay vì convert source, ánh xạ trực tiếp lời gọi API sang runtime Zig viết tay ở bước 1 (giống cách ta ánh xạ `Vec` → `ArrayList`).
3. Code người dùng (game logic, systems, components) mới thực sự chạy qua pipeline convert tự động.

**Đây chính là milestone khả thi để "chạy được 1 dự án Rust Bevy":** không phải convert Bevy engine, mà convert **code ứng dụng dùng Bevy**, còn engine core dùng bản runtime Zig viết tay tối giản (tương tự cách nhiều dự án port engine chỉ port phần logic, giữ lại core bằng binding).

**Exit criteria:** một app Rust kiểu:
```rust
fn main() {
    App::new()
        .add_systems(Startup, spawn_player)
        .add_systems(Update, move_player)
        .run();
}
```
được convert & chạy bằng Zig, in log/di chuyển entity đúng như bản Rust (headless, không cần render).

### Phase 7 — Mở rộng: rendering/windowing (giai đoạn xa, có thể để sau)
- Nếu muốn có cửa sổ + render thật: khuyến nghị **FFI hybrid** thay vì convert `wgpu`/`winit`:
  - Biên dịch `winit`+`wgpu` giữ nguyên dạng Rust `cdylib`, expose C ABI.
  - Zig gọi qua `@cImport`/FFI vào thư viện Rust đó.
  - Đây KHÔNG phải "convert", mà là interop — cần nói rõ với agent đây là lựa chọn thực dụng, không phải giả vờ đã convert được graphics stack.

---

## 5. Bảng ánh xạ ngữ nghĩa cốt lõi (living document, agent cập nhật liên tục)

| Rust | Zig | Ghi chú |
|---|---|---|
| `Vec<T>` | `std.ArrayList(T)` | cần allocator |
| `String`/`&str` | `[]u8` / `[]const u8` | Rust String owned, &str borrowed |
| `Option<T>` | `?T` | |
| `Result<T,E>` | `E!T` | cần map error enum |
| `Box<T>` | `*T` (heap alloc) | |
| `Rc<T>`/`Arc<T>` | struct wrapper tự viết có refcount (`RcBox(T)`) | Zig không có sẵn |
| `HashMap<K,V>` | `std.HashMap(K,V,...)` | |
| enum có data | `union(enum)` | |
| `match` | `switch` | |
| trait (static) | `comptime` duck-typing | |
| `dyn Trait` | vtable struct thủ công | |
| `?` operator | `try` | |
| `impl Drop` | `deinit()` + `defer` | |
| closure | Zig anonymous struct + function, hoặc tuple capture thủ công | Zig không có closure gọn như Rust, cần lowering đặc biệt |
| `unsafe {}` | bỏ block wrapper, giữ nguyên logic (Zig quản lý unsafe khác) | |
| `macro_rules!` | cần expand trước, không convert macro definition | |
| async/await | **không hỗ trợ ở giai đoạn đầu**, đánh dấu unsupported | Bevy dùng `bevy_tasks` (thread pool), có thể map sang `std.Thread` thủ công sau |

---

## 6. Chiến lược kiểm thử (bắt buộc để đảm bảo "chuẩn xác")

1. **Golden file test**: mỗi feature nhỏ có `input.rs` / `expected.zig` cố định, chạy CI mỗi lần sửa code.
2. **Differential testing**: với các test phức tạp hơn, không so sánh source code Zig, mà **build cả 2 bản, chạy, so sánh output/stdout/exit code**.
3. **Property-based fuzz nhẹ**: sinh ngẫu nhiên các biểu thức số học/control-flow đơn giản, convert, chạy, so kết quả — bắt lỗi edge-case sớm.
4. **Corpus tăng dần độ khó**: tổ chức thư mục `corpus/` từ mã tự viết → mã từ crate nhỏ trên crates.io (không phụ thuộc ngoài) → cuối cùng là ví dụ chính thức `bevy/examples/ecs/*.rs` (không phải ví dụ render).
5. **Regression tracking**: agent giữ file `docs/support_matrix.md` liệt kê % feature Rust được hỗ trợ, tự động cập nhật qua test suite.

---

## 7. Rủi ro cần agent lường trước & cách xử lý

| Rủi ro | Mức độ | Xử lý |
|---|---|---|
| Proc-macro không expand được (macro custom phức tạp của bên thứ 3) | Cao | Bắt lỗi rõ ràng, báo "unsupported macro", không cố convert mù |
| Generic phức tạp (higher-kinded, associated types) | Cao | Giới hạn phạm vi hỗ trợ generics ở version đầu, liệt kê rõ trong support matrix |
| Lifetime phức tạp ảnh hưởng đến layout bộ nhớ | Trung bình | Dùng chiến lược allocator đơn giản, chấp nhận có thể kém tối ưu hơn Rust gốc ở bản đầu |
| `unsafe`/FFI/SIMD trong code Bevy internals | Cao | Không convert engine core — dùng runtime Zig viết tay (Phase 6) |
| Zig thay đổi API nhanh (ngôn ngữ đang phát triển) | Trung bình | Pin phiên bản Zig cụ thể (khuyến nghị 0.13/0.14 tùy thời điểm), test lại khi upgrade |
| Rendering stack (wgpu/winit) | Rất cao | Dùng FFI hybrid thay vì convert (Phase 7), nói rõ đây là giải pháp thực dụng |

---

## 8. Checklist cụ thể để agent bắt đầu ngay

1. Cài môi trường: Python ≥3.10, `pip install tree_sitter tree_sitter_languages`, Rust toolchain (`cargo install cargo-expand`), Zig compiler (pin version cụ thể).
2. Viết `frontend/ts_parser.py`: load grammar rust, parse 1 file mẫu `fn main() { println!("hi"); }`, in ra CST — xác nhận pipeline chạy được.
3. Viết `ir/nodes.py` định nghĩa `FnDecl, StructDecl, Expr, Stmt...` bằng `@dataclass`.
4. Viết `backend/zig_emitter.py` sinh Zig source từ IR đơn giản nhất (function rỗng).
5. Chạy `zig build-obj` để validate, lặp cho tới khi hello-world build được.
6. Từ đó đi theo đúng thứ tự Phase 1 → Phase 6 ở trên, mỗi phase có bộ test golden riêng trước khi sang phase tiếp theo, không nhảy cóc.
7. Sau mỗi phase, cập nhật `docs/support_matrix.md` và chạy lại toàn bộ `tests/golden/` để đảm bảo không có regression.
8. Chỉ bắt đầu Phase 5 (macro expansion) khi Phase 1-4 đã đạt >90% test pass trên corpus tương ứng.
9. Milestone cuối (Phase 6) coi là "thành công" khi: một Bevy app headless dùng `add_systems`, `Component`, `Resource`, `Query` cơ bản chạy đúng bằng Zig, output khớp 100% với bản Rust gốc trên cùng input.

---

## 9. Ghi chú quan trọng khi giao việc cho agent

- Agent nên làm việc **theo từng commit nhỏ, mỗi commit tương ứng 1 feature trong support matrix**, không viết toàn bộ pipeline cùng lúc rồi mới test.
- Ưu tiên **feedback loop nhanh**: mỗi lần sinh code Zig, chạy `zig build-obj`/`zig ast-check` ngay lập tức để bắt lỗi cú pháp, không đợi đến cuối.
- Khi gặp construct Rust chưa hỗ trợ, agent nên **raise lỗi rõ ràng có vị trí dòng/cột**, không cố "đoán" convert sai lệch âm thầm — độ chính xác quan trọng hơn độ phủ.
- Bevy thay đổi API khá nhanh giữa các version — agent nên pin version Bevy cụ thể (vd 0.14/0.15) khi xây "Bevy ECS Minimal runtime" để tránh API drift.
