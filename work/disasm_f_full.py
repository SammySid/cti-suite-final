"""
Disassemble 0x408005 (f function), 0x456019 (pow helper), and decode all constants.
Shows the FULL computation to understand what the f function actually computes.
"""
import ctypes, struct, time, os

try:
    import win32process
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
except ImportError as e:
    print(f"Missing: {e}"); import sys; sys.exit(1)

KERNEL32 = ctypes.windll.kernel32
EXE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                    '..', 'official', 'cti toolkit', 'CTIToolkit.exe'))

os.system("taskkill /F /IM CTIToolkit.exe >nul 2>&1"); time.sleep(0.3)
si = win32process.STARTUPINFO(); si.dwFlags=1; si.wShowWindow=0
p_info = win32process.CreateProcess(None, '"'+EXE+'"', None, None, False,
                                     8, None, os.path.dirname(EXE), si)
h, ht, pid, tid = p_info; h_int = int(h)
time.sleep(1.5)

def rb(addr, n):
    buf = ctypes.create_string_buffer(n); nr = ctypes.c_size_t(0)
    KERNEL32.ReadProcessMemory(h_int, addr, buf, n, ctypes.byref(nr))
    return buf.raw[:nr.value]

cs = Cs(CS_ARCH_X86, CS_MODE_32)

def decode_const_pair(lo_dw, hi_dw):
    return struct.unpack('<d', struct.pack('<II', lo_dw, hi_dw))[0]

# Read full f function (800 bytes to cover the whole thing)
for name, addr, n_bytes in [
    ("f(0x408005)",          0x00408005, 800),
    ("0x456019 (pow helper)", 0x00456019, 200),
    ("0x40893C (sub)",        0x0040893C, 400),
    ("0x4089E0 (psychro eq)", 0x004089E0, 400),
]:
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    data = rb(addr, n_bytes)
    if not data:
        print("  (empty)")
        continue

    insns = list(cs.disasm(data, addr))

    # Track constant pairs being loaded (mov [ebp-N], imm)
    pending = {}   # offset → low_dword
    for ins in insns:
        # Detect: mov dword ptr [ebp-N], imm32
        if ins.mnemonic == 'mov' and '[ebp -' in ins.op_str:
            parts = ins.op_str.split(',')
            if len(parts) == 2:
                loc = parts[0].strip()
                val = parts[1].strip()
                try:
                    offset_s = loc.replace('dword ptr [ebp - ','').replace(']','').strip()
                    offset = int(offset_s, 16)
                    imm    = int(val, 16)
                    if offset not in pending:
                        pending[offset] = imm    # this is the LOW dword (stored first)
                    else:
                        # Already have low dword, this is high dword
                        lo = pending.pop(offset)
                        hi = imm
                        v  = decode_const_pair(lo, hi)
                        print(f"  CONST [ebp-0x{offset:02x}] = {v:+.10e}   (0x{hi:08x}_{lo:08x})")
                except:
                    pass

    print()
    for i, ins in enumerate(insns):
        print(f"  {ins.address:08X}:  {ins.mnemonic:<8} {ins.op_str}")
        if i >= 79:
            print(f"  ... ({len(insns)-80} more instructions, total={len(insns)})")
            break

os.system("taskkill /F /PID " + str(pid) + " >nul 2>&1")

# Also decode constants from addresses in Final Conversion (0x409418):
# 0x487af0 and 0x487b18 referenced by fld and fdiv
print()
print("=" * 70)
print("  Globals from 0x409418 (Final Conversion) referenced addresses")
print("=" * 70)
os.system("taskkill /F /IM CTIToolkit.exe >nul 2>&1"); time.sleep(0.3)
p2 = win32process.CreateProcess(None, '"'+EXE+'"', None, None, False,
                                  8, None, os.path.dirname(EXE), si)
h2, ht2, pid2, tid2 = p2; h2_int = int(h2)
time.sleep(1.5)
for gaddr, label in [(0x487af0,'fld_const'), (0x487b18,'fdiv_const'), (0x487b90,'Pws_compare_zero'), (0x487c10,'Pws_addend')]:
    data = rb.__func__(h2_int, gaddr, 8) if hasattr(rb,'__func__') else b''
    # rb is a closure, just call it directly
    buf = ctypes.create_string_buffer(8); nr2=ctypes.c_size_t(0)
    KERNEL32.ReadProcessMemory(h2_int, gaddr, buf, 8, ctypes.byref(nr2))
    if nr2.value == 8:
        v = struct.unpack('<d', buf.raw[:8])[0]
        print(f"  0x{gaddr:08X} ({label}) = {v:.10e}")
    else:
        print(f"  0x{gaddr:08X} ({label}) = (unreadable)")
os.system("taskkill /F /PID " + str(pid2) + " >nul 2>&1")
print("\nDone.")
