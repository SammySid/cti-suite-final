"""
Direct binary probe of MerkelPsychro_imperial at the exact (P, T) points
used for the 40/30/27.4/1.11/110m integration.
This gives bit-perfect truth for this case.
"""
import os, sys, ctypes, struct, time, math

sys.stdout.reconfigure(line_buffering=True)
def P(s): print(s, flush=True)

try:
    import win32process
except ImportError:
    P("pip install pywin32"); sys.exit(1)

KERNEL32  = ctypes.windll.kernel32
EXE_PATH  = os.path.join(os.path.dirname(__file__), "..", "official", "cti toolkit", "CTIToolkit.exe")
ADDR_EP   = 0x004569CE
FUNC_HSAT = 0x407723   # (P_psi, T_F, T_F) → h_sat

# Integration parameters from screenshot
hwt, cwt, wbt, lg, alt_m = 40.0, 30.0, 27.4, 1.11, 110.0

WBT_F     = wbt * 1.8 + 32          # 81.32°F
Range_F   = (hwt - cwt) * 1.8       # 18.0°F
Approach_F = (cwt - wbt) * 1.8      # 4.68°F
CWT_F     = WBT_F + Approach_F      # 86.0°F

def alt_to_psi_h1(alt_m):
    if alt_m == 0: return 14.696
    alt_ft = alt_m / 0.3048
    x = alt_ft / 10000.0
    return ((0.547462*x - 7.67923)*x + 29.9309) * 0.491154 / (0.10803*x + 1.0)

P_psi = alt_to_psi_h1(alt_m)

# The 5 temperatures we need h_sat for
TEMPS = [WBT_F]
for cheb in [0.9, 0.6, 0.4, 0.1]:
    TEMPS.append(Range_F * cheb + CWT_F)

P(f"Integration setup:")
P(f"  WBT_F={WBT_F}, Range_F={Range_F}, Approach_F={Approach_F}, CWT_F={CWT_F}")
P(f"  P_psi={P_psi:.8f} PSI  (alt={alt_m}m = {alt_m/0.3048:.3f}ft)")
P(f"  Temps to probe: {[f'{t:.4f}' for t in TEMPS]}")

def kill_cti():
    os.system("taskkill /F /IM CTIToolkit.exe >nul 2>&1")
    time.sleep(0.3)

def probe_hsat_points(p_psi, temps):
    kill_cti()
    si = win32process.STARTUPINFO(); si.dwFlags=1; si.wShowWindow=0
    try:
        p_info = win32process.CreateProcess(
            None, f'"{EXE_PATH}"', None, None, False, 4,
            None, os.path.dirname(EXE_PATH), si)
    except Exception as e:
        P(f"[!] {e}"); return None
    h, ht, pid, tid = p_info; h_int = int(h)

    N = len(temps)
    alloc = 32 + N*8 + N*50 + 1024
    cave  = KERNEL32.VirtualAllocEx(h_int, 0, alloc, 0x3000, 0x40)
    if not cave: os.system(f"taskkill /F /PID {pid} >nul 2>&1"); return None

    results_addr  = cave
    sentinel_addr = cave + N*8 + 16
    code_addr     = sentinel_addr + 16

    def push_d(v):
        pk = struct.pack("<d", v)
        return b"\x68" + pk[4:8] + b"\x68" + pk[0:4]

    code = bytearray(b"\xDB\xE3")
    code += b"\xC7\x05" + struct.pack("<I", sentinel_addr) + b"\x01\x00\x00\x00"

    for idx, T_F in enumerate(temps):
        ra = results_addr + idx*8
        code += push_d(T_F) + push_d(T_F) + push_d(p_psi)
        cs = code_addr + len(code)
        code += b"\xE8" + struct.pack("<i", FUNC_HSAT - (cs+5))
        code += b"\x83\xC4\x18"
        code += b"\xDD\x1D" + struct.pack("<I", ra)

    code += b"\xC7\x05" + struct.pack("<I", sentinel_addr) + b"\x02\x00\x00\x00"
    code += b"\xEB\xFE"

    KERNEL32.WriteProcessMemory(h_int, code_addr, bytes(code), len(code), None)
    old = ctypes.c_ulong()
    KERNEL32.VirtualProtectEx(h_int, ADDR_EP, 5, 0x40, ctypes.byref(old))
    KERNEL32.WriteProcessMemory(h_int, ADDR_EP,
        b"\xE9" + struct.pack("<i", code_addr - (ADDR_EP+5)), 5, None)
    win32process.ResumeThread(ht)

    t0 = time.time(); sentinel = ctypes.c_uint32()
    while time.time() - t0 < 15:
        KERNEL32.ReadProcessMemory(h_int, sentinel_addr, ctypes.byref(sentinel), 4, None)
        if sentinel.value == 2: break
        time.sleep(0.05)

    if sentinel.value != 2:
        os.system(f"taskkill /F /PID {pid} >nul 2>&1"); P("TIMEOUT"); return None

    buf = (ctypes.c_double * N)()
    KERNEL32.ReadProcessMemory(h_int, results_addr, buf, N*8, None)
    os.system(f"taskkill /F /PID {pid} >nul 2>&1")
    return list(buf)

h_sat_probed = probe_hsat_points(P_psi, TEMPS)
if h_sat_probed is None:
    P("Probe failed"); sys.exit(1)

P(f"\nProbed h_sat values at P={P_psi:.6f} PSI:")
for T_F, hs in zip(TEMPS, h_sat_probed):
    P(f"  T={T_F:8.4f}°F → h_sat = {hs:.10f} BTU/lb")

# Compute KaV/L from probed values
h_air_in  = h_sat_probed[0]   # h_sat at WBT_F
h_air_out = Range_F * lg + h_air_in

P(f"\nIntegration:")
P(f"  h_air_in  = {h_air_in:.10f}")
P(f"  h_air_out = {h_air_out:.10f}")
P(f"  Range_F   = {Range_F}")

total = 0.0
for i, cheb in enumerate([0.9, 0.6, 0.4, 0.1]):
    T_i     = Range_F * cheb + CWT_F
    h_sat_i = h_sat_probed[i+1]
    h_air_i = (h_air_out - h_air_in) * cheb + h_air_in
    driving = h_sat_i - h_air_i
    contrib = 0.25 / driving
    P(f"  cheb={cheb}  T={T_i:.4f}  h_sat={h_sat_i:.8f}  h_air={h_air_i:.8f}  df={driving:.8f}  +{contrib:.8f}")
    total += contrib

kavl_raw  = total * Range_F
kavl_5dp  = float(f"{kavl_raw:.5f}")
kavl_str  = str(kavl_5dp)

P(f"\nResult:")
P(f"  KaV/L (raw)  = {kavl_raw:.10f}")
P(f"  KaV/L (5dp)  = {kavl_5dp}")
P(f"  KaV/L (str)  = {kavl_str}   ← what JS returns")
P(f"  GUI shows:     2.1739         ← 4dp displayed in CTI GUI")
P(f"  Our dashboard: 2.17389        ← user reports")
P()
if kavl_str == "2.17389":
    P("✓ Our engine is CORRECT — binary gives exactly 2.17389 too")
    P("  The GUI is displaying only 4dp (trailing zero stripped from 2.17390? No — 2.17389 ≠ 2.17390)")
    P("  Likely the GUI field has variable precision or rounds to 4dp for this case")
elif kavl_str == "2.1739":
    P("✓ Binary gives 2.17390 (displays as '2.1739') — our engine is WRONG by 1 ULP at 5dp")
else:
    P(f"  Binary truth: {kavl_str}  vs  Our engine: 2.17389")
    if kavl_str.startswith("2.1739"):
        P("  Very close — difference in last digit(s) only")
