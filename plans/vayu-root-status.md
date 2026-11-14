# Poco X3 Pro Root via CVE-2023-33107 — Status

Last updated: 2026-11-13

## Goal
Root → SELinux permissive → devinfo patch → `fastboot oem unlock` on Poco X3 Pro (vayu, MIUI V12.5.5.0.RJUEUXM, Android 11, kernel 4.14.180-perf).

## Device
- Model: 2201117TG (Poco X3 Pro vayu EEA)
- SoC: Snapdragon 860 (SM8150, Kryo 585, 8 cores, 4MB L3)
- Build: V12.5.5.0.RJUEUXM
- Kernel: 4.14.180-perf, `CONFIG_ARM64_PAN=y`
- adb shell (uid=2000), adb root unavailable

## Files
- **Exploit repo**: `/tmp/CVE-2023-33107/`
- **Target header**: `/tmp/CVE-2023-33107/src/targets/vayu-V12.5.5.0.RJUEUXM/target.h`
- **Binary**: `/tmp/CVE-2023-33107/build/vayu-V12.5.5.0.RJUEUXM/kgsl_root_su`
- **vmlinux (extracted from boot.img)**: `/private/tmp/claude-501/-Users-hellonfire-Coding-nura/fc68d650-22f5-4cb0-8273-f55e4360b27a/scratchpad/vmlinux.elf` (46MB)
- **Build command**:
  ```
  cd /tmp/CVE-2023-33107 && rm -rf build/vayu-V12.5.5.0.RJUEUXM && \
  PATH="$HOME/litedroid-work/dl/android-ndk-r27c/toolchains/llvm/prebuilt/darwin-x86_64/bin:$PATH" \
  make PROJECT=vayu-V12.5.5.0.RJUEUXM
  ```
- **Run command**:
  ```
  adb push build/vayu-V12.5.5.0.RJUEUXM/kgsl_root_su /data/local/tmp/
  adb shell "SEC_SID=1 SEC_PERMISSIVE=0 SEC_PROBE=1 SEC_DUMP=1 /data/local/tmp/kgsl_root_su"
  ```

## What Works Reliably
| Step | Status | Notes |
|------|--------|-------|
| KGSL UAF race | **Works** | Won on first try every run |
| Memory pressure drain | **Works** | ~1750 MiB, 6144 children |
| Task scan (comm markers) | **Works** | Finds 64 writable task_structs |
| Credential alias scan | **Works** | Finds 20-60 matching aliases |
| Root cred patching (uid=0, all caps) | **Works** | Verified via /proc/PID/status |
| KASLR slide derivation | **Works** | switch_continuation_off=0x6174 |
| SID=1 forge (GPU writes fake struct + cred->security) | **GPU write succeeds** | But CPU never sees it (cache coherency) |

## Confirmed Offsets (all from vmlinux + GPU probes)
```c
#define TARGET_TASK_STRIDE          0xE30
#define TARGET_TASK_STATE           0x58
#define TARGET_TASK_REAL_CRED       0x800
#define TARGET_TASK_CRED            0x808
#define TARGET_TASK_COMM            0x810
#define TARGET_TASK_TASKS           0x4E0
#define TARGET_TASK_PID             0x658
#define TARGET_TASK_TGID            0x65C
#define TARGET_TASK_GROUP_LEADER    0x698
#define TARGET_TASK_CPU_CONTEXT     0xC50   // vmlinux cpu_switch_to: mov x10,#0xc50
#define TARGET_TASK_FPSIMD          0xCD0
#define TARGET_CRED_SECURITY        0x78    // vmlinux selinux_cred_alloc_blank: str x0,[x19,#0x78]
#define TARGET_SWITCH_CONTINUATION_OFF  0x6174
#define TARGET_GADGET_STORE_OFF     0x3F5750   // str w20,[x19]; ldp...; ret
#define TARGET_GADGET_SWITCH_RETURN_OFF  0xE8990
#define TARGET_SELINUX_STATE_OFF    0x2a40b08  // from vmlinux nm
#define TARGET_KERNEL_TEXT_VA       0xffffff8008080000
```

## UNVERIFIED Offsets (the problem)
```c
#define TARGET_TASK_SECURITY        0xBE8  // ESTIMATE — never confirmed by probe
#define TARGET_TASK_FAKE_SEC        0xBF0  // security + 8 — depends on above
```

**These offsets control where the SID=1 fake struct is written inside the task_struct page.** If wrong, the GPU write lands on the wrong field, corrupting something else or writing to dead space. The cred->security pointer overwrite (at cred+0x78) is correct, but it points to `task + 0xBF0` which may not be a safe location.

## The Core Problem: GPU→CPU Cache Incoherence

### What happens
1. GPU writes SID=1 fake task_security_struct at `task_page + 0xBF0` via KGSL DMA
2. GPU writes new cred->security pointer at `cred + 0x78` pointing to the fake struct
3. Parent does per-core 8MB cache thrash on all 8 cores (added this session)
4. Child wakes up, also does 8MB cache thrash on its own core (added this session)
5. Child's kernel reads cred->security → **still sees old (shell) pointer**
6. All SELinux checks use old SID → child has root uid but shell SELinux domain
7. `open("/sys/fs/selinux/enforce", O_WRONLY)` → Permission denied
8. `open("/dev/block/by-name/*", O_RDONLY)` → Permission denied
9. No sec_dump.txt, no sec_ctx.txt, no dump files created

### Why cache thrash doesn't work
The SD860 (SM8150) has:
- Per-core L1 (64KB) + L2 (256KB) = 320KB per core
- Shared L3/LLC (4MB)
- KGSL DMA writes go to DRAM, bypassing all caches

The 8MB per-core thrash evicts L1/L2 reliably but may not evict the specific L3 cache set holding cred->security. L3 is set-associative — the thrash's physical pages may not map to the same cache sets as the cred's physical page.

**This same problem also killed the cpu_context hijack approach** (prior session). GPU-written cpu_context values were stale when cpu_switch_to loaded them → kernel panic.

### Evidence
- cred ID writes (uid=0) DO take effect — but these are verified by a different code path (GPU read-back, then /proc/PID/status CPU read on a different cache line)
- cred->security write NEVER takes effect — confirmed across multiple runs with different cache strategies
- SEC_DUMP block (child tries to open /dev/block/by-name/*) produces nothing
- sec_ctx.txt (child writes its own SELinux context) never created

## Two Secondary Bugs (fixed this session)

### 1. SEC_SID child never reached setenforce_permissive()
The SEC_SID block in child_loop ended with `for(;;) pause();` BEFORE the perm_go wait + setenforce_permissive() call. Fixed: added perm_go wait + setenforce_permissive() inside the SEC_SID block, right before the infinite pause.

### 2. Parent can't kill root child → waitpid hangs forever
After the exploit finishes, parent (uid=shell) tries `kill(child_pid, SIGKILL)` but child is uid=root → EPERM. Then `waitpid()` blocks forever. The child never exits because of `for(;;) pause();` + `prctl(PR_SET_PDEATHSIG, 0)`. Need to either: have the child exit on its own after setenforce, or have the parent not wait for it.

## Your Question: "Can't you find the offset from the boot image?"

**Yes — and this is probably the right approach.** The `task_security` offset (0xBE8) is an unverified estimate. If it's wrong, the SID forge writes to the wrong place and can't work regardless of cache coherency.

### How to verify task_security from vmlinux

The vmlinux is at `/private/tmp/claude-501/-Users-hellonfire-Coding-nura/fc68d650-22f5-4cb0-8273-f55e4360b27a/scratchpad/vmlinux.elf`.

**Method: disassemble selinux_task_alloc or task_security()**

The kernel function that reads `task->security` is `selinux_task_alloc()` or the LSM blob accessor. In 4.14 kernels (before LSM blob refactor), each task has a `void *security` pointer directly in `struct task_struct`. The offset can be found by disassembling:
- `selinux_task_getsid()` — reads task->security
- `selinux_task_getsecid()` — reads task->security
- `security_task_free()` → `selinux_task_free()` — reads task->security
- Or look at the `task_struct` definition in vmlinux DWARF info

```bash
# Find the offset used to access task->security:
aarch64-linux-android-objdump -d vmlinux.elf | grep -A20 'selinux_task_getsecid'
# Look for: ldr x?, [x?, #OFFSET]  — OFFSET is task_security
```

### Alternative: find it from the kernel source

The vayu kernel source (4.14.180-perf, MIUI) has the task_struct definition. The `security` field is near the end of task_struct, after `audit_context` and before the `cgroup` fields. On 4.14 with MIUI additions, it may be at a different offset than vanilla.

The Sony (SM8250, 4.19) reference has task_security at 0xAD8. The vayu kernel is 4.14 with MIUI additions (0x28 extra bytes after cred). The estimate of 0xBE8 was based on cpu_context being at 0xC50 and placing security before it, but this is just a guess.

## What To Do Next (Priority Order)

### 1. Verify task_security offset from vmlinux
Disassemble `selinux_task_getsecid` or similar from vmlinux.elf to find the exact `task->security` offset. This is the most likely reason the SID forge fails — if the offset is wrong, nothing else matters.

### 2. Consider alternative: direct selinux_state write via GPU
Instead of forging SID (which requires cred->security to be visible), write directly to the `selinux_state.enforcing` byte in kernel .bss. We already have:
- KASLR slide (working)
- selinux_state offset: 0x2a40b08 from _text
- So selinux_state VA = 0xffffff8008080000 + slide + 0x2a40b08

The problem: GPU IOVA range may not reach kernel .bss (it's in the linear map, not in the KGSL range). Need to check if KGSL SMMU mapping covers kernel virtual addresses.

### 3. Fix the cpu_context gadget hijack (if direct GPU write won't work)
The cpu_context hijack to write selinux_state.enforcing via a `str w20,[x19]; ret` gadget was abandoned due to cache coherency. But the SAME cache problem exists for the SID forge. So either:
- Find a way to explicitly invalidate CPU cache for the target address
- Use `IOCTL_KGSL_GPUMEM_SYNC_CACHE` on a still-live KGSL object overlapping the target
- Have the root child use `ptrace(PTRACE_PEEKDATA/POKEDATA)` on a kthread to read/write kernel memory (root + CAP_SYS_PTRACE, if SELinux allows under shell domain with uid=0)

### 4. Have the root child do it without SELinux bypass
The child already has uid=0 + all capabilities. Things it CAN do even with shell SELinux context:
- Write to /proc/sys/kernel/kptr_restrict (check — might work)
- Read /proc/kallsyms (if kptr_restrict lowered)
- ptrace a kthread (needs both root AND SELinux permission — probably blocked)
- Possibly: ioctl on specific devices that shell domain is allowed to access

### 5. Last resort: repeat exploit runs
The cache coherency failure is probabilistic. Running the exploit many times in a row (rebooting between each to clear KGSL pool) may eventually produce a run where the cache happens to be cold for the cred->security line. This is unreliable but might work.

## Code Changes Made This Session

### In `/tmp/CVE-2023-33107/src/main.c`:

1. **Removed broken memcpy to UAF pages** (~line 989): Removed `memcpy((void *)(uintptr_t)(root_child->page + ...))` that segfaulted because freed KGSL buffer's user mmap is torn down.

2. **Per-core 8MB cache thrash** (~line 3245): Replaced single-core 4MB flush with per-core thrash: `sched_setaffinity` to each of 8 cores, thrash 8MB, to evict L1/L2/L3.

3. **Skipped task_security GPU write in SID forge** (~line 3078): Removed the middle `gpu_write_words` that wrote to `root_child.page + task_security` — only write fake struct data and cred->security pointer.

4. **Cache flush before waking SID child** (~line 3127): Added per-core 8MB thrash between SID forge GPU writes and `action=1` futex wake, so the child sees fresh memory.

5. **Child-side cache thrash in SEC_SID block** (~line 1082): Added 8MB anonymous mmap thrash + 20ms usleep at the start of the SEC_SID child path.

6. **setenforce_permissive() in SEC_SID block** (~line 1486): Changed `for(;;) pause();` to: wait for perm_go → call setenforce_permissive() → set root_done=1 → then `for(;;) pause();`.

## KGSL Pool Exhaustion
After each exploit run, the KGSL driver pool is exhausted. **Must reboot device before retrying.** The orphaned root child process also can't be killed from shell (EPERM).

## Key Insight for Next Session
The most productive next step is verifying `task_security` from vmlinux. If that offset is wrong, the SID forge writes garbage to an unrelated field. Even if cache coherency were perfect, the SID wouldn't be forged correctly. Fix the offset first, then worry about cache.
