"""
MERKEL NITRO SIPHON (v2026 PRODUCTION)
=======================================
High-speed KaV/L data extraction from the CTI Toolkit Merkel tab.
Calculates Merkel cooling tower characteristic at ~617 pts/sec.

USAGE:
    python Merkel_Siphon.py
    
    Or import as a module:
        from Merkel_Siphon import MerkelSiphon
        bot = MerkelSiphon()
        if bot.launch():
            result = bot.process_point(hwt=43.33, cwt=28.88, wbt=20.0, lg=1.3)
            print(result)  # e.g. "4.18559"
            bot.kill()

ARCHITECTURE:
    - Input:  WM_SETTEXT with direct Python strings (OS auto-marshals cross-process)
    - Notify: EN_CHANGE (0x0300) to MAIN window (not the #32770 dialog parent)
    - Calc:   WM_COMMAND with Button ID 1027 to MAIN window
    - Read:   ctypes.windll.user32.SendMessageA + WM_GETTEXT into LOCAL buffer
    - Sync:   Poll until result is non-empty (engine clears result during calc)

    CRITICAL: Edit controls use LOCAL buffers (auto-marshalled by OS).
    Do NOT use WriteProcessMemory/ReadProcessMemory for Edit controls.
    Only ListView (Psychrometrics) needs remote buffers.

CONTROL IDS:
    HWT (T1):         1020 (Edit, parent: #32770 dialog)
    CWT (T2):         1021 (Edit, parent: #32770 dialog)
    WBT:              1022 (Edit, parent: #32770 dialog)
    L/G:              1023 (Edit, parent: #32770 dialog)
    KaV/L Result:     1029 (Edit, parent: #32770 dialog)
    Altitude:         1030 (Edit, parent: #32770 dialog)
    Recalculate:      1027 (Button, parent: #32770 dialog)

TAB SWITCH: Ghost Click at SysTabControl32 coordinate (125, 11) for Tab 1 (Merkel).
            Must wait 2.0 seconds after switch for child dialog to initialize.

UNITS: Celsius (all inputs and outputs)
VALID RANGES: HWT 30-70C, CWT 20-50C, WBT 15-40C, LG 0.5-3.0, Alt 0-2000m
CONSTRAINTS: HWT > CWT > WBT always. Violations produce empty results.

SPEED: ~617 pts/sec (verified on 9950X3D, 1000 points, 100% success)
"""
import csv
import time
import ctypes
import subprocess
import os
import win32api
import win32gui
import win32con
import win32process

# Path to CTI Toolkit executable (relative to this script's location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXE = os.path.join(SCRIPT_DIR, "..", "official", "cti toolkit", "CTIToolkit_Ghost_Engine.exe")
DEFAULT_CSV = os.path.join(SCRIPT_DIR, "Merkel_Output.csv")


class MerkelSiphon:
    """Production-grade Merkel KaV/L data harvester for CTI Toolkit."""

    def __init__(self, exe_path=DEFAULT_EXE):
        self.exe_path = os.path.abspath(exe_path)
        self.cmd_dir = os.path.dirname(self.exe_path)
        self.hwnd = None
        self.pid = None
        
        # Merkel Control IDs (CTI Toolkit Build 2026)
        self.ID_HWT    = 1020   # HWT (T1) Edit
        self.ID_CWT    = 1021   # CWT (T2) Edit
        self.ID_WBT    = 1022   # WBT Edit
        self.ID_LG     = 1023   # L/G Edit
        self.ID_ALT    = 1030   # Altitude Edit
        self.ID_RESULT = 1029   # KaV/L Result Edit
        self.ID_CALC   = 1027   # Recalculate Button
        
        self.ctrls = {}
        self.user32 = ctypes.windll.user32

    def launch(self, visible=True):
        """
        Launch CTI Toolkit, switch to Merkel tab, and initialize controls.
        
        Steps:
        1. Kill any existing instance
        2. Launch fresh process
        3. Find main window (TForm containing "Cooling")
        4. Ghost Click on SysTabControl32 at (125, 11) to switch to Merkel tab
        5. Wait 2.0 seconds for child dialog (#32770) to initialize
        6. Enumerate and cache all control HWNDs
        """
        print("[*] Launching Merkel Nitro Engine...")
        self.kill()
        time.sleep(0.5)
        
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = win32con.SW_SHOW if visible else win32con.SW_HIDE
        proc = subprocess.Popen([self.exe_path], startupinfo=si, cwd=self.cmd_dir)
        self.pid = proc.pid
        
        # Window Discovery (timeout: 10 seconds)
        timeout = time.time() + 10
        while time.time() < timeout:
            def cb(h, _):
                if win32gui.IsWindow(h) and win32gui.IsWindowVisible(h):
                    _, p = win32process.GetWindowThreadProcessId(h)
                    if p == self.pid and "Cooling" in win32gui.GetWindowText(h):
                        self.hwnd = h; return False
                return True
            win32gui.EnumWindows(cb, None)
            if self.hwnd: break
            time.sleep(0.5)
            
        if not self.hwnd:
            print("[!] Failed to find main window.")
            return False

        # Tab Switch: Ghost Click on SysTabControl32 at Merkel tab center (125, 11)
        h_tab = 0
        def find_tab(h, _):
            if "SysTabControl32" in win32gui.GetClassName(h):
                nonlocal h_tab; h_tab = h; return False
            return True
        win32gui.EnumChildWindows(self.hwnd, find_tab, None)
        
        if h_tab:
            print("[*] Switching to Merkel Tab (Ghost Click at 125, 11)...")
            lparam = win32api.MAKELONG(125, 11)
            win32gui.SendMessage(h_tab, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            win32gui.SendMessage(h_tab, win32con.WM_LBUTTONUP, 0, lparam)
            time.sleep(2.0)  # Wait for child dialog + controls to initialize

        # Enumerate and cache ALL child control HWNDs
        def enum_cb(h, _):
            self.ctrls[win32gui.GetDlgCtrlID(h)] = h; return True
        win32gui.EnumChildWindows(self.hwnd, enum_cb, None)
        
        required = [self.ID_HWT, self.ID_CWT, self.ID_WBT, self.ID_LG, self.ID_RESULT, self.ID_CALC]
        missing = [cid for cid in required if cid not in self.ctrls]
        if missing:
            print(f"[!] Missing controls: {missing}")
            return False
        
        # Read defaults to confirm unit system
        default_result = self.get_result()
        default_hwt = self._read_input(self.ID_HWT)
        default_cwt = self._read_input(self.ID_CWT)
        default_wbt = self._read_input(self.ID_WBT)
        print(f"[OK] Merkel ready. Defaults: HWT={default_hwt} CWT={default_cwt} WBT={default_wbt} KaV/L={default_result}")
        return True

    def kill(self):
        """Kill the CTI Toolkit process."""
        if self.pid:
            os.system(f"taskkill /F /PID {self.pid} >nul 2>&1")
            self.pid = None

    def _read_input(self, ctrl_id):
        """
        Read text from any Edit control using LOCAL buffer.
        Windows auto-marshals WM_GETTEXT across process boundaries.
        """
        buf = ctypes.create_string_buffer(64)
        self.user32.SendMessageA(self.ctrls[ctrl_id], win32con.WM_GETTEXT, 64, buf)
        return buf.value.decode('ascii', errors='ignore').strip()

    def get_result(self):
        """Read KaV/L result from Edit control 1029."""
        return self._read_input(self.ID_RESULT)

    def process_point(self, hwt, cwt, wbt, lg, alt=0.0):
        """
        Calculate KaV/L for a single set of inputs at full speed.
        
        Args:
            hwt: Hot Water Temperature (Celsius, 30-70)
            cwt: Cold Water Temperature (Celsius, 20-50)
            wbt: Wet Bulb Temperature (Celsius, 15-40)
            lg:  Liquid-to-Gas ratio (0.5-3.0)
            alt: Altitude in meters (0-2000)
        
        Returns:
            KaV/L value as string, or "N/A" if calculation failed.
        
        Sync Strategy:
            The engine CLEARS the result field to empty during recalculation,
            then fills it with the new value when done. We poll until non-empty.
        """
        # A. Inject all inputs (direct string, OS auto-marshals cross-process)
        inputs = [
            (self.ID_HWT, f"{hwt:.2f}"),
            (self.ID_CWT, f"{cwt:.2f}"),
            (self.ID_WBT, f"{wbt:.2f}"),
            (self.ID_LG,  f"{lg:.3f}"),
        ]
        if self.ID_ALT in self.ctrls:
            inputs.append((self.ID_ALT, f"{alt:.1f}"))
        
        for cid, val in inputs:
            h = self.ctrls[cid]
            win32gui.SendMessage(h, win32con.WM_SETTEXT, 0, val)
            win32gui.SendMessage(self.hwnd, win32con.WM_COMMAND, (0x0300 << 16) | cid, h)

        # B. Trigger Recalculate (WM_COMMAND to MAIN window, not dialog)
        win32gui.SendMessage(self.hwnd, win32con.WM_COMMAND, self.ID_CALC, self.ctrls[self.ID_CALC])
        
        # C. Empty-to-Value Polling (tight loop, no sleep)
        for _ in range(3000):
            current = self.get_result()
            if current:  # Any non-empty string = calculation complete
                return current
        
        return "N/A"

    def run_sweep(self, count, filename):
        """
        Run a parameter sweep and save results to CSV.
        
        Default sweep (Celsius, constraints always satisfied):
          HWT: 40 + (i * 0.03)   [range 40-70 C]
          CWT: 28 + (i * 0.02)   [range 28-48 C]  
          WBT: 20 (fixed)
          LG:  1.0 + (i * 0.001) [range 1.0-2.0]
        """
        print(f"[*] MERKEL NITRO: Sweeping {count} points -> {filename}")
        ok = 0
        na = 0
        errors = 0
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["HWT", "CWT", "WBT", "LG", "ALT", "KaVL"])
            t0 = time.time()
            
            for i in range(count):
                h = 40.0 + (i * 0.03)
                c = 28.0 + (i * 0.02)
                w = 20.0
                lg = 1.0 + (i * 0.001)
                a = 0.0
                
                res = self.process_point(h, c, w, lg, a)
                writer.writerow([f"{h:.2f}", f"{c:.2f}", f"{w:.2f}", f"{lg:.3f}", f"{a:.1f}", res])
                
                if res == "N/A":
                    na += 1
                elif "ERROR" in res.upper():
                    errors += 1
                else:
                    ok += 1
                
                if i > 0 and i % 100 == 0:
                    dt = time.time() - t0
                    rate = i / dt if dt > 0 else 0
                    print(f"  [>] {i}/{count} | {rate:.1f} pts/sec | OK:{ok} NA:{na} ERR:{errors} | KaV/L={res}")
            
            dur = time.time() - t0
            rate = count / dur if dur > 0 else 0
            print(f"\n[*] ====================================================")
            print(f"[*] HARVEST COMPLETE")
            print(f"[*] Points: {count} | Rate: {rate:.1f} pts/sec")
            print(f"[*] Success: {ok} | Failed: {na} | Errors: {errors}")
            print(f"[*] Duration: {dur:.2f}s")
            print(f"[*] CSV: {filename}")
            print(f"[*] ====================================================")


if __name__ == "__main__":
    bot = MerkelSiphon(DEFAULT_EXE)
    if bot.launch(visible=True):
        try: bot.run_sweep(1000, DEFAULT_CSV)
        finally: bot.kill()
    else: print("[!] FAILED INIT.")
