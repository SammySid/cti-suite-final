"""
gen_poly_tables.py
==================
Compress merkel_tables_10m_018F.bin (12.8 MB) into Chebyshev polynomial
coefficients (merkel_poly.bin, ~30 KB) with zero loss of display parity.

THEORY
------
ln(f*Pws(T)) is analytic over [50, 200°F].  A degree-18 Chebyshev series
fits it to residual < 1e-10 — far below the ~5e-7 ln-space error budget
that maps to ±0.000005 KaV/L (half the display rounding unit).

OUTPUT FORMAT
-------------
  merkel_poly.bin   — raw float64, little-endian
  Layout: 201 altitude levels × 19 coefficients = 3819 doubles = 30552 bytes
  Coefficient indexing: [alt_idx * N_COEFF + coeff_idx]
  Evaluation: standard Chebyshev on x = (T_F − T_MID) / T_HALF ∈ [−1, 1]

CONSTANTS stored in merkel_poly_meta.json:
  T_start_F, T_end_F, T_mid_F, T_half_F, degree, N_coeff, alt_levels_m
"""
import array, struct, json, math, os, sys
import numpy as np

HERE = os.path.dirname(__file__)

SRC_BIN  = os.path.join(HERE, "merkel_tables_10m_018F.bin")
OUT_BIN  = os.path.join(HERE, "merkel_poly.bin")
OUT_META = os.path.join(HERE, "merkel_poly_meta.json")

# ── grid parameters (must match merkel_tables_10m_018F.json) ───────────
T_START  = 50.0
T_STEP   = 9.0 / 500.0     # 0.018°F
N_T      = 8334
ALT_STEP = 10               # m
N_ALT    = 201

T_END    = T_START + (N_T - 1) * T_STEP    # 199.994°F
T_MID    = (T_END  + T_START) / 2.0        # 124.997°F
T_HALF   = (T_END  - T_START) / 2.0        # 74.997°F

DEGREE   = 18
N_COEFF  = DEGREE + 1      # 19

ALT_LEVELS = list(range(0, 2001, ALT_STEP))

def alt_to_psi(alt_m):
    if alt_m == 0:
        return 14.696
    alt_ft = alt_m / 0.3048
    x = alt_ft / 10_000.0
    return ((0.547462 * x - 7.67923) * x + 29.9309) * 0.491154 / (0.10803 * x + 1.0)

P_LEVELS = [alt_to_psi(a) for a in ALT_LEVELS]

# ── load source table ───────────────────────────────────────────────────
print(f"Loading {SRC_BIN} …")
with open(SRC_BIN, "rb") as f:
    raw = f.read()
expected = N_ALT * N_T * 8
if len(raw) != expected:
    sys.exit(f"ERROR: expected {expected} bytes, got {len(raw)}")

all_ln = array.array("d")
all_ln.frombytes(raw)
print(f"  Loaded {len(all_ln):,} float64 values  ({len(raw)/1024/1024:.1f} MB)")

# ── build normalised T axis ─────────────────────────────────────────────
T_vals = np.array([T_START + i * T_STEP for i in range(N_T)], dtype=np.float64)
x_vals = (T_vals - T_MID) / T_HALF     # ∈ [−1, 1]

# ── fit Chebyshev per altitude level ───────────────────────────────────
print(f"\nFitting degree-{DEGREE} Chebyshev polynomial for each of {N_ALT} altitude levels …")
coeffs_all = np.empty((N_ALT, N_COEFF), dtype=np.float64)

max_residual = 0.0
worst_alt    = 0

for alt_idx in range(N_ALT):
    ln_vals = np.array(all_ln[alt_idx * N_T : (alt_idx + 1) * N_T], dtype=np.float64)
    c = np.polynomial.chebyshev.chebfit(x_vals, ln_vals, DEGREE)
    coeffs_all[alt_idx] = c

    # verify residual
    approx = np.polynomial.chebyshev.chebval(x_vals, c)
    res    = np.max(np.abs(approx - ln_vals))
    if res > max_residual:
        max_residual = res
        worst_alt    = ALT_LEVELS[alt_idx]

    if (alt_idx % 50) == 0 or alt_idx == N_ALT - 1:
        print(f"  [{alt_idx+1:3d}/{N_ALT}]  alt={ALT_LEVELS[alt_idx]:4d}m  "
              f"max_residual_so_far={max_residual:.2e}")

print(f"\n  ✓ Worst-case residual: {max_residual:.2e}  at alt={worst_alt}m")
required = 5e-7
print(f"  Required threshold:   {required:.2e}")
print(f"  Safety margin:        {required/max_residual:.0f}×")

if max_residual > required:
    sys.exit("FAIL: residual too large — increase DEGREE and rerun")

# ── write binary ────────────────────────────────────────────────────────
with open(OUT_BIN, "wb") as f:
    for alt_idx in range(N_ALT):
        f.write(struct.pack(f"<{N_COEFF}d", *coeffs_all[alt_idx]))

size_kb = os.path.getsize(OUT_BIN) / 1024
print(f"\n  Saved: {OUT_BIN}")
print(f"  Size:  {size_kb:.1f} KB  (was 12.8 MB — {12800/size_kb:.0f}× compression)")

# ── write metadata ──────────────────────────────────────────────────────
meta = {
    "T_start_F":    T_START,
    "T_end_F":      T_END,
    "T_mid_F":      T_MID,
    "T_half_F":     T_HALF,
    "degree":       DEGREE,
    "N_coeff":      N_COEFF,
    "N_alt":        N_ALT,
    "alt_step_m":   ALT_STEP,
    "alt_levels_m": ALT_LEVELS,
    "P_levels_psi": P_LEVELS,
    "bin_file":     "merkel_poly.bin",
    "max_residual_ln": float(max_residual),
}
with open(OUT_META, "w") as f:
    json.dump(meta, f, indent=2)
print(f"  Meta:  {OUT_META}")

# ── quick KaV/L parity check ────────────────────────────────────────────
print("\n" + "="*65)
print("  QUICK PARITY CHECK (polynomial vs binary table)")
print("="*65)

def poly_frac(alt_idx, x):
    c = coeffs_all[alt_idx]
    return float(np.polynomial.chebyshev.chebval(x, c))

def fpws_poly(T_F, P_psi):
    n = len(P_LEVELS)
    x = (T_F - T_MID) / T_HALF
    if P_psi >= P_LEVELS[0]:
        return math.exp(poly_frac(0, x))
    if P_psi <= P_LEVELS[-1]:
        return math.exp(poly_frac(n - 1, x))
    lo = 0
    for k in range(n - 1):
        if P_psi >= P_LEVELS[k + 1]:
            lo = k
            break
    hi = lo + 1
    frac = (P_psi - P_LEVELS[lo]) / (P_LEVELS[hi] - P_LEVELS[lo])
    return math.exp(poly_frac(lo, x) + frac * (poly_frac(hi, x) - poly_frac(lo, x)))

def hsat_poly(P_psi, T_F):
    fp = fpws_poly(T_F, P_psi)
    d  = P_psi - fp
    if d <= 0:
        return 999.0
    Ws = 0.62198 * fp / d
    return 0.24 * T_F + Ws * (1061.0 + 0.444 * T_F)

def kavl_poly(hwt, cwt, wbt, lg, alt_m):
    WBT_F   = wbt * 1.8 + 32
    Range_F = (hwt - cwt) * 1.8
    CWT_F   = WBT_F + (cwt - wbt) * 1.8
    pp      = alt_to_psi(alt_m)
    h_in    = hsat_poly(pp, WBT_F)
    h_out   = Range_F * lg + h_in
    total   = 0.0
    for cheb in [0.9, 0.6, 0.4, 0.1]:
        hs = hsat_poly(pp, Range_F * cheb + CWT_F)
        ha = (h_out - h_in) * cheb + h_in
        df = hs - ha
        if df <= 0:
            return None, "ERR"
        total += 0.25 / df
    raw = total * Range_F
    return raw, f"{raw:.5f}"

# Also load original table for comparison
def get_ln_table(alt_idx, T_F):
    idx = round((T_F - T_START) / T_STEP)
    idx = max(0, min(N_T - 1, idx))
    return all_ln[alt_idx * N_T + idx]

def fpws_table(T_F, P_psi):
    n = len(P_LEVELS)
    if P_psi >= P_LEVELS[0]:
        return math.exp(get_ln_table(0, T_F))
    if P_psi <= P_LEVELS[-1]:
        return math.exp(get_ln_table(n - 1, T_F))
    lo = 0
    for k in range(n - 1):
        if P_psi >= P_LEVELS[k + 1]:
            lo = k
            break
    hi = lo + 1
    frac = (P_psi - P_LEVELS[lo]) / (P_LEVELS[hi] - P_LEVELS[lo])
    return math.exp(get_ln_table(lo, T_F) + frac * (get_ln_table(hi, T_F) - get_ln_table(lo, T_F)))

def hsat_table(P_psi, T_F):
    fp = fpws_table(T_F, P_psi)
    d  = P_psi - fp
    if d <= 0:
        return 999.0
    Ws = 0.62198 * fp / d
    return 0.24 * T_F + Ws * (1061.0 + 0.444 * T_F)

def kavl_table(hwt, cwt, wbt, lg, alt_m):
    WBT_F   = wbt * 1.8 + 32
    Range_F = (hwt - cwt) * 1.8
    CWT_F   = WBT_F + (cwt - wbt) * 1.8
    pp      = alt_to_psi(alt_m)
    h_in    = hsat_table(pp, WBT_F)
    h_out   = Range_F * lg + h_in
    total   = 0.0
    for cheb in [0.9, 0.6, 0.4, 0.1]:
        hs = hsat_table(pp, Range_F * cheb + CWT_F)
        ha = (h_out - h_in) * cheb + h_in
        df = hs - ha
        if df <= 0:
            return None, "ERR"
        total += 0.25 / df
    raw = total * Range_F
    return raw, f"{raw:.5f}"

# 320 comprehensive test cases from merkel_parity_comprehensive.py
ALT_CASES = [0, 110, 500, 750, 1000, 1250, 1500, 2000]
TEMP_CASES = [
    (40, 28, 20, 1.0),
    (40, 30, 27.4, 1.11),
    (45, 32, 22, 1.2),
    (50, 35, 25, 1.3),
    (55, 38, 28, 1.4),
    (35, 25, 18, 0.9),
    (60, 42, 30, 1.5),
    (65, 48, 35, 1.6),
    (30, 22, 15, 0.8),
    (55, 38, 25, 1.3),
]
LG_CASES = [0.75, 1.0, 1.25, 1.5]

ok_tbl = ok_poly = total = 0
mismatches = []

for hwt, cwt, wbt, lg_base in TEMP_CASES:
    for alt in ALT_CASES:
        for lg in LG_CASES:
            total += 1
            _, t_res = kavl_table(hwt, cwt, wbt, lg, alt)
            _, p_res = kavl_poly(hwt, cwt, wbt, lg, alt)
            if t_res == p_res:
                ok_poly += 1
            else:
                mismatches.append((hwt, cwt, wbt, lg, alt, t_res, p_res))

print(f"\n  Polynomial vs Table: {ok_poly}/{total} exact matches")
if mismatches:
    print(f"\n  MISMATCHES ({len(mismatches)}):")
    for hwt, cwt, wbt, lg, alt, t_res, p_res in mismatches[:20]:
        print(f"    {hwt}/{cwt}/{wbt}/{lg} alt={alt}m  table={t_res}  poly={p_res}")
else:
    print(f"  ✓ ALL {total} cases identical — polynomial compression is loss-free!")
print("="*65)
