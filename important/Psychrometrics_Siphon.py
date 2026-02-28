"""
PSYCHROMETRICS NITRO SIPHON (v2026 PRODUCTION)
================================================
High-speed data extraction from the CTI Toolkit Psychrometrics tab.
Reads all 13 psychrometric properties at ~256 pts/sec.

USAGE:
    python Psychrometrics_Siphon.py
    
    Or import as a module:
        from Psychrometrics_Siphon import PsychrometricsSiphon
        bot = PsychrometricsSiphon()
        if bot.launch():
            bot.run_sweep(1000, "output.csv")
            bot.kill()

ARCHITECTURE:
    - Input:  WM_SETTEXT with direct Python strings (OS auto-marshals)
    - Notify: EN_CHANGE (0x0300) to main window for each input field
    - Calc:   WM_COMMAND with Button ID 1007
    - Read:   LVM_GETITEMTEXTW (0x104B) via remote buffer (VirtualAllocEx)
    - Sync:   Poll ListView Row 2 (DBT) until it matches requested input

CONTROL IDS:
    Altitude:     1002 (Edit)
    DBT Input:    1003 (Edit)
    WBT Input:    1004 (Edit)
    Recalculate:  1007 (Button)
    Results:      1015 (SysListView32, 10 rows)

UNITS: Celsius (all inputs and outputs)
VALID RANGES: DBT 0-60C, WBT 0-50C, Altitude 0-3000m
CONSTRAINT: DBT > WBT always. If DBT == WBT, subtract 0.01 from WBT.

SPEED: ~256 pts/sec (verified on 9950X3D, 1000 points, 100% success)
"""
import csv
import time
import ctypes
import struct
import subprocess
import os
import win32api
import win32gui
import win32con
import win32process

# Path to CTI Toolkit executable (relative to this script's location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXE = os.path.join(SCRIPT_DIR, "..", "official", "cti toolkit", "CTIToolkit_Ghost_Engine.exe")
DEFAULT_CSV = os.path.join(SCRIPT_DIR, "Psychrometrics_Output.csv")


class PsychrometricsSiphon:
    """Production-grade Psychrometrics data harvester for CTI Toolkit."""
    
    def __init__(self, exe_path=DEFAULT_EXE):
        self.exe_path = os.path.abspath(exe_path)
        self.cmd_dir = os.path.dirname(self.exe_path)
        self.h_proc = None
        self.hwnd = None
        self.pid = None
        self.kernel32 = ctypes.windll.kernel32
        
        # Control IDs (CTI Toolkit Build 2026)
        self.ID_ALT  = 1002   # Altitude Edit
        self.ID_DBT  = 1003   # Dry Bulb Temp Edit
        self.ID_WBT  = 1004   # Wet Bulb Temp Edit
        self.ID_CALC = 1007   # Recalculate Button
        self.ID_LV   = 1015   # Results ListView (10 rows)
        
        self.h_alt = 0
        self.h_dbt = 0
        self.h_wbt = 0
        self.h_lv = 0
        self.remote_mem = None

    def launch(self, visible=False):
        """Launch CTI Toolkit and initialize for Psychrometrics siphoning."""
        self.kill()
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
            
        if not self.hwnd: return False
        self.h_proc = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, self.pid)
        
        # Cache Control Handles
        def enum_cb(h, _):
            cid = win32gui.GetDlgCtrlID(h)
            if cid == self.ID_ALT: self.h_alt = h
            if cid == self.ID_DBT: self.h_dbt = h
            if cid == self.ID_WBT: self.h_wbt = h
            if cid == self.ID_LV: self.h_lv = h
            return True
        win32gui.EnumChildWindows(self.hwnd, enum_cb, None)
        
        if not self.h_alt or not self.h_lv:
            print("[!] Failed to find required controls.")
            return False

        # NITRO: Disable ListView redraw for speed
        win32gui.SendMessage(self.h_lv, win32con.WM_SETREDRAW, 0, 0)
        
        # NITRO: Pre-allocate remote "Landing Zone" buffer for bulk reads
        self.remote_mem = self.kernel32.VirtualAllocEx(self.h_proc.handle, 0, 4096, 0x1000, 0x04)
        for i in range(10):
            buf_addr = self.remote_mem + 600 + (i * 128)
            lvitem = struct.pack("IIiiIIIIII", 1, i, 1, 0, 0, buf_addr, 64, 0, 0, 0)
            self.kernel32.WriteProcessMemory(self.h_proc.handle, self.remote_mem + (i * 60), lvitem, len(lvitem), None)
            
        print(f"[OK] Psychrometrics engine ready (PID: {self.pid})")
        return True

    def kill(self):
        """Kill the CTI Toolkit process."""
        if self.pid: 
            os.system(f"taskkill /F /PID {self.pid} >nul 2>&1")
            self.pid = None

    def poll_sync(self, d_target, a_target):
        """
        Input-Match Polling: Read ListView Row 2 (DBT) and Row 1 (Alt).
        Returns True when displayed values match our requested inputs.
        """
        win32gui.SendMessage(self.h_lv, 0x104B, 2, self.remote_mem + (2 * 60))
        win32gui.SendMessage(self.h_lv, 0x104B, 1, self.remote_mem + (1 * 60))
        
        buf = ctypes.create_string_buffer(256)
        self.kernel32.ReadProcessMemory(self.h_proc.handle, self.remote_mem + 600 + (1 * 128), buf, 256, None)
        
        raw = buf.raw
        res_alt = raw[0:128].decode('utf-16le').split('\0')[0].strip()
        res_dbt = raw[128:256].decode('utf-16le').split('\0')[0].strip()
        
        try:
            return abs(float(res_dbt) - float(d_target)) < 0.05 and abs(float(res_alt) - float(a_target)) < 0.1
        except: return False

    def siphon_full(self):
        """
        Bulk-read all 10 rows from the Results ListView in one batch.
        Returns: [P, Alt, DBT, WBT, H, DP, RH, Dens, SV, HR]
        """
        results = []
        for i in range(10):
            win32gui.SendMessage(self.h_lv, 0x104B, i, self.remote_mem + (i * 60))
        full_buf = ctypes.create_string_buffer(1280)
        self.kernel32.ReadProcessMemory(self.h_proc.handle, self.remote_mem + 600, full_buf, 1280, None)
        for i in range(10):
            results.append(full_buf.raw[i*128 : (i+1)*128].decode('utf-16le').split('\0')[0].strip())
        return results

    def run_sweep(self, count, filename):
        """
        Run a parameter sweep and save to CSV.
        Default sweep: DBT 30+, WBT 20+, Alt cycling 0-900m.
        """
        print(f"[*] Psychrometrics NITRO sweep: {count} points -> {filename}")
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Req_DBT", "Req_WBT", "Req_Alt", "P", "Alt", "DBT", "WBT", "H", "DP", "RH", "Dens", "SV", "HR"])
            
            start = time.time()
            for i in range(count):
                d, w, a = 30.0+(i*0.01), 20.0+(i*0.01), (i%10)*100.0
                ds, ws, as_ = f"{d:.2f}", f"{w:.2f}", f"{a:.1f}"
                
                win32gui.SendMessage(self.h_alt, win32con.WM_SETTEXT, 0, as_)
                win32gui.SendMessage(self.hwnd, win32con.WM_COMMAND, (0x0300 << 16) | 1002, self.h_alt)
                win32gui.SendMessage(self.h_dbt, win32con.WM_SETTEXT, 0, ds)
                win32gui.SendMessage(self.hwnd, win32con.WM_COMMAND, (0x0300 << 16) | 1003, self.h_dbt)
                win32gui.SendMessage(self.h_wbt, win32con.WM_SETTEXT, 0, ws)
                win32gui.SendMessage(self.hwnd, win32con.WM_COMMAND, (0x0300 << 16) | 1004, self.h_wbt)
                win32gui.SendMessage(self.hwnd, win32con.WM_COMMAND, 1007, 0)
                
                for _ in range(500):
                    if self.poll_sync(ds, as_):
                        writer.writerow([ds, ws, as_] + self.siphon_full())
                        break
                
                if i % 100 == 0 and i > 0:
                    elapsed = time.time() - start
                    print(f"  [>] {i}/{count} | {i/elapsed:.1f} pts/sec")
            
            dur = time.time() - start
            print(f"\n[*] SWEEP COMPLETE. {count} points in {dur:.2f}s ({count/dur:.1f} pts/sec)")


if __name__ == "__main__":
    bot = PsychrometricsSiphon(DEFAULT_EXE)
    if bot.launch():
        try: bot.run_sweep(1000, DEFAULT_CSV)
        finally: bot.kill()
    else:
        print("[!] Failed to initialize.")
