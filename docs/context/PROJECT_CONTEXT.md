# PROJECT_CONTEXT.md — Single Source of Truth

> Mọi con số, tên, quy ước ở đây là **luật**. Nếu trí nhớ của agent mâu thuẫn với file này, file này thắng. Chỉ sửa khi có quyết định cấp dự án và phải ghi ADR tương ứng trong `CONTRACTS_ADR.md`.

---

## 1. Project Metadata

| Trường | Giá trị |
|---|---|
| Tên mã dự án | `Project Vanguard` (mẫu — đổi khi dùng template) |
| Thể loại | 3D Action, góc nhìn thứ ba, chiến đấu theo state |
| Engine | **Unity 6 (6000.0 LTS)** |
| Ngôn ngữ | **C# 12** (`<LangVersion>12.0</LangVersion>`) |
| Render Pipeline | **Universal Render Pipeline (URP)**, SRP Batcher bật |
| Color Space | Linear |
| Scripting Backend | IL2CPP (build), Mono (editor) |
| API Compatibility | .NET Standard 2.1 |
| Input | Unity Input System (package `com.unity.inputsystem`), không dùng `UnityEngine.Input` cũ |
| Physics | Built-in PhysX 3D, `Physics.simulationMode = FixedUpdate`, `fixedDeltaTime = 1/60` |
| Target Platform | PC (Windows/Steam), Console (PS5/Xbox Series) |
| Target Frame Rate | **60 FPS khóa** (`Application.targetFrameRate = 60`, `vSyncCount = 1`) |
| Version control | Git + Git LFS cho `*.fbx *.png *.psd *.wav *.exr` |

---

## 2. Memory Budget & Performance Targets

Các ngưỡng này là **điều kiện pass** của pha QA. Đo trên bản Development Build, cảnh tham chiếu `Sandbox_Arena` (1 player, 30 enemy hoạt động, 200 projectile pool).

| Chỉ số | Ngân sách | Cách đo |
|---|---|---|
| Frame time tổng | **≤ 16.6 ms** (p99 ≤ 16.6 ms, không frame nào > 33 ms) | Profiler → CPU Usage; Frame Timing Manager |
| CPU main thread | ≤ 10.0 ms | Profiler Timeline |
| Render thread | ≤ 6.0 ms | Profiler Timeline |
| **Managed alloc / frame** | **0 Byte** ở trạng thái ổn định | Profiler → GC Alloc column; `Recorder "GC.Alloc"` |
| GC.Collect trong gameplay | 0 lần / 10 phút | `GC.CollectionCount(0)` delta |
| **Draw calls (Batches)** | **≤ 150** | Frame Debugger; Rendering Stats |
| SetPass calls | ≤ 60 | Rendering Stats |
| Triangles / frame | ≤ 1.5M | Rendering Stats |
| **Poly budget nhân vật** | **≤ 30,000 tris** (LOD0), LOD1 ≤ 12k, LOD2 ≤ 4k | Blender Statistics / Mesh Inspector |
| Poly budget enemy thường | ≤ 15,000 tris | như trên |
| Material / nhân vật | ≤ 3 | Renderer.sharedMaterials.Length |
| Bones / nhân vật | ≤ 75 (skin weights ≤ 4 / vertex) | Import settings |
| Texture nhân vật | ≤ 2048² (BC7), atlas dùng chung | Texture importer |
| Managed heap (steady state) | ≤ 256 MB | Memory Profiler |
| Total memory (console) | ≤ 3.5 GB | Memory Profiler |
| Load scene | ≤ 3.0 s (SSD) | Stopwatch log |
| Physics step | ≤ 1.5 ms | Profiler → Physics |
| Animator | ≤ 1.0 ms với 30 enemy | Profiler → Animation |

Ngân sách shadow: 1 directional cascade 2 tầng, distance ≤ 60 m. Realtime light ≤ 1 directional + 4 additional per object. Post-process: Bloom + Color Grading + Vignette; không SSAO ở console base.

---

## 3. Coding Standard Conventions

### 3.1 Naming

| Đối tượng | Quy tắc | Ví dụ |
|---|---|---|
| Namespace | `Vanguard.<Module>[.<Sub>]`, PascalCase | `Vanguard.Combat.Hitbox` |
| Class / struct / enum / interface | PascalCase; interface tiền tố `I` | `PlayerMotor`, `IDamageable` |
| Method / property / event | PascalCase | `ApplyDamage`, `IsGrounded` |
| Private field | `_camelCase` | `_moveDirection` |
| `[SerializeField]` private | `_camelCase` | `[SerializeField] private float _moveSpeed;` |
| Const / static readonly | PascalCase | `MaxPoolSize` |
| Local / parameter | camelCase | `deltaTime` |
| Enum value | PascalCase; enum flag đặt `[Flags]` và giá trị `1 << n` | `DamageType.Fire` |
| ScriptableObject asset | `SO_<Kind>_<Name>` | `SO_Weapon_Katana` |
| Prefab | `PF_<Kind>_<Name>` | `PF_Enemy_Grunt` |
| Material / Shader | `M_<Name>` / `SH_<Name>` | `M_ToonSkin`, `SH_ToonLit` |
| Texture | `T_<Name>_<D/N/M/E>` | `T_Hero_D` |
| Layer | PascalCase, danh sách cố định ở §3.4 | `PlayerHurtbox` |
| Async / coroutine | Cấm `async void`. Coroutine đặt tiền tố `Routine` | `RoutineFlashDamage` |

### 3.2 Quy tắc code

- `#nullable enable` trong assembly gameplay mới; dùng `[CanBeNull]`/`?` tường minh.
- Struct dữ liệu truyền qua sự kiện/hot path: `readonly struct`, `IEquatable<T>` (tránh boxing khi so sánh).
- Không `public` field trừ struct dữ liệu thuần; dùng `[field: SerializeField] public T Prop { get; private set; }`.
- `sealed` mặc định cho class không thiết kế để kế thừa.
- Một type public mỗi file; tên file = tên type.
- Magic number cấm; hằng số gameplay nằm trong ScriptableObject (`05_ECONOMY_BALANCER`); hằng số kỹ thuật dùng `const`.
- Cache `Animator.StringToHash`, `Shader.PropertyToID` vào `static readonly int`.
- Mọi `Physics` query dùng LayerMask cache sẵn, buffer cấp trước, phiên bản `NonAlloc`/`*Non Alloc` (Unity 6: `RaycastNonAlloc` hoặc overload `Span`/`QueryParameters`).
- Sự kiện `event Action` phải hủy đăng ký ở `OnDisable`. Cặp `+=`/`-=` bắt buộc đối xứng.
- Không `Find*`/`GetComponent*` trong runtime loop; reference truyền qua inspector hoặc service đã inject.
- Comment giải thích *tại sao*, không giải thích *cái gì*. Không comment code chết — xóa.

### 3.3 Assembly Definition (.asmdef) Architecture

Đồ thị phụ thuộc là **DAG một chiều**; cấm phụ thuộc vòng. Mũi tên = "được phép tham chiếu".

```
Vanguard.Core                (không phụ thuộc gì; interface, struct, EventBus, Pool, Math)
   ▲
   ├── Vanguard.Data         (ScriptableObject, JSON schema, formula)   → Core
   ├── Vanguard.Gameplay     (controller, camera, combat, physics)       → Core, Data
   ├── Vanguard.AI           (BT, FSM, perception, NavMesh glue)         → Core, Data, Gameplay(read-only interface)
   ├── Vanguard.Presentation (VFX, UI, audio, damage popup)              → Core, Data
   └── Vanguard.Bootstrap    (composition root, scene loader)            → tất cả
Vanguard.Editor              (tool, Blender import postprocessor)        → Core, Data  [Editor only]
Vanguard.Tests.EditMode      (NUnit)                                     → Core, Data, Gameplay, AI
Vanguard.Tests.PlayMode      (NUnit + Performance Testing)               → tất cả
```

| Assembly | Đường dẫn | Ghi chú `.asmdef` |
|---|---|---|
| `Vanguard.Core` | `Assets/_Project/Scripts/Core/` | `noEngineReferences: false`, `allowUnsafeCode: true` |
| `Vanguard.Data` | `Assets/_Project/Scripts/Data/` | refs: Core |
| `Vanguard.Gameplay` | `Assets/_Project/Scripts/Gameplay/` | refs: Core, Data, Unity.InputSystem, Unity.Cinemachine |
| `Vanguard.AI` | `Assets/_Project/Scripts/AI/` | refs: Core, Data, Unity.AI.Navigation |
| `Vanguard.Presentation` | `Assets/_Project/Scripts/Presentation/` | refs: Core, Data, Unity.TextMeshPro |
| `Vanguard.Bootstrap` | `Assets/_Project/Scripts/Bootstrap/` | refs: tất cả runtime |
| `Vanguard.Editor` | `Assets/_Project/Editor/` | `includePlatforms: [Editor]` |

Giao tiếp chéo module **chỉ** qua: (a) interface trong `Core`, (b) struct message trên `EventBus`, (c) ScriptableObject trong `Data`. Cấm `Gameplay` tham chiếu trực tiếp `AI` hoặc ngược lại ngoài interface.

### 3.4 Layer & Collision Matrix (nguồn sự thật — xem ADR-001)

| # | Layer | Va chạm với |
|---|---|---|
| 6 | `Environment` | Player, Enemy, Projectile, Ragdoll |
| 7 | `Player` | Environment, EnemyHitbox, Pickup |
| 8 | `Enemy` | Environment, PlayerHitbox, Projectile |
| 9 | `PlayerHitbox` | EnemyHurtbox |
| 10 | `PlayerHurtbox` | EnemyHitbox, EnemyProjectile |
| 11 | `EnemyHitbox` | PlayerHurtbox |
| 12 | `EnemyHurtbox` | PlayerHitbox, PlayerProjectile |
| 13 | `PlayerProjectile` | Environment, EnemyHurtbox |
| 14 | `EnemyProjectile` | Environment, PlayerHurtbox |
| 15 | `Pickup` | Player |
| 16 | `Perception` | (chỉ query, không va chạm vật lý) |

### 3.5 Cấu trúc thư mục Unity

```
Assets/_Project/
├── Art/            (Models, Materials, Textures, Animations, VFX)
├── Scripts/        (Core, Data, Gameplay, AI, Presentation, Bootstrap)
├── Editor/
├── Data/           (SO_*.asset, JSON)
├── Prefabs/
├── Scenes/         (Bootstrap.unity, Sandbox_Arena.unity)
├── Settings/       (URP assets, input actions, quality tiers)
└── Tests/
```

### 3.6 Git & Review

- Nhánh: `main` (luôn build được), `dev`, `feat/<milestone>-<slug>`, `fix/<slug>`, `perf/<slug>`.
- Commit theo Conventional Commits. Một commit = một ý.
- PR không merge nếu `scripts/verify.sh` đỏ hoặc QA Profiler verdict `FAIL`.
