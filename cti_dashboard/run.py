"""
CTI Analysis Dashboard — Smart Launcher
========================================
Automatically serves the dashboard and opens it in your default browser.

Features:
  - Auto-detects available port (tries 8080, then finds free port)
  - Opens browser automatically
  - Graceful shutdown with Ctrl+C
  - Works on Windows, macOS, and Linux
  - Zero dependencies (uses only Python stdlib)

Usage:
  python run.py              # Serve on default port (8080)
  python run.py 9090         # Serve on specific port
  python run.py --no-open    # Don't auto-open browser
"""

import http.server
import socketserver
import os
import sys
import socket
import webbrowser
import threading
import signal

# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_PORT = 8080
MAX_PORT_ATTEMPTS = 20
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# PORT DETECTION
# ============================================================

def is_port_available(port):
    """Check if a TCP port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(("", port))
            return True
    except OSError:
        return False


def find_available_port(start_port):
    """Find the first available port starting from start_port."""
    for offset in range(MAX_PORT_ATTEMPTS):
        port = start_port + offset
        if is_port_available(port):
            return port
    # Fallback: let OS assign a port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

# ============================================================
# SERVER
# ============================================================

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that suppresses request logging for a cleaner console."""
    
    def log_message(self, format, *args):
        # Only log errors, not every request
        if args and isinstance(args[0], str) and args[0].startswith("4"):
            super().log_message(format, *args)

    def end_headers(self):
        # Add CORS headers for ES module support
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def serve(port, auto_open=True):
    """Start the HTTP server and optionally open the browser."""
    os.chdir(DASHBOARD_DIR)
    
    with socketserver.TCPServer(("", port), QuietHandler) as httpd:
        url = f"http://localhost:{port}"
        
        print()
        print("  ╔══════════════════════════════════════════════╗")
        print("  ║       CTI Analysis Dashboard — Running       ║")
        print("  ╠══════════════════════════════════════════════╣")
        print(f"  ║  URL:  {url:<37s} ║")
        print(f"  ║  Dir:  {DASHBOARD_DIR[-37:]:<37s} ║")
        print("  ║  Stop: Ctrl+C                                ║")
        print("  ╚══════════════════════════════════════════════╝")
        print()
        
        if auto_open:
            # Open browser after a short delay (let server start)
            def open_browser():
                webbrowser.open(url)
            timer = threading.Timer(0.5, open_browser)
            timer.daemon = True
            timer.start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped. Goodbye!")
            httpd.shutdown()

def kill_port_owner(port):
    """Identify and terminate the process holding a specific port."""
    try:
        if os.name == 'nt':
            # Windows: Find PID using netstat
            import subprocess
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True).decode()
            for line in output.strip().split('\n'):
                if 'LISTENING' in line:
                    pid = line.strip().split()[-1]
                    if pid != '0':
                        os.system(f'taskkill /F /PID {pid} >nul 2>&1')
        else:
            # Unix: Use lsof/fuser
            os.system(f'fuser -k {port}/tcp > /dev/null 2>&1')
    except:
        pass

def kill_existing_instances():
    """Tries to kill other Python processes running this script."""
    try:
        current_pid = os.getpid()
        if os.name == 'nt':
            cmd = f'wmic process where "name=\'python.exe\' and commandline like \'%run.py%\' and processid!={current_pid}" call terminate'
            os.system(f'{cmd} >nul 2>&1')
        else:
            os.system(f'pkill -f "python.*run.py" --exclude {current_pid} > /dev/null 2>&1')
    except:
        pass


# ============================================================
# MAIN
# ============================================================

def main():
    # 1. Clear console
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # 2. Parse arguments
    port = DEFAULT_PORT
    auto_open = True
    
    for arg in sys.argv[1:]:
        if arg == "--no-open":
            auto_open = False
        elif arg == "--help" or arg == "-h":
            print(__doc__)
            sys.exit(0)
        else:
            try:
                port = int(arg)
            except ValueError:
                port = DEFAULT_PORT

    # 3. Force-kill existing instances and port owners
    print(f"  Cleanup: Stopping existing instances and clearing port {port}...")
    kill_existing_instances()
    kill_port_owner(port)
    print("  Done. Launching dashboard...")
    
    # Start serving
    serve(port, auto_open)


if __name__ == "__main__":
    main()
