"""
f_dense_probe.py
================
Probe f(0x408005) for T = -5..59°C at 1°C step, alt = 0, 500, 1000, 1500 m.
Replaces 2°C F_ALT_TABLE with 1°C table to eliminate interpolation-induced H error.
"""
import os, sys, math, struct, ctypes, time

try:
    import win32process
except ImportError:
    print("pip install pywin32"); sys.exit(1)

KERNEL32 = ctypes.windll.kernel32
HERE     = os.path.dirname(os.path.abspath(__file__))
EXE_PATH = os.path.abspath(os.path.join(HERE, '..', 'official', 'cti toolkit', 'CTIToolkit.exe'))

ADDR_EP  = 0x004569CE
FUNC_F   = 0x00408005

def push_d(v):
    pk = struct.pack('<d', v)
    return b'\x68' + pk[4:8] + b'\x68' + pk[0:4]

def kill_cti():
    os.system('taskkill /F /IM CTIToolkit.exe >nul 2>&1'); time.sleep(0.2)

def alt_to_P_kPa(alt_m):
    return 101.325 * (1 - 2.25577e-5 * alt_m) ** 5.2559

def C_to_F(T_C):
    return T_C * 1.8 + 32.0

def kPa_to_psi(P_kPa):
    return P_kPa * 14.696 / 101.325

def probe_f_batch(cases_CF, timeout=30.0):
    """Probe f(T_F, P_psi) for all cases in one EP-hijack batch."""
    N = len(cases_CF)
    kill_cti()
    si = win32process.STARTUPINFO(); si.dwFlags=1; si.wShowWindow=0
    p_info = win32process.CreateProcess(
        None, '"'+EXE_PATH+'"', None, None, False, 4,
        None, os.path.dirname(EXE_PATH), si)
    h, ht, pid, tid = p_info; h_int = int(h)

    off_res  = 0
    off_sent = N * 8 + 8
    off_code = off_sent + 8
    alloc_sz = off_code + N * 40 + 4096

    cave = KERNEL32.VirtualAllocEx(h_int, 0, alloc_sz, 0x3000, 0x40)
    if not cave:
        KERNEL32.TerminateProcess(h_int, 1)
        raise RuntimeError("VirtualAllocEx failed")

    sentinel_val = struct.pack('<d', 3.14159265)
    blob = bytearray(alloc_sz)
    blob[off_sent:off_sent+8] = sentinel_val

    sc = bytearray()
    for i, (T_F, P_psi) in enumerate(cases_CF):
        sc += push_d(P_psi)
        sc += push_d(T_F)
        abs_call_target = FUNC_F
        rel = abs_call_target - (cave + off_code + len(sc) + 5)
        sc += b'\xe8' + struct.pack('<i', rel)
        sc += b'\x83\xc4\x10'
        sc += b'\xdd\x1d' + struct.pack('<I', cave + i * 8)

    res_addr = cave + off_sent
    sc += b'\xdd\x1d' + struct.pack('<I', res_addr)
    rel_back = ADDR_EP - (cave + off_code + len(sc) + 5)
    sc += b'\xe9' + struct.pack('<i', rel_back)

    blob[off_code:off_code+len(sc)] = sc

    written = ctypes.c_size_t(0)
    KERNEL32.WriteProcessMemory(h_int, cave, bytes(blob), alloc_sz, ctypes.byref(written))

    jmp = b'\xe9' + struct.pack('<i', (cave + off_code) - (ADDR_EP + 5))
    KERNEL32.WriteProcessMemory(h_int, ADDR_EP, jmp, 5, ctypes.byref(written))

    ht_int = int(ht)
    KERNEL32.ResumeThread(ht_int)

    start = time.time()
    res_buf = (ctypes.c_uint8 * 8)()
    while time.time() - start < timeout:
        KERNEL32.ReadProcessMemory(h_int, res_addr, res_buf, 8, ctypes.byref(ctypes.c_size_t(0)))
        if bytes(res_buf) != sentinel_val:
            break
        time.sleep(0.05)
    else:
        KERNEL32.TerminateProcess(h_int, 1)
        raise RuntimeError(f"Timeout after {timeout}s — shellcode did not complete")

    time.sleep(0.1)
    out_buf = (ctypes.c_uint8 * (N*8))()
    KERNEL32.ReadProcessMemory(h_int, cave, out_buf, N*8, ctypes.byref(ctypes.c_size_t(0)))
    KERNEL32.TerminateProcess(h_int, 1)
    kill_cti()

    return [struct.unpack('<d', bytes(out_buf[i*8:(i+1)*8]))[0] for i in range(N)]

# Grid: T = -5 to 59°C, 1°C step (65 values), 4 altitudes
TEMPS_C = list(range(-5, 60))   # -5,-4,...,59 → 65 values
ALT_M   = [0, 500, 1000, 1500]

print(f"Probing f: {len(TEMPS_C)} temps × {len(ALT_M)} altitudes = {len(TEMPS_C)*len(ALT_M)} total calls")
print(f"EXE: {EXE_PATH}")

all_cases = []
labels    = []
for alt in ALT_M:
    P_kPa = alt_to_P_kPa(alt)
    P_psi = kPa_to_psi(P_kPa)
    for T_C in TEMPS_C:
        T_F = C_to_F(T_C)
        all_cases.append((T_F, P_psi))
        labels.append((alt, T_C, P_kPa))

print(f"Running probe (batch of {len(all_cases)})...")
t0 = time.time()
results = probe_f_batch(all_cases, timeout=60.0)
print(f"Done in {time.time()-t0:.1f}s")

# Organise by altitude row
by_alt = {}
for (alt, T_C, P_kPa), f_val in zip(labels, results):
    if alt not in by_alt:
        by_alt[alt] = []
    by_alt[alt].append((T_C, f_val))

# Print table and generate JS/Python array literals
print()
print("Results:")
for alt in ALT_M:
    row = by_alt[alt]
    vals = [v for (_, v) in row]
    print(f"\n// alt={alt}m ({len(vals)} values, T=-5..59°C step 1°C)")
    # Print in rows of 8 for readability
    for i in range(0, len(vals), 8):
        chunk = vals[i:i+8]
        print("  " + ", ".join(f"{v:.14f}" for v in chunk) + ",")

print()
print("Saving to f_dense_probe.csv ...")
import csv
outpath = os.path.join(HERE, 'f_dense_probe.csv')
with open(outpath, 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['alt_m', 'T_C', 'P_kPa', 'f_bin'])
    for (alt, T_C, P_kPa), f_val in zip(labels, results):
        w.writerow([alt, T_C, f'{P_kPa:.6f}', f'{f_val:.14f}'])
print(f"Saved to {outpath}")
