"""
COMPREHENSIVE MERKEL PARITY TEST
===================================
Probes the CTI binary for exact h_sat values at every integration point
across a wide matrix of temperature ranges and altitudes, then computes
KaV/L from those exact binary values (ground truth) vs our new table engine
(merkel_tables_10m_018F.bin).

Tests:
  • 8 altitude levels  (0m, 110m, 250m, 500m, 750m, 1000m, 1500m, 2000m)
  • 5 temperature sets  (cold / medium / hot / high-temp / high-range)
  • 4 LG ratios         (0.75, 1.0, 1.5, 2.0)
  = up to 160 test cases

Method:
  Binary truth  — probe MerkelPsychro_imperial (0x407723) at exact P and T,
                  compute KaV/L from those exact h_sat values
  Table engine  — load merkel_tables_10m_018F.bin, exact 0.018°F grid lookup,
                  linear P-interpolation between 10m altitude levels

Usage:
    cd "f:\\2026 latest\\cti Toolkit\\cti_crack"
    python work/merkel_parity_comprehensive.py
"""
import os, sys, ctypes, struct, time, math, array as arr_mod

sys.stdout.reconfigure(line_buffering=True)
def P(s): print(s, flush=True)

try:
    import win32process
except ImportError:
    P("pip install pywin32"); sys.exit(1)

KERNEL32  = ctypes.windll.kernel32
EXE_PATH  = r"f:\2026 latest\cti Toolkit\cti_crack\official\cti toolkit\CTIToolkit.exe"
ADDR_EP   = 0x004569CE
FUNC_HSAT = 0x407723

# ─── Table engine setup ────────────────────────────────────────────────────
BIN_PATH   = os.path.join(os.path.dirname(__file__), "merkel_tables_10m_018F.bin")
T_START_F  = 50.0
T_STEP_F   = 9.0 / 500.0   # 0.018°F
N_TEMPS    = 8334
ALT_LEVELS = list(range(0, 2001, 10))   # 201 levels

def alt_to_psi(alt_m):
    if alt_m == 0: return 14.696
    alt_ft = alt_m / 0.3048
    x = alt_ft / 10000.0
    return ((0.547462*x - 7.67923)*x + 29.9309) * 0.491154 / (0.10803*x + 1.0)

P_LEVELS = [alt_to_psi(a) for a in ALT_LEVELS]

P("Loading binary table...")
_table = arr_mod.array("d")
with open(BIN_PATH, "rb") as f:
    _table.frombytes(f.read())
assert len(_table) == len(ALT_LEVELS) * N_TEMPS, "Table size mismatch"
P(f"  Loaded {len(_table):,} float64 values from {BIN_PATH.split(chr(92))[-1]}")

def _fpws_table(T_F, P_psi):
    """Exact table lookup (0.018°F grid) + linear P-interpolation."""
    n = len(P_LEVELS)
    idx_T_raw = (T_F - T_START_F) / T_STEP_F
    idx_T = round(idx_T_raw)            # exact for all 0.1°C inputs
    idx_T = max(0, min(N_TEMPS - 1, idx_T))

    if P_psi >= P_LEVELS[0]:            # above sea level
        return math.exp(_table[0 * N_TEMPS + idx_T])
    if P_psi <= P_LEVELS[-1]:           # above 2000m
        return math.exp(_table[(n-1) * N_TEMPS + idx_T])

    lo = 0
    for k in range(n - 1):
        if P_psi >= P_LEVELS[k + 1]: lo = k; break
    hi = lo + 1
    frac = (P_psi - P_LEVELS[lo]) / (P_LEVELS[hi] - P_LEVELS[lo])
    ln_lo = _table[lo * N_TEMPS + idx_T]
    ln_hi = _table[hi * N_TEMPS + idx_T]
    return math.exp(ln_lo + frac * (ln_hi - ln_lo))

def h_sat_table(P_psi, T_F):
    fp  = _fpws_table(T_F, P_psi)
    d   = P_psi - fp
    if d <= 0: return 999.0
    Ws  = 0.62198 * fp / d
    return 0.24 * T_F + Ws * (1061.0 + 0.444 * T_F)

def kavl_table(hwt, cwt, wbt, lg, alt_m):
    WBT_F   = wbt * 1.8 + 32
    Range_F = (hwt - cwt) * 1.8
    CWT_F   = WBT_F + (cwt - wbt) * 1.8
    pp      = alt_to_psi(alt_m)
    hi_in   = h_sat_table(pp, WBT_F)
    hi_out  = Range_F * lg + hi_in
    total   = 0.0
    for cheb in [0.9, 0.6, 0.4, 0.1]:
        hs = h_sat_table(pp, Range_F * cheb + CWT_F)
        ha = (hi_out - hi_in) * cheb + hi_in
        df = hs - ha
        if df <= 0: return "ERR"    # physically invalid (driving force ≤ 0)
        total += 0.25 / df
    raw = total * Range_F
    return f"{raw:.5f}"

# ─── Binary probe infrastructure ──────────────────────────────────────────
def kill_cti():
    os.system("taskkill /F /IM CTIToolkit.exe >nul 2>&1"); time.sleep(0.15)

def probe_batch(pairs):
    """
    Probe multiple (P_psi, T_F) pairs in one binary launch.
    pairs: list of (P_psi, T_F)
    Returns: list of h_sat values (same order as input pairs)
    """
    kill_cti()
    si = win32process.STARTUPINFO(); si.dwFlags = 1; si.wShowWindow = 0
    p_info = win32process.CreateProcess(
        None, f'"{EXE_PATH}"', None, None, False, 4,
        None, os.path.dirname(EXE_PATH), si)
    h, ht, pid, tid = p_info; h_int = int(h)

    N = len(pairs)
    alloc = N*8 + 16 + N*60 + 4096
    cave  = KERNEL32.VirtualAllocEx(h_int, 0, alloc, 0x3000, 0x40)
    if not cave:
        os.system(f"taskkill /F /PID {pid} >nul 2>&1"); return None

    res_addr  = cave
    sent_addr = cave + N*8 + 8
    code_addr = sent_addr + 8

    def push_d(v):
        pk = struct.pack("<d", v); return b"\x68"+pk[4:8]+b"\x68"+pk[0:4]

    code = bytearray(b"\xDB\xE3")
    code += b"\xC7\x05" + struct.pack("<I", sent_addr) + b"\x01\x00\x00\x00"
    for i, (p, T) in enumerate(pairs):
        ra = res_addr + i*8
        code += push_d(T) + push_d(T) + push_d(p)
        cs = code_addr + len(code)
        code += b"\xE8" + struct.pack("<i", FUNC_HSAT - (cs + 5))
        code += b"\x83\xC4\x18"
        code += b"\xDD\x1D" + struct.pack("<I", ra)
    code += b"\xC7\x05" + struct.pack("<I", sent_addr) + b"\x02\x00\x00\x00"
    code += b"\xEB\xFE"

    KERNEL32.WriteProcessMemory(h_int, code_addr, bytes(code), len(code), None)
    old = ctypes.c_ulong()
    KERNEL32.VirtualProtectEx(h_int, ADDR_EP, 5, 0x40, ctypes.byref(old))
    KERNEL32.WriteProcessMemory(h_int, ADDR_EP,
        b"\xE9" + struct.pack("<i", code_addr - (ADDR_EP + 5)), 5, None)
    win32process.ResumeThread(ht)

    sentinel = ctypes.c_uint32()
    deadline = time.time() + 30
    while time.time() < deadline:
        KERNEL32.ReadProcessMemory(h_int, sent_addr, ctypes.byref(sentinel), 4, None)
        if sentinel.value == 2: break
        time.sleep(0.04)

    if sentinel.value != 2:
        os.system(f"taskkill /F /PID {pid} >nul 2>&1"); return None

    buf = (ctypes.c_double * N)()
    KERNEL32.ReadProcessMemory(h_int, res_addr, buf, N*8, None)
    os.system(f"taskkill /F /PID {pid} >nul 2>&1")
    return list(buf)

def kavl_from_hsat(h_sat_vals, Range_F, lg):
    """Compute KaV/L from 5 exact h_sat values (index 0=WBT, 1-4=Chebyshev)."""
    hi_in  = h_sat_vals[0]
    hi_out = Range_F * lg + hi_in
    total  = 0.0
    for i, cheb in enumerate([0.9, 0.6, 0.4, 0.1]):
        hs = h_sat_vals[i + 1]
        ha = (hi_out - hi_in) * cheb + hi_in
        df = hs - ha
        if df <= 0: return "ERR"
        total += 0.25 / df
    return f"{total * Range_F:.5f}"

# ─── Test cases ───────────────────────────────────────────────────────────
ALTITUDES = [0, 110, 250, 500, 750, 1000, 1500, 2000]

# Temperature scenarios: (hwt, cwt, wbt, label)
TEMP_SETS = [
    # Cold range — low temps
    (30, 24, 18, "cold"),
    (35, 27, 22, "cool-lo"),
    # Medium range — common CTI cases
    (40, 28, 20, "medium"),
    (40, 30, 27.4, "img-case"),   # ← the screenshot case
    (45, 32, 25, "warm"),
    # Hot range — high HWT
    (50, 36, 28, "hot"),
    (55, 38, 25, "hot-lo"),
    (60, 42, 30, "very-hot"),
    # Wide range
    (55, 30, 20, "wide-range"),
    # High approach
    (40, 35, 20, "hi-approach"),
]

LG_RATIOS = [0.75, 1.0, 1.5, 2.0]


def main():
    P("=" * 80)
    P("  COMPREHENSIVE MERKEL PARITY TEST")
    P(f"  {len(TEMP_SETS)} temp sets × {len(ALTITUDES)} altitudes × {len(LG_RATIOS)} LG = "
      f"{len(TEMP_SETS)*len(ALTITUDES)*len(LG_RATIOS)} test cases")
    P("=" * 80)

    # Build all test cases
    cases = []
    for hwt, cwt, wbt, label in TEMP_SETS:
        for alt_m in ALTITUDES:
            for lg in LG_RATIOS:
                if hwt <= cwt or cwt <= wbt or lg <= 0: continue
                WBT_F   = wbt * 1.8 + 32
                Range_F = (hwt - cwt) * 1.8
                CWT_F   = WBT_F + (cwt - wbt) * 1.8
                pp      = alt_to_psi(alt_m)
                temps   = [WBT_F] + [Range_F * c + CWT_F for c in [0.9, 0.6, 0.4, 0.1]]
                cases.append({
                    "hwt": hwt, "cwt": cwt, "wbt": wbt, "lg": lg,
                    "alt_m": alt_m, "label": label,
                    "P_psi": pp, "Range_F": Range_F, "temps": temps
                })

    P(f"  Effective test cases: {len(cases)}")

    # Collect all unique (P_psi, T_F) pairs to probe in one binary session
    pair_set = {}   # (P_psi_rounded, T_F_rounded) → index
    pairs    = []
    for c in cases:
        for T_F in c["temps"]:
            key = (round(c["P_psi"], 8), round(T_F, 8))
            if key not in pair_set:
                pair_set[key] = len(pairs)
                pairs.append((c["P_psi"], T_F))

    P(f"  Unique (P, T) pairs to probe: {len(pairs)}")

    # Probe in batches of 200 pairs per binary launch
    BATCH = 200
    h_sat_map = {}
    n_batches = (len(pairs) + BATCH - 1) // BATCH
    P(f"\n  Probing {len(pairs)} pairs in {n_batches} batches...")

    t_probe = time.time()
    for b in range(n_batches):
        batch_pairs = pairs[b*BATCH:(b+1)*BATCH]
        print(f"  Batch {b+1}/{n_batches} ({len(batch_pairs)} pairs)...", end="", flush=True)
        results = probe_batch(batch_pairs)
        if results is None:
            print(" FAILED"); continue
        for (p, T), h in zip(batch_pairs, results):
            h_sat_map[(round(p, 8), round(T, 8))] = h
        print(f" ✓")

    P(f"  Probed in {time.time()-t_probe:.1f}s  ({len(h_sat_map)} results)")

    # ─── Evaluate each case ───────────────────────────────────────────────
    P(f"\n  Running {len(cases)} comparisons...\n")

    match_total = 0; total = 0
    failures = []

    # Group by altitude for cleaner display
    by_alt = {}
    for c in cases:
        by_alt.setdefault(c["alt_m"], []).append(c)

    for alt_m in ALTITUDES:
        if alt_m not in by_alt: continue
        alt_cases = by_alt[alt_m]
        alt_match = 0; alt_total = 0
        alt_fails = []

        for c in alt_cases:
            pp  = c["P_psi"]

            # Binary truth
            h_sat_bin = []
            for T in c["temps"]:
                key = (round(pp, 8), round(T, 8))
                h = h_sat_map.get(key)
                if h is None: break
                h_sat_bin.append(h)

            if len(h_sat_bin) < 5:
                continue

            bin_result  = kavl_from_hsat(h_sat_bin, c["Range_F"], c["lg"])
            tbl_result  = kavl_table(c["hwt"], c["cwt"], c["wbt"], c["lg"], alt_m)
            match       = (bin_result == tbl_result)

            alt_match += int(match); alt_total += 1
            match_total += int(match); total += 1

            if not match:
                alt_fails.append({
                    "label": c["label"],
                    "hwt": c["hwt"], "cwt": c["cwt"],
                    "wbt": c["wbt"], "lg": c["lg"],
                    "alt_m": alt_m,
                    "bin": bin_result, "tbl": tbl_result,
                    "delta": abs(float(bin_result) - float(tbl_result))
                        if bin_result not in ("ERR","") else 0
                })
                failures.append(alt_fails[-1])

        pct = 100 * alt_match / max(1, alt_total)
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        P(f"  alt={alt_m:4d}m │ {bar} │ {alt_match:3d}/{alt_total:3d} ({pct:6.2f}%)",)
        if alt_fails and pct < 100:
            for f in alt_fails[:3]:
                P(f"           ✗ {f['label']:10s} HWT={f['hwt']} CWT={f['cwt']} WBT={f['wbt']} "
                  f"LG={f['lg']}  bin={f['bin']}  tbl={f['tbl']}  Δ={f['delta']:.2e}")

    # ─── Summary ──────────────────────────────────────────────────────────
    pct_total = 100 * match_total / max(1, total)
    P(f"\n{'='*80}")
    P(f"  FINAL SCORE: {match_total}/{total} exact matches  ({pct_total:.2f}%)")
    P(f"{'='*80}")

    if failures:
        P(f"\n  {len(failures)} FAILURES:")
        P(f"  {'Label':<12s} {'HWT':>4s} {'CWT':>4s} {'WBT':>5s} {'LG':>4s} {'Alt':>5s}"
          f" {'Binary':>10s} {'Table':>10s} {'Delta':>10s}")
        P(f"  {'─'*70}")
        for f in sorted(failures, key=lambda x: -x["delta"])[:20]:
            P(f"  {f['label']:<12s} {f['hwt']:4.0f} {f['cwt']:4.0f} {f['wbt']:5.1f}"
              f" {f['lg']:4.2f} {f['alt_m']:5.0f}"
              f" {f['bin']:>10s} {f['tbl']:>10s} {f['delta']:>10.2e}")
    else:
        P(f"\n  ✓ ALL {total} cases matched exactly!")

    P(f"\n  Note: 'Binary truth' = KaV/L computed from exact h_sat values probed")
    P(f"        via code-cave injection into MerkelPsychro_imperial (0x407723).")
    P(f"        Both values are displayed at 5 decimal places (CTI display format).")


if __name__ == "__main__":
    main()
