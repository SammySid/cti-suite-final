"""
probe_dp_parity.py
==================
Probes the CTI binary for fresh psychrometric truth and compares
against the current psychro-engine.js (post-C9 fix).

Fix v2: poll_sync now checks DBT + WBT + Alt to avoid stale reads.
"""
import sys, os, csv, math, random, time
import ctypes
sys.path.insert(0, r"f:\2026 latest\cti Toolkit\cti_crack\important")

# ─── Python re-implementation of psychro-engine.js (post-C9 fix) ─────────────
C9_WATER = 1.3914993 - math.log(1000)
C9_ICE   = 6.3925247 - math.log(1000)
F_TABLE_MIN = -5
F_DATA = [
    1.0040315738708063, 1.004018725503031,  1.0040071724095705,
    1.0039968752757855, 1.0039878016447452, 1.0039799255559547,
    1.0039732271840844, 1.0039676924776961, 1.0039633127979717,
    1.003960084557444,  1.0039580088587197, 1.0039570911332116,
    1.0039573407798636, 1.0039587708038833, 1.0039613974554642,
    1.003965239868518,  1.0039703196994003, 1.0039766607656408,
    1.0039842886846695, 1.0039932305125454, 1.0040035143826855,
    1.0040151691445907, 1.004028224002576,  1.0040427081544965,
    1.0040586504304778, 1.0040760789316425, 1.0040950206688388,
    1.004115501201367,  1.004137544275712,  1.0041611714642635,
    1.004186401804054,  1.0042132514354778, 1.004241733241025,
    1.0042718564840065, 1.0043036264472835, 1.0043370440719939,
    1.004372105596284,  1.0044088021940316, 1.004447119613578,
    1.0044870378164537, 1.0045285306161078, 1.004571565316636,
    1.0046161023515068, 1.0046620949222926, 1.0047094886373953,
    1.0047582211507753, 1.0048082218006797, 1.0048594112483697,
    1.0049117011168494, 1.0049649936295926, 1.0050191812492741,
    1.005074146316492,  1.0051297606885021, 1.0051858853779416,
    1.0052423701915585, 1.0052990533689405, 1.005355761221242,
    1.005412307769911,  1.005468494385421,  1.0055241094259957,
    1.0055789278763365, 1.0056327109863539, 1.0056852059098924,
    1.0057361453434612, 1.0057852471649595, 1.0058322140724072,
    1.0058767332226708, 1.0059184758701918, 1.0059570970057172,
    1.0059922349950237, 1.0060235112176488, 1.0060505297056177,
    1.0060728767821703, 1.006090120700492,  1.0061018112824385,
    1.0061074795572678, 1.0061066374003627, 1.006098777171965,
    1.006083371355898,  1.0060598721982998, 1.0060277113463465,
    1.0059862994869835, 1.0059350259856525, 1.0058732585250203,
    1.0058003427437041, 1.0057156018750033, 1.0056183363856253,
    1.005507823614414,  1.0053833174110782, 1.005244047774919,
    1.0050892204935582, 1.0049180167816676, 1.0047295929196942,
    1.00452307989259,   1.0042975830285414, 1.0040521816376955,
    1.0037859286508857, 1.0034978502583662, 1.0031869455485354,
]

def f_enhance(T):
    T = max(float(F_TABLE_MIN), min(93.0, T))
    lo = int(math.floor(T)) - F_TABLE_MIN
    frac = T - math.floor(T)
    if lo + 1 < len(F_DATA):
        return F_DATA[lo] + frac * (F_DATA[lo + 1] - F_DATA[lo])
    return F_DATA[lo]

def f_enhance_at_P(T, P):
    """Pressure-corrected enhancement factor (matches binary at altitude)."""
    f_sea = f_enhance(T)
    correction = 1.27e-5 / (f_sea - 1.0) * (1.0 - P / 101.325)
    return f_sea - correction

def pws_kpa(T_C):
    T_K = T_C + 273.15
    if T_K <= 0: return 0.0
    if T_C >= 0:
        ln = (-5800.2206/T_K + C9_WATER - 0.048640239*T_K
              + 4.1764768e-5*T_K**2 - 1.4452093e-8*T_K**3
              + 6.5459673*math.log(T_K))
    else:
        ln = (-5674.5359/T_K + C9_ICE - 0.0096778430*T_K
              + 6.2215701e-7*T_K**2 + 2.0747825e-9*T_K**3
              - 9.484024e-13*T_K**4 + 4.1635019*math.log(T_K))
    return math.exp(ln)

def dpws_dT(T_C, pws_val):
    T_K = T_C + 273.15
    if T_C >= 0:
        d = (5800.2206/T_K**2 - 0.048640239 + 2*4.1764768e-5*T_K
             - 3*1.4452093e-8*T_K**2 + 6.5459673/T_K)
    else:
        d = (5674.5359/T_K**2 - 0.0096778430 + 2*6.2215701e-7*T_K
             + 3*2.0747825e-9*T_K**2 - 4*9.484024e-13*T_K**3
             + 4.1635019/T_K)
    return d * pws_val

def ashrae_dp_approx(Pw):
    if Pw <= 0: return 0.0
    alpha = math.log(Pw)
    dp = (6.54 + 14.526*alpha + 0.7389*alpha**2
          + 0.09486*alpha**3 + 0.4569*Pw**0.1984)
    if dp < 0:
        dp = 6.09 + 12.608*alpha + 0.4959*alpha**2
    return dp

MW_MA = 0.62198

def psychrometrics(dbt, wbt, alt_m=0):
    P = 101.325 * (1 - 2.25577e-5 * alt_m) ** 5.2559
    Pws_wbt  = pws_kpa(wbt)
    f_wbt    = f_enhance_at_P(wbt, P)
    fPws_wbt = f_wbt * Pws_wbt
    Ws = MW_MA * fPws_wbt / (P - fPws_wbt)
    denom = 2501 + 1.805*dbt - 4.186*wbt
    W = max(0.0, ((2501 - 2.381*wbt)*Ws - (dbt - wbt)) / denom) if denom > 0 else 0.0

    f_init = f_enhance_at_P(wbt, P)
    den_w  = (MW_MA + W) * f_init
    Pw     = P * W / den_w if den_w > 0 else 0.0
    dp     = ashrae_dp_approx(Pw)
    for _ in range(2):
        f_dp  = f_enhance_at_P(dp, P)
        den_w = (MW_MA + W) * f_dp
        Pw    = P * W / den_w if den_w > 0 else 0.0
        dp    = ashrae_dp_approx(Pw)

    step = 1.0
    for _ in range(50):
        Pws_dp  = pws_kpa(dp)
        f_dp    = f_enhance_at_P(dp, P)
        fPws_dp = f_dp * Pws_dp
        denom_dp = P - fPws_dp
        if abs(denom_dp) < 1e-15: break
        W_dp = MW_MA * fPws_dp / denom_dp
        if W_dp <= 0: break
        if abs(W / W_dp - 1) < 1e-6: break
        if abs(step) < 0.0001: break
        dpws = dpws_dT(dp, Pws_dp)
        dW_dp = MW_MA * f_dp * dpws * P / (denom_dp * denom_dp)
        if abs(dW_dp) < 1e-20: break
        step = (W - W_dp) / dW_dp
        dp += step

    H  = 1.006*dbt + W*(2501 + 1.805*dbt)
    RH = 100.0*W*(P - fPws_wbt) / (MW_MA * fPws_wbt * (1 + W/MW_MA)) if fPws_wbt > 0 else 0.0
    return {"HR": round(W, 4), "DP": round(dp, 2), "H": round(H, 4), "RH": round(RH, 2)}

# ─── Enhanced siphon with WBT sync ───────────────────────────────────────────
print("="*60)
print("CTI Psychrometrics DP Parity Probe v2 (WBT-synced)")
print("="*60)

try:
    from Psychrometrics_Siphon import PsychrometricsSiphon
    import win32gui, win32con
except ImportError:
    print("[!] Could not import PsychrometricsSiphon"); sys.exit(1)

EXE = r"f:\2026 latest\cti Toolkit\cti_crack\official\cti toolkit\CTIToolkit_Ghost_Engine.exe"
OUT_CSV = os.path.join(os.path.dirname(__file__), "dp_parity_probe.csv")

class SiphonEx(PsychrometricsSiphon):
    """Extended siphon that also syncs on WBT."""
    def poll_sync_full(self, d_target, w_target, a_target):
        # Read rows: 1=Alt, 2=DBT, 3=WBT
        win32gui.SendMessage(self.h_lv, 0x104B, 1, self.remote_mem + (1 * 60))
        win32gui.SendMessage(self.h_lv, 0x104B, 2, self.remote_mem + (2 * 60))
        win32gui.SendMessage(self.h_lv, 0x104B, 3, self.remote_mem + (3 * 60))
        full_buf = ctypes.create_string_buffer(384)  # 3 rows × 128 bytes
        self.kernel32.ReadProcessMemory(
            self.h_proc.handle,
            self.remote_mem + 600 + (1 * 128),  # rows 1,2,3 in the data buffer
            full_buf, 384, None)
        raw = full_buf.raw
        res_alt = raw[0:128].decode('utf-16le').split('\0')[0].strip()
        res_dbt = raw[128:256].decode('utf-16le').split('\0')[0].strip()
        res_wbt = raw[256:384].decode('utf-16le').split('\0')[0].strip()
        try:
            ok_a = abs(float(res_alt) - float(a_target)) < 0.05
            ok_d = abs(float(res_dbt) - float(d_target)) < 0.05
            ok_w = abs(float(res_wbt) - float(w_target)) < 0.05
            return ok_a and ok_d and ok_w
        except:
            return False

bot = SiphonEx(EXE)
if not bot.launch():
    print("[!] Failed to launch siphon."); sys.exit(1)
print(f"[OK] Siphon ready (PID: {bot.pid})")

# Generate test cases: broad coverage, avoiding W=0 (impossible) cases
# CTI valid range: DBT 0-60°C, WBT 0-50°C, alt 0-3000m
random.seed(2026)
test_cases = []
for alt in [0, 500, 1000, 1500]:
    for _ in range(80):
        dbt = round(random.uniform(15.0, 55.0), 1)
        wbt = round(random.uniform(max(10.0, dbt - 20.0), dbt - 0.5), 1)
        test_cases.append((dbt, wbt, alt))
# Ensure DBT > WBT
test_cases = [(d, w, a) for d, w, a in test_cases if d > w + 0.1]

N = len(test_cases)
print(f"[*] Test cases: {N}")

results = []
t0 = time.time()
for i, (dbt, wbt, alt) in enumerate(test_cases):
    ds = f"{dbt:.1f}"; ws = f"{wbt:.1f}"; als = f"{alt:.1f}"
    win32gui.SendMessage(bot.h_alt, win32con.WM_SETTEXT, 0, als)
    win32gui.SendMessage(bot.hwnd, win32con.WM_COMMAND, (0x0300 << 16) | 1002, bot.h_alt)
    win32gui.SendMessage(bot.h_dbt, win32con.WM_SETTEXT, 0, ds)
    win32gui.SendMessage(bot.hwnd, win32con.WM_COMMAND, (0x0300 << 16) | 1003, bot.h_dbt)
    win32gui.SendMessage(bot.h_wbt, win32con.WM_SETTEXT, 0, ws)
    win32gui.SendMessage(bot.hwnd, win32con.WM_COMMAND, (0x0300 << 16) | 1004, bot.h_wbt)
    win32gui.SendMessage(bot.hwnd, win32con.WM_COMMAND, 1007, 0)
    synced = False
    for _ in range(500):
        if bot.poll_sync_full(ds, ws, als):
            synced = True
            break
    if not synced:
        print(f"  [!] Sync timeout: DBT={dbt}, WBT={wbt}, Alt={alt}")
        continue
    row = bot.siphon_full()
    results.append((dbt, wbt, alt, row))
    if (i + 1) % 60 == 0:
        print(f"  [{i+1}/{N}] {(i+1)/(time.time()-t0):.0f} pts/s")

bot.kill()
print(f"\n[OK] {len(results)} valid readings in {time.time()-t0:.1f}s")

# ─── Analysis ────────────────────────────────────────────────────────────────
dp_match = dp_fail = h_match = h_fail = hr_match = hr_fail = 0
fail_dp = []

for dbt, wbt, alt, row in results:
    try:
        dp_b = float(row[5]); h_b = float(row[4]); hr_b = float(row[9])
    except (ValueError, IndexError):
        continue
    js = psychrometrics(dbt, wbt, alt)
    dp_j = js["DP"]; h_j = js["H"]; hr_j = js["HR"]

    if round(dp_b, 2) == round(dp_j, 2): dp_match += 1
    else:
        dp_fail += 1
        fail_dp.append((dbt, wbt, alt, dp_b, dp_j, h_b, h_j, hr_b, hr_j))

    if round(h_b, 4) == round(h_j, 4): h_match += 1
    else: h_fail += 1
    if round(hr_b, 4) == round(hr_j, 4): hr_match += 1
    else: hr_fail += 1

total = dp_match + dp_fail
if total == 0:
    print("No valid results!"); sys.exit(1)

print(f"\n{'='*60}")
print(f"PARITY RESULTS (post-C9 fix, WBT-synced probe)")
print(f"{'='*60}")
print(f"  DP:  {dp_match:3d}/{total}  ({100*dp_match/total:.2f}%)")
print(f"  H:   { h_match:3d}/{total}  ({100* h_match/total:.2f}%)")
print(f"  HR:  {hr_match:3d}/{total}  ({100*hr_match/total:.2f}%)")

if fail_dp:
    print(f"\nFailing DP cases ({len(fail_dp)}):")
    hdr = f"{'DBT':>6} {'WBT':>6} {'Alt':>5} | {'DP_bin':>7} {'DP_js':>7} {'Δ°C':>8} | {'H_bin':>9} {'H_js':>9} | {'HR match':>8}"
    print(hdr)
    print("-"*75)
    for r in fail_dp[:40]:
        dbt,wbt,alt,dp_b,dp_j,h_b,h_j,hr_b,hr_j = r
        hr_ok = "OK" if round(hr_b,4)==round(hr_j,4) else "FAIL"
        print(f"{dbt:6.1f} {wbt:6.1f} {alt:5.0f} | {dp_b:7.2f} {dp_j:7.2f} {dp_b-dp_j:+8.4f} | {h_b:9.4f} {h_j:9.4f} | {hr_ok:>8}")
    
    diffs = [abs(dp_b-dp_j) for _,_,_,dp_b,dp_j,*_ in fail_dp]
    h_ok_in_fail  = sum(1 for _,_,_,_,_,h_b,h_j,_,_ in fail_dp if round(h_b,4)==round(h_j,4))
    hr_ok_in_fail = sum(1 for _,_,_,_,_,_,_,hr_b,hr_j in fail_dp if round(hr_b,4)==round(hr_j,4))
    by_diff = {}
    for d in diffs:
        k = round(d, 2)
        by_diff[k] = by_diff.get(k, 0) + 1
    print(f"\n  H  matches when DP fails: {h_ok_in_fail}/{len(fail_dp)}")
    print(f"  HR matches when DP fails: {hr_ok_in_fail}/{len(fail_dp)}")
    print(f"  DP error distribution: {sorted(by_diff.items())[:15]}")
    alt_groups = {}
    for _,_,alt,dp_b,dp_j,*_ in fail_dp:
        alt_groups[alt] = alt_groups.get(alt, 0) + 1
    print(f"  Failures by altitude: {alt_groups}")

# Save for further analysis
with open(OUT_CSV, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['dbt','wbt','alt','dp_bin','dp_js','dp_ok','h_bin','h_js','h_ok','hr_bin','hr_js','hr_ok'])
    for dbt, wbt, alt, row in results:
        try:
            dp_b = float(row[5]); h_b = float(row[4]); hr_b = float(row[9])
        except: continue
        js = psychrometrics(dbt, wbt, alt)
        w.writerow([dbt, wbt, alt,
                    round(dp_b,2), round(js["DP"],2), int(round(dp_b,2)==round(js["DP"],2)),
                    round(h_b,4),  round(js["H"],4),  int(round(h_b,4)==round(js["H"],4)),
                    round(hr_b,4), round(js["HR"],4), int(round(hr_b,4)==round(js["HR"],4))])
print(f"\n[*] Saved: {OUT_CSV}")
