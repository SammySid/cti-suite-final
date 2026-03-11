
# CTI TOOLKIT AUTOMATION: THE COMPLETE REFERENCE (v2026.4)

**Single Source of Truth for High-Speed CTI Toolkit Data Extraction**
**Last Updated: 2026-02-27 | Verified on 9950X3D**

---

## ⚠️ MANDATORY AI USAGE RULES ⚠️

**READ THIS BEFORE DOING ANYTHING. THESE RULES ARE NON-NEGOTIABLE.**

### Rule 1: NEVER EDIT Files in `important/`
The files in this directory are **production-verified, battle-tested, and locked**:
- `CTI_Complete_Reference.md` — This document (READ ONLY)
- `Psychrometrics_Siphon.py` — Production Psych harvester (DO NOT MODIFY)
- `Merkel_Siphon.py` — Production Merkel harvester (DO NOT MODIFY)

These files were painstakingly debugged and verified at full speed with 100% data integrity.
**ANY modification risks breaking the proven architecture.** Do NOT "fix", "improve", "refactor", or "clean up" these files.

### Rule 2: IMPORT and INHERIT — Create NEW Scripts
When you need to use the CTI siphons, **import the classes** from the existing scripts and create a **new script** in the `work/` directory.

```python
# ✅ CORRECT: Import and use in a NEW file (e.g., work/my_task.py)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'important'))

from Psychrometrics_Siphon import PsychrometricsSiphon
from Merkel_Siphon import MerkelSiphon

# Use the classes directly
bot = MerkelSiphon()
if bot.launch():
    result = bot.process_point(hwt=43.33, cwt=28.88, wbt=20.0, lg=1.3)
    print(result)
    bot.kill()
```

```python
# ✅ CORRECT: Extend via inheritance in a NEW file
from Psychrometrics_Siphon import PsychrometricsSiphon

class MyCustomSiphon(PsychrometricsSiphon):
    def custom_sweep(self, points_list):
        """My custom sweep logic that reuses the proven engine."""
        for dbt, wbt, alt in points_list:
            # Use parent's proven methods
            ...
```

```python
# ❌ WRONG: Never do this
# Editing Merkel_Siphon.py or Psychrometrics_Siphon.py directly
```

### Rule 3: File Locations
```
cti-suite-final/
├── important/          ← READ-ONLY. Never create or edit files here.
│   ├── CTI_Complete_Reference.md
│   ├── Psychrometrics_Siphon.py
│   └── Merkel_Siphon.py
├── official/           ← READ-ONLY. Contains the CTI Toolkit executable.
│   └── cti toolkit/
│       └── CTIToolkit.exe
└── work/               ← CREATE NEW SCRIPTS HERE
    └── (your new scripts go here)
```

---

## Table of Contents
1. [Application Overview](#1-application-overview)
2. [Architecture Summary](#2-architecture-summary)
3. [Window & Control Discovery](#3-window--control-discovery)
4. [Tab Switching Protocol](#4-tab-switching-protocol)
5. [Cross-Process I/O: The Auto-Marshal Rule](#5-cross-process-io-the-auto-marshal-rule)
6. [Psychrometrics Tab (Full Protocol)](#6-psychrometrics-tab-full-protocol)
7. [Merkel Tab (Full Protocol)](#7-merkel-tab-full-protocol)
8. [Control ID Reference Table](#8-control-id-reference-table)
9. [Input Ranges & Boundary Safety](#9-input-ranges--boundary-safety)
10. [Speed & Performance](#10-speed--performance)
11. [Watchdog, Recovery & Error Handling](#11-watchdog-recovery--error-handling)
12. [File Structure & Scripts](#12-file-structure--scripts)

---

## 1. Application Overview

**Target Application:** `CTIToolkit.exe` (32-bit Delphi)
**Location:** `official/cti toolkit/CTIToolkit.exe`
**Window Title:** Contains "Cooling Technology Institute"
**Window Class:** `TForm` (Delphi VCL)
**Unit System:** **Celsius** (default, all inputs and outputs)

The CTI Toolkit has 4 tabs. We automate 2:
- **Tab 0: Psychrometrics** — 13 output columns (P, Alt, DBT, WBT, H, DP, RH, Dens, SV, HR)
- **Tab 1: Merkel** — Single KaV/L output

---

## 2. Architecture Summary

We drive the application's **Win32 Message Pump** at full speed:

```
1. Set Input  →  WM_SETTEXT (direct Python string, OS auto-marshals)
2. Notify     →  WM_COMMAND with EN_CHANGE (0x0300) to main window
3. Calculate  →  WM_COMMAND with Button ID to main window
4. Poll       →  Read result until it commits (tab-specific strategy)
5. Save       →  Write to CSV
```

Both tabs achieve **100% data integrity** using tight polling loops with zero `time.sleep()` in the critical path.

---

## 3. Window & Control Discovery

### Find the Main Window
```python
import win32gui, win32process, subprocess, os
proc = subprocess.Popen([EXE_PATH], cwd=os.path.dirname(EXE_PATH))
pid = proc.pid
# Wait 4 seconds for app startup

hwnd = 0
def find_main(h, _):
    if win32gui.IsWindowVisible(h):
        _, p = win32process.GetWindowThreadProcessId(h)
        if p == pid and "Cooling" in win32gui.GetWindowText(h):
            global hwnd; hwnd = h; return False
    return True
win32gui.EnumWindows(find_main, None)
```

### Cache All Control HWNDs
```python
ctrls = {}
def enum_cb(h, _):
    ctrls[win32gui.GetDlgCtrlID(h)] = h
    return True
win32gui.EnumChildWindows(hwnd, enum_cb, None)
```

### Parent Hierarchy
```
Desktop
  └── TForm (Main Window)                              ← hwnd
        ├── SysTabControl32 (Tab bar)                   ← h_tab
        ├── [Psychrometrics controls: 1002-1015]        ← direct children
        └── #32770 (Dialog: "  Merkel  ")               ← child dialog
              ├── Edit 1020-1023, 1029-1030
              ├── Button 1027 (&Recalculate)
              └── Static labels
```

> **Key:** Merkel controls live inside a `#32770` dialog, but all `WM_COMMAND` notifications must be sent to the **main `hwnd`** — the TForm routes them internally.

---

## 4. Tab Switching Protocol

Tab switching uses a **Ghost Click** — a simulated click via `SendMessage` that doesn't move the real cursor and works even when hidden.

### Tab Coordinates

| Index | Tab Name | Center (X, Y) |
| :---: | :--- | :--- |
| 0 | Psychrometrics | (~50, 11) |
| 1 | Merkel | (~125, 11) |

### Code
```python
# Find SysTabControl32
h_tab = 0
def find_tab(h, _):
    if "SysTabControl32" in win32gui.GetClassName(h):
        nonlocal h_tab; h_tab = h; return False
    return True
win32gui.EnumChildWindows(hwnd, find_tab, None)

# Ghost Click at Merkel tab center
lparam = win32api.MAKELONG(125, 11)
win32gui.SendMessage(h_tab, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
win32gui.SendMessage(h_tab, win32con.WM_LBUTTONUP, 0, lparam)

# CRITICAL: Wait 2.0 seconds for child dialog initialization!
time.sleep(2.0)

# Re-enumerate controls (new HWNDs after tab switch)
win32gui.EnumChildWindows(hwnd, enum_cb, None)
```

### Timing

| Event | Wait | Reason |
| :--- | :--- | :--- |
| After app launch | **4.0s** | Full startup |
| After tab switch | **2.0s** | Child dialog created lazily |
| Between calculations | **0s** | Tight poll loop handles timing |

---

## 5. Cross-Process I/O: The Auto-Marshal Rule

**The most important rule in the system.** Getting this wrong causes silent failures.

### Auto-Marshalled by OS (Use LOCAL Buffers) — For Edit Controls
```python
# WRITE: Direct Python string → remote Edit control
win32gui.SendMessage(h_edit, win32con.WM_SETTEXT, 0, "43.33")

# READ: Local ctypes buffer → OS copies from remote Edit
buf = ctypes.create_string_buffer(64)
ctypes.windll.user32.SendMessageA(h_edit, win32con.WM_GETTEXT, 64, buf)
result = buf.value.decode('ascii', errors='ignore').strip()
```

### NOT Auto-Marshalled (Require Remote Buffers) — For ListView
```python
# ListView reads require VirtualAllocEx + WriteProcessMemory + ReadProcessMemory
remote_buf = kernel32.VirtualAllocEx(h_proc, 0, 4096, 0x1000, 0x04)
# Write LVITEM struct → remote, SendMessage with remote pointer, ReadProcessMemory back
```

**Summary:** `WM_SETTEXT`/`WM_GETTEXT` on Edit controls = local buffers. `LVM_GETITEMTEXT` on ListView = remote buffers.

---

## 6. Psychrometrics Tab (Full Protocol)

### Speed: ~250 pts/sec

### Controls
| Field | ID | Type |
| :--- | :--- | :--- |
| Altitude | `1002` | Edit |
| DBT | `1003` | Edit |
| WBT | `1004` | Edit |
| Recalculate | `1007` | Button |
| Results | `1015` | SysListView32 (10 rows) |

### Output Rows (ListView ID 1015)
| Row | Property | Row | Property |
| :--- | :--- | :--- | :--- |
| 0 | Pressure (P) | 5 | Dew Point (DP) |
| 1 | Altitude (Alt) | 6 | Relative Humidity (RH) |
| 2 | Dry Bulb (DBT) | 7 | Density (Dens) |
| 3 | Wet Bulb (WBT) | 8 | Specific Volume (SV) |
| 4 | Enthalpy (H) | 9 | Humidity Ratio (HR) |

### Protocol
```python
# 1. Set inputs
win32gui.SendMessage(h_alt, WM_SETTEXT, 0, "0.0")
win32gui.SendMessage(hwnd, WM_COMMAND, (0x0300 << 16) | 1002, h_alt)
win32gui.SendMessage(h_dbt, WM_SETTEXT, 0, "30.00")
win32gui.SendMessage(hwnd, WM_COMMAND, (0x0300 << 16) | 1003, h_dbt)
win32gui.SendMessage(h_wbt, WM_SETTEXT, 0, "20.00")
win32gui.SendMessage(hwnd, WM_COMMAND, (0x0300 << 16) | 1004, h_wbt)

# 2. Trigger Recalculate
win32gui.SendMessage(hwnd, WM_COMMAND, 1007, 0)

# 3. Input-Match Polling: read ListView Row 2 (DBT) until it matches input
# 4. Bulk Siphon: read all 10 rows via LVM_GETITEMTEXTW
```

### Sync Strategy: Input-Match Polling
Poll **Row 2 (DBT)** in ListView until it matches requested input. Once it matches, all rows are current.

---

## 7. Merkel Tab (Full Protocol)

### Speed: ~600 pts/sec

### Controls
| Field | ID | Type |
| :--- | :--- | :--- |
| HWT (T1) | `1020` | Edit |
| CWT (T2) | `1021` | Edit |
| WBT | `1022` | Edit |
| L/G | `1023` | Edit |
| Altitude | `1030` | Edit |
| Recalculate | `1027` | Button |
| KaV/L Result | `1029` | Edit |

### Protocol
```python
# 1. Set inputs (direct string, auto-marshalled)
for cid, val in [(1020, "43.33"), (1021, "28.88"), (1022, "20.00"), (1023, "1.300")]:
    h = ctrls[cid]
    win32gui.SendMessage(h, WM_SETTEXT, 0, val)
    win32gui.SendMessage(hwnd, WM_COMMAND, (0x0300 << 16) | cid, h)

# 2. Trigger Recalculate
win32gui.SendMessage(hwnd, WM_COMMAND, 1027, ctrls[1027])

# 3. Empty-to-Value Polling: read Edit 1029 until non-empty
buf = ctypes.create_string_buffer(64)
ctypes.windll.user32.SendMessageA(ctrls[1029], WM_GETTEXT, 64, buf)
result = buf.value.decode('ascii', errors='ignore').strip()
```

### Sync Strategy: Empty-to-Value Polling
The engine **clears the result field during calculation**, then fills it when done. Poll until non-empty.

**IMPORTANT:** Use `ctypes.windll.user32.SendMessageA()` with local buffer. Do NOT use `win32gui.GetWindowText()`.

---

## 8. Control ID Reference Table

| Tab | Feature | ID | Widget | Parent |
| :--- | :--- | :--- | :--- | :--- |
| **Psych** | Altitude | `1002` | Edit | Main Window |
| **Psych** | DBT Input | `1003` | Edit | Main Window |
| **Psych** | WBT Input | `1004` | Edit | Main Window |
| **Psych** | Recalculate | `1007` | Button | Main Window |
| **Psych** | Results | `1015` | SysListView32 | Main Window |
| **Merkel** | HWT (T1) | `1020` | Edit | Dialog #32770 |
| **Merkel** | CWT (T2) | `1021` | Edit | Dialog #32770 |
| **Merkel** | WBT | `1022` | Edit | Dialog #32770 |
| **Merkel** | L/G | `1023` | Edit | Dialog #32770 |
| **Merkel** | Recalculate | `1027` | Button | Dialog #32770 |
| **Merkel** | KaV/L Result | `1029` | Edit | Dialog #32770 |
| **Merkel** | Altitude | `1030` | Edit | Dialog #32770 |

---

## 9. Input Ranges & Boundary Safety

### All Units: Celsius

### Psychrometrics

| Input | Range | Constraint |
| :--- | :--- | :--- |
| DBT | 0 – 60 °C | DBT > WBT always |
| WBT | 0 – 50 °C | WBT < DBT |
| Altitude | 0 – 3000 m | — |

### Merkel

| Input | Range | Constraint |
| :--- | :--- | :--- |
| HWT (T1) | 30 – 70 °C | HWT > CWT |
| CWT (T2) | 20 – 50 °C | CWT > WBT |
| WBT | 15 – 40 °C | WBT < CWT |
| L/G | 0.5 – 3.0 | > 0 |
| Altitude | 0 – 2000 m | — |

### ⚠️ KNOWN CRASH POINTS (App Hangs — Must Be Avoided)

These exact input combinations cause the CTI engine to **hang permanently** (infinite loop in the math kernel). The app becomes completely unresponsive and must be killed.

| # | DBT | WBT | Confirmed | Fix |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `DBT == WBT` (any value) | same | Yes | Subtract 0.01 from WBT |
| 2 | `73.00` | `27.00` | **Yes (tested 2026-02-17)** | Nudge WBT by ±0.01 |
| 3 | `42.00` | `13.50` | Historical | Skip point |
| 4 | `93.00` | `10.00` | Historical | Skip point |

### Nudge Strategy (Tested & Verified)

For crash point #2 (`DBT=73, WBT=27`), testing confirmed:
- **`WBT=27.01`** → ✅ Works (1.7ms)
- **`WBT=26.99`** → ✅ Works (1.3ms)
- **`DBT=73.01`** → ✅ Works (1.3ms)
- **`DBT=72.99`** → ✅ Works (1.4ms)
- **ALL ±0.1 nudges** → ✅ All work

**The hang is ONLY on the EXACT values.** A ±0.01 nudge completely bypasses it.

### Recommended Guard Code
```python
# Add this check before calling process_point or setting inputs:
KNOWN_HANG_PAIRS = [(73.00, 27.00), (42.00, 13.50), (93.00, 10.00)]

def safe_inputs(dbt, wbt):
    """Nudge inputs away from known CTI crash points."""
    # Rule 1: DBT must never equal WBT (100% RH hang)
    if abs(dbt - wbt) < 0.001:
        wbt -= 0.01
    # Rule 2: Check known exact hang pairs
    for bad_dbt, bad_wbt in KNOWN_HANG_PAIRS:
        if abs(dbt - bad_dbt) < 0.001 and abs(wbt - bad_wbt) < 0.001:
            wbt += 0.01
    return dbt, wbt
```

### Merkel Boundary Notes
- HWT ≤ CWT or CWT ≤ WBT → **empty result** (no hang, just skip)
- Very close temps (HWT - CWT < 1°C) → valid but very small KaV/L (~0.001)

---

## 10. Speed & Performance

### Verified Benchmarks (9950X3D)

| Tab | Speed | Points | Duration | Success |
| :--- | :--- | :--- | :--- | :--- |
| **Psychrometrics** | ~250 pts/sec | 1,000 | ~4s | 100% |
| **Merkel** | ~600 pts/sec | 1,000 | ~1.7s | 100% |

### Why Merkel is Faster
- Merkel: 1 Edit read (`WM_GETTEXT` + local buffer) = **1 syscall**
- Psych: 10 ListView reads (`LVM_GETITEMTEXTW` + remote buffer + `ReadProcessMemory`) = **multiple syscalls**

### Limits
- Total system throughput caps at **~600 pts/sec** regardless of instance count.
- **Best practice:** Use 1 instance at full speed.

---

## 11. Watchdog, Recovery & Error Handling

### Proactive Reset
The CTI Toolkit leaks GDI handles at Nitro speeds.
- **Every 5,000 points OR 2 minutes:** Kill → Wait 2s → Relaunch
- **Downtime:** 4s (launch) + 2s (tab switch) = **6 seconds per reset**
- **After relaunch:** Must re-enumerate ALL control HWNDs

### Sync Guards

| Tab | Method | How It Works |
| :--- | :--- | :--- |
| **Psych** | Input-Match | Poll ListView Row 2 (DBT) until it matches requested input |
| **Merkel** | Empty-to-Value | Poll Edit 1029 until result is non-empty |

### Hang Detection with `SendMessageTimeout`
For sweeps that may hit crash points, use `SendMessageTimeoutW` instead of `SendMessage` for the recalculate command. If the engine hangs, this returns after the timeout instead of blocking forever:
```python
import ctypes
SMTO_ABORTIFHUNG = 0x0002
result = ctypes.c_ulong(0)
ret = ctypes.windll.user32.SendMessageTimeoutW(
    hwnd, WM_COMMAND, 1007, 0,
    SMTO_ABORTIFHUNG, 5000,  # 5 second timeout
    ctypes.byref(result)
)
if ret == 0:
    # Engine is hung — kill and relaunch
    ...
```

### Error Types

| Error | Symptom | Tab | Recovery |
| :--- | :--- | :--- | :--- |
| Empty Result | WM_GETTEXT returns "" | Merkel | Skip (boundary violation) |
| "ERROR!" | Text reads "ERROR!" | Merkel | Skip (math overflow) |
| Stale Data | Same result as previous | Psych | Re-poll |
| **App Hang** | **SendMessage never returns** | **Both** | **Kill + Relaunch** |
| Known Crash Pair | DBT=73/WBT=27 etc. | Psych | **Nudge by ±0.01** |

---

## 12. File Structure & Scripts

```
cti-suite-final/
├── HANDOFF.md                              ← Project overview & formula documentation
├── cti_dashboard/                          ← ★ Standalone web dashboard (no binary at runtime)
│   ├── index.html
│   ├── js/psychro-engine.js                ← Psychrometric engine (98.19% bit-perfect)
│   ├── js/merkel-engine.js                 ← Merkel engine (100% parity, loads binary table)
│   └── README.md
├── important/                              ← 🔒 READ-ONLY
│   ├── CTI_Complete_Reference.md           ← This document (siphon reference)
│   ├── Psychrometrics_Siphon.py            ← Production Psych harvester (~250 pts/sec)
│   ├── Merkel_Siphon.py                    ← Production Merkel harvester (~600 pts/sec)
│   └── Merkel_Output.csv                   ← 1000-point Merkel truth dataset
├── work/
│   ├── merkel_tables_10m_018F.bin          ← ★ 12.8 MB pre-probed table (deploy with dashboard)
│   ├── merkel_tables_10m_018F.json         ← Table grid metadata
│   ├── merkel_gen_10m_018F.py              ← Table generator (re-run on Windows to reproduce)
│   ├── merkel_parity_comprehensive.py      ← 320-case parity test (100% pass)
│   ├── merkel_altitude_verify.py           ← Python reference Merkel engine
│   ├── check_2173_probe.py                 ← Spot-check any input vs binary
│   ├── merkel_deep_disasm.txt              ← Merkel function disassembly reference
│   └── archive/                            ← All exploratory scripts (historical)
├── official/
│   └── cti toolkit/                        ← Official CTI Toolkit binary
└── tools/
    └── w64devkit/                           ← Development toolchain
```

### Production Siphons (Win32 GUI Automation)

| Script | Location | Purpose | Speed |
| :--- | :--- | :--- | :--- |
| `Psychrometrics_Siphon.py` | `important/` | 13-column psychrometric extraction | ~250 pts/sec |
| `Merkel_Siphon.py` | `important/` | KaV/L cooling tower characteristic | ~600 pts/sec |

### Running Siphons
```bash
cd important
python Psychrometrics_Siphon.py   # → Psychrometrics_Output.csv
python Merkel_Siphon.py           # → Merkel_Output.csv
```

### Importing Siphons
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'important'))
from Psychrometrics_Siphon import PsychrometricsSiphon
from Merkel_Siphon import MerkelSiphon
```

### Standalone Dashboard (No CTI Binary at Runtime)
The `cti_dashboard/` web app uses pre-probed binary tables for 100% parity without the exe:
- **Psychrometrics:** 98.19% bit-perfect via Hyland-Wexler formula reimplementation
- **Merkel KaV/L:** 100% exact (320/320 across 8 altitudes) via `work/merkel_tables_10m_018F.bin`
- Works on Linux, Mac, Windows, any browser

---

**STATUS: FULL PRODUCTION**
- **Siphons:** Psychrometrics ~250 pts/sec, Merkel ~600 pts/sec — 100% data integrity
- **Dashboard:** 100% Merkel parity (all altitudes 0–2000m) · 98.19% Psychrometrics — zero runtime binary dependency
