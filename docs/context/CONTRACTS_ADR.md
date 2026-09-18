# CONTRACTS_ADR.md — Core Interfaces & Architecture Decision Records

> Đây là **hợp đồng cứng** giữa các assembly. Thay đổi chữ ký = breaking change → phải có ADR mới, cập nhật mọi implementer trong cùng commit, và `06_QA_PROFILER` xác nhận không phát sinh alloc.
> Tất cả file thuộc assembly `Vanguard.Core` (`Assets/_Project/Scripts/Core/`).

---

## Part A — Core Interfaces

### A.1 `DamageData.cs` + `DamageType.cs`

```csharp
using System;
using UnityEngine;

namespace Vanguard.Core
{
    /// <summary>
    /// Loại sát thương. Dùng bit flag để một nguồn có thể mang nhiều hệ
    /// (ví dụ Fire | Explosive) và để Armor/Resist lọc bằng phép AND, không boxing.
    /// </summary>
    [Flags]
    public enum DamageType : ushort
    {
        None      = 0,
        Physical  = 1 << 0,
        Fire      = 1 << 1,
        Ice       = 1 << 2,
        Lightning = 1 << 3,
        Poison    = 1 << 4,
        Explosive = 1 << 5,
        True      = 1 << 6   // bỏ qua giáp và kháng tính
    }

    /// <summary>
    /// Gói dữ liệu một lần sát thương. readonly struct: truyền theo `in`, không alloc,
    /// không thể bị hệ khác sửa giữa đường. Kích thước xấp xỉ 40 byte trên x64.
    /// </summary>
    public readonly struct DamageData : IEquatable<DamageData>
    {
        /// <summary>Lượng sát thương thô, chưa qua giảm trừ giáp. Luôn ≥ 0.</summary>
        public readonly float Amount;

        /// <summary>Điểm chạm trong world space.</summary>
        public readonly Vector3 HitPoint;

        /// <summary>Pháp tuyến bề mặt tại điểm chạm, đã chuẩn hóa (|n| = 1). Dùng cho VFX và knockback.</summary>
        public readonly Vector3 HitNormal;

        public readonly DamageType DamageType;

        /// <summary>
        /// Nguồn gây sát thương. Có thể null (môi trường, DoT đã mất nguồn).
        /// Người nhận PHẢI kiểm tra null và kiểm tra `instigator.IsAlive`
        /// nếu object có thể đã trả về pool.
        /// </summary>
        public readonly GameObject Instigator;

        public DamageData(float amount, Vector3 hitPoint, Vector3 hitNormal,
                          DamageType damageType, GameObject instigator)
        {
            Amount     = amount < 0f ? 0f : amount;
            HitPoint   = hitPoint;
            HitNormal  = hitNormal;
            DamageType = damageType;
            Instigator = instigator;
        }

        public bool Equals(DamageData other) =>
            Amount.Equals(other.Amount) &&
            HitPoint.Equals(other.HitPoint) &&
            HitNormal.Equals(other.HitNormal) &&
            DamageType == other.DamageType &&
            ReferenceEquals(Instigator, other.Instigator);

        public override bool Equals(object obj) => obj is DamageData d && Equals(d);

        public override int GetHashCode() =>
            HashCode.Combine(Amount, HitPoint, HitNormal, (int)DamageType, Instigator);

        public static bool operator ==(in DamageData a, in DamageData b) => a.Equals(b);
        public static bool operator !=(in DamageData a, in DamageData b) => !a.Equals(b);
    }
}
```

### A.2 `IDamageable.cs`

```csharp
namespace Vanguard.Core
{
    /// <summary>
    /// Hợp đồng cho mọi thực thể nhận sát thương. Được implement bởi Hurtbox, không phải
    /// bởi root của nhân vật, để hỗ trợ hệ số theo vùng (đầu ×2, chân ×0.8).
    /// </summary>
    public interface IDamageable
    {
        /// <summary>false khi đã chết, đang miễn nhiễm (i-frame), hoặc đã trả về pool.</summary>
        bool IsAlive { get; }

        /// <summary>
        /// Áp sát thương. Truyền `in` để tránh copy struct qua interface call.
        /// </summary>
        /// <returns>
        /// Lượng sát thương THỰC SỰ trừ vào máu sau giảm trừ (≥ 0). Trả 0 khi bị bỏ qua.
        /// Người gọi dùng giá trị này cho damage popup, lifesteal, thống kê.
        /// </returns>
        /// <remarks>
        /// Không được ném exception, không được alloc. Phải idempotent theo từng hit id
        /// do tầng gọi đảm bảo (Weapon Trace chống trùng hit trong một swing).
        /// </remarks>
        float ApplyDamage(in DamageData damage);
    }
}
```

### A.3 `IPoolable.cs`

```csharp
namespace Vanguard.Core
{
    /// <summary>
    /// Vòng đời của object tái sử dụng. Pool gọi các hàm này; code khác KHÔNG gọi trực tiếp.
    /// </summary>
    public interface IPoolable
    {
        /// <summary>
        /// Được gọi NGAY SAU khi pool lấy object ra và đã SetActive(true).
        /// Reset toàn bộ trạng thái runtime: máu, velocity, cooldown, trail, particle,
        /// và ĐĂNG KÝ lại mọi event. Không giả định trạng thái từ lần dùng trước.
        /// </summary>
        void OnSpawnFromPool();

        /// <summary>
        /// Được gọi NGAY TRƯỚC khi pool SetActive(false) và đưa vào kho.
        /// HỦY ĐĂNG KÝ mọi event, dừng coroutine/tween, xóa tham chiếu tới object khác
        /// (target, instigator) để tránh giữ sống graph và tránh dangling reference.
        /// </summary>
        void OnReturnToPool();
    }
}
```

### A.4 `IState.cs`

```csharp
namespace Vanguard.Core
{
    /// <summary>
    /// Trạng thái của máy trạng thái phân cấp (ADR-002). TContext là dữ liệu dùng chung
    /// (Player/Enemy context). State là class sealed được tạo MỘT LẦN lúc khởi tạo máy
    /// và tái sử dụng — không `new` state trong runtime.
    /// </summary>
    public interface IState<in TContext>
    {
        /// <summary>Vào state. Reset timer nội bộ, bật animation, đăng ký input.</summary>
        void Enter(TContext context);

        /// <summary>
        /// Gọi mỗi Update. Chứa logic quyết định và chuyển state.
        /// Hot path: cấm alloc.
        /// </summary>
        void Tick(TContext context, float deltaTime);

        /// <summary>Gọi mỗi FixedUpdate. Chỉ chứa thao tác vật lý (velocity, force).</summary>
        void FixedTick(TContext context, float fixedDeltaTime);

        /// <summary>Rời state. Dọn tài nguyên, hủy đăng ký input. Phải an toàn khi gọi ngay sau Enter.</summary>
        void Exit(TContext context);
    }

    /// <summary>Phiên bản không context cho state độc lập.</summary>
    public interface IState
    {
        void Enter();
        void Tick(float deltaTime);
        void FixedTick(float fixedDeltaTime);
        void Exit();
    }
}
```

### A.5 Mẫu State Machine tối thiểu dùng với `IState<TContext>`

```csharp
using System;
using System.Collections.Generic;

namespace Vanguard.Core
{
    /// <summary>
    /// Máy trạng thái không alloc. State đăng ký một lần bằng Register; chuyển state
    /// qua khóa kiểu (Type) đã cache thành index, không dictionary lookup nóng.
    /// </summary>
    public sealed class StateMachine<TContext>
    {
        private readonly TContext _context;
        private readonly List<IState<TContext>> _states = new List<IState<TContext>>(16);
        private IState<TContext> _current;
        private int _pendingIndex = -1;

        public StateMachine(TContext context) => _context = context;

        public IState<TContext> Current => _current;

        /// <summary>Đăng ký state; trả về index dùng cho RequestTransition.</summary>
        public int Register(IState<TContext> state)
        {
            if (state == null) throw new ArgumentNullException(nameof(state));
            _states.Add(state);
            return _states.Count - 1;
        }

        /// <summary>
        /// Yêu cầu chuyển state; áp dụng ở đầu Tick kế tiếp để Exit/Enter không chạy
        /// giữa lúc state cũ đang Tick (tránh re-entrancy).
        /// </summary>
        public void RequestTransition(int index)
        {
            if ((uint)index >= (uint)_states.Count) throw new ArgumentOutOfRangeException(nameof(index));
            _pendingIndex = index;
        }

        public void Tick(float deltaTime)
        {
            ApplyPending();
            _current?.Tick(_context, deltaTime);
        }

        public void FixedTick(float fixedDeltaTime) => _current?.FixedTick(_context, fixedDeltaTime);

        private void ApplyPending()
        {
            if (_pendingIndex < 0) return;
            IState<TContext> next = _states[_pendingIndex];
            _pendingIndex = -1;
            _current?.Exit(_context);
            _current = next;
            _current.Enter(_context);
        }
    }
}
```

---

## Part B — Architecture Decision Records

### ADR-001 — Layer-based Collision Matrix + NonAlloc Raycasts, thay vì Trigger overlap liên tục

| Trường | Giá trị |
|---|---|
| Trạng thái | **Accepted** |
| Ngày | 2026-09-19 |
| Người quyết định | `01_GAME_ARCHITECT` (đồng thuận `02_GAMEPLAY_ENGINEER`, `06_QA_PROFILER`) |
| Liên quan | `PROJECT_CONTEXT §3.4`, M2-03, M2-04 |

**Bối cảnh.** Combat 3D cần biết "đòn nào trúng ai". Cách phổ biến là gắn `Collider` isTrigger lên vũ khí và bắt `OnTriggerEnter/Stay`. Ở 30–50 actor, cách này gây ba vấn đề đo được:

1. **Tunneling.** Lưỡi kiếm di chuyển 20 m/s ở 60 FPS đi 0.33 m mỗi frame; trigger dày 0.1 m nhảy qua mục tiêu giữa hai bước vật lý → miss ngẫu nhiên. Bật `CollisionDetectionMode.ContinuousDynamic` không áp dụng cho trigger kinematic.
2. **Chi phí broadphase liên tục.** Trigger luôn bật kể cả khi không đánh, làm PhysX tính overlap mỗi bước cho mọi cặp layer cho phép.
3. **Callback không kiểm soát.** `OnTriggerStay` chạy mỗi FixedUpdate mỗi cặp; cần tự chống hit lặp, và callback được marshal từ native sang managed (chi phí + nguy cơ alloc qua `Collider` wrapper).

**Quyết định.**

1. **Ma trận layer** khai báo một lần (bảng ở `PROJECT_CONTEXT §3.4`), áp dụng qua `Physics.IgnoreLayerCollision` lúc bootstrap và khai báo trong `ProjectSettings/TagManager` + Physics matrix. Hitbox và Hurtbox nằm ở layer riêng, nên một query chỉ chạm đúng tập cần thiết.
2. **Không dùng `OnTriggerStay`.** Cấm trong `Vanguard.Gameplay` (analyzer/grep kiểm tra).
3. **Weapon Trace chủ động** chỉ trong *Active frames* của đòn đánh: mỗi `FixedTick`, với mỗi socket, quét đoạn `prevPos → currPos` bằng `Physics.SphereCastNonAlloc` (hoặc `RaycastNonAlloc` cho đầu mũi), `LayerMask` = `EnemyHurtbox` (hoặc `PlayerHurtbox`), vào **buffer `RaycastHit[]` cấp trước** (kích thước 16, dùng chung theo thread).
4. Số sub-step = `ceil(distance / (radius * 1.5f))`, tối đa 4, để không bỏ sót mục tiêu mỏng.
5. Chống trùng hit bằng `HashSet<int>`-tương-đương dạng mảng `int[]` chứa `instanceID` của Hurtbox đã trúng trong swing hiện tại (xóa ở `Enter` của Active state).
6. Overlap tĩnh (vùng nổ, aura) dùng `Physics.OverlapSphereNonAlloc` một lần khi kích hoạt, không giữ trigger.

**Hệ quả.**

- (+) Không tunneling ở vận tốc thiết kế; hành vi xác định, dễ test bằng số.
- (+) Zero-GC: mọi query ghi vào buffer cấp trước.
- (+) Chi phí vật lý tỉ lệ với số đòn đang *thực sự active*, không tỉ lệ với số actor.
- (−) Phải quản lý vòng đời trace thủ công (bật ở Active, tắt ở Recovery).
- (−) Buffer đầy → mất hit. Giảm thiểu: size 16 + log cảnh báo (`Conditional`) khi `hitCount == buffer.Length`.

**Phương án bị loại.** (a) Trigger + `OnTriggerStay`: xem trên. (b) `Physics.RaycastAll`/`SphereCastAll`: cấp phát mảng mỗi lần gọi. (c) `Rigidbody` continuous trên vũ khí: đắt, không kiểm soát được cửa sổ hit.

**Kiểm chứng.** M2-03, M2-04: 1,000 lần swing 20 m/s vào target dày 0.1 m → 0 miss, 0 B GC Alloc.

---

### ADR-002 — State Pattern thay vì Monolithic Switch-Case FSM cho Character Controller

| Trường | Giá trị |
|---|---|
| Trạng thái | **Accepted** |
| Ngày | 2026-09-19 |
| Người quyết định | `01_GAME_ARCHITECT` (đồng thuận `02_GAMEPLAY_ENGINEER`) |
| Liên quan | `IState`, M1-06, M2-05 |

**Bối cảnh.** Character Controller có ≥ 10 trạng thái (Idle, Run, Jump, Fall, Dash, AttackWindup/Active/Recovery, HitStun, Block, Dead). Cách ban đầu là một `enum State` với `switch` trong `Update` và `FixedUpdate`.

Vấn đề với switch-case đơn khối:

1. **Bùng nổ điều kiện.** Mỗi state mới sửa `switch` ở 2–3 nơi (Update, FixedUpdate, transition table); dễ quên nhánh `Exit` khi thoát bằng đường bất thường. Kết quả là bug "kẹt state" (ví dụ vẫn còn cờ `isDashing` sau khi bị stun).
2. **Dữ liệu tạm rò rỉ.** Biến của mọi state nằm chung một class (`dashTimer`, `comboIndex`, `stunTimer`) nên bị dùng sai ngữ cảnh.
3. **Không test cô lập được.** Không thể unit-test `DashState` mà không dựng cả controller.
4. **Vi phạm Open/Closed:** thêm `WallRunState` = sửa file lõi đã ổn định.

**Quyết định.**

1. Mỗi trạng thái là một class `sealed` implement `IState<PlayerContext>` (`Enter/Tick/FixedTick/Exit`), sở hữu dữ liệu tạm của riêng nó.
2. State được **tạo một lần** ở khởi tạo và đăng ký vào `StateMachine<TContext>` (xem A.5) — không `new` state khi chạy → Zero-GC.
3. Chuyển state bằng `RequestTransition(index)`; áp dụng ở đầu `Tick` kế tiếp (không re-entrancy).
4. Dữ liệu chia sẻ (velocity, grounded, input buffer, stats) nằm trong `PlayerContext` (struct nhóm + class giữ tham chiếu), không nằm trong state.
5. Điều kiện chuyển state do **state đang chạy** quyết định (state biết nó có thể đi đâu), giữ transition cục bộ.
6. Tính tổ hợp (vừa chạy vừa cầm khiên) dùng *layer/sub-state machine* thứ hai (ví dụ Locomotion × Upper-body), không nhân số state.

**Hệ quả.**

- (+) Thêm state = thêm 1 file, không sửa state khác.
- (+) `Exit` luôn chạy khi rời state → không kẹt cờ.
- (+) Test cô lập từng state bằng `TContext` giả.
- (+) Không alloc lúc chạy; gọi virtual qua interface (~2 ns) không đáng kể so với lợi ích.
- (−) Nhiều file/class hơn (≈ 12 file thay vì 1).
- (−) Cần kỷ luật để không để state gọi trực tiếp state khác (chỉ qua `RequestTransition`).

**Phương án bị loại.** (a) Switch-case đơn khối: xem trên. (b) `Animator` làm FSM logic: khó test, ràng buộc gameplay vào graph animation, và transition dựa trên chuỗi tên. (c) Behavior Tree cho player: thừa; BT dành cho AI (xem `04_AI_DESIGNER`).

**Kiểm chứng.** M1-06/M2-05: chuyển 10,000 state/giây → 0 B GC Alloc; test đơn vị cho từng state.

---

## Part C — Mẫu ADR mới

```markdown
### ADR-NNN — <Quyết định>
| Trường | Giá trị |
|---|---|
| Trạng thái | Proposed / Accepted / Superseded by ADR-MMM |
| Ngày | YYYY-MM-DD |
| Người quyết định | <role> |
**Bối cảnh.** <vấn đề, số liệu>
**Quyết định.** <đánh số, cụ thể>
**Hệ quả.** (+) ... (−) ...
**Phương án bị loại.** ...
**Kiểm chứng.** <AC đo được>
```
