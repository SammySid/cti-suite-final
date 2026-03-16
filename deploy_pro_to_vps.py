"""
deploy_pro_to_vps.py
====================
Deploys ONLY the cti_dashboard_pro/ sub-folder to the VPS via SFTP.

Credentials are read from deploy_config.json (which is git-ignored —
never commit that file). By default, this will append '_pro' to your 
remote_path from the config so it doesn't overwrite your static dashboard.

Usage:
    python deploy_pro_to_vps.py

Requirements:
    pip install paramiko
"""

import os
import json
import paramiko

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_config.json")

# Only this sub-folder is uploaded to the VPS
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cti_dashboard_pro")

# Files / dirs inside cti_dashboard_pro that should NOT be uploaded
EXCLUDE_DIRS  = {".git", "__pycache__", "docs", "reports"}   # docs = internal reference only
EXCLUDE_FILES = {
    ".DS_Store", "Thumbs.db", "desktop.ini",
    "*.log", "*.tmp", "*.xlsx"
}
EXCLUDE_EXTS  = {".log", ".tmp", ".pyc", ".pyo"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"deploy_config.json not found at {CONFIG_FILE}\n"
            "Create it with: {{\"host\":\"…\",\"user\":\"…\",\"password\":\"…\",\"remote_path\":\"…\"}}"
        )
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    for key in ("host", "user", "password", "remote_path"):
        if key not in cfg:
            raise KeyError(f"deploy_config.json is missing key: {key!r}")
    return cfg


def should_exclude(name: str, is_dir: bool) -> bool:
    if is_dir:
        return name in EXCLUDE_DIRS
    if name in EXCLUDE_FILES:
        return True
    _, ext = os.path.splitext(name)
    return ext.lower() in EXCLUDE_EXTS


def sftp_mkdir_p(sftp, remote_dir: str):
    """Recursively create remote directory if it doesn't exist."""
    parts = remote_dir.replace("\\", "/").split("/")
    path = ""
    for part in parts:
        if not part:
            path = "/"
            continue
        path = f"{path}/{part}" if path != "/" else f"/{part}"
        try:
            sftp.stat(path)
        except FileNotFoundError:
            sftp.mkdir(path)


# ── Main ──────────────────────────────────────────────────────────────────────

def deploy():
    cfg = load_config()
    host        = cfg["host"]
    user        = cfg["user"]
    password    = cfg["password"]
    # Append _pro to avoid overwriting the static dashboard unless modified by the user
    remote_root = cfg["remote_path"].rstrip("/") + "_pro"

    if not os.path.isdir(DASHBOARD_DIR):
        raise FileNotFoundError(f"Pro Dashboard source not found: {DASHBOARD_DIR}")

    print(f"\n🚀  CTI Dashboard PRO — deploying to {user}@{host}:{remote_root}")
    print(f"    Source : {DASHBOARD_DIR}")
    print(f"    Skipping dirs : {EXCLUDE_DIRS}")
    print(f"    Skipping exts : {EXCLUDE_EXTS}\n")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    uploaded = 0
    skipped  = 0
    errors   = 0

    try:
        client.connect(host, username=user, password=password, timeout=30)
        sftp = client.open_sftp()

        # Ensure remote root exists
        sftp_mkdir_p(sftp, remote_root)

        for root, dirs, files in os.walk(DASHBOARD_DIR):
            # Filter out excluded dirs in-place so os.walk won't descend into them
            dirs[:] = [d for d in dirs if not should_exclude(d, is_dir=True)]

            rel = os.path.relpath(root, DASHBOARD_DIR)
            remote_dir = remote_root if rel == "." else f"{remote_root}/{rel.replace(chr(92), '/')}"

            # Create remote sub-directory
            if rel != ".":
                sftp_mkdir_p(sftp, remote_dir)

            for filename in files:
                if should_exclude(filename, is_dir=False):
                    skipped += 1
                    continue

                local_file  = os.path.join(root, filename)
                remote_file = f"{remote_dir}/{filename}"

                try:
                    size_kb = os.path.getsize(local_file) / 1024
                    display = f"{rel}/{filename}" if rel != "." else filename
                    print(f"  📤  {display:<55}  {size_kb:>7.1f} KB")
                    sftp.put(local_file, remote_file)
                    uploaded += 1
                except Exception as e:
                    print(f"  ❌  FAILED {filename}: {e}")
                    errors += 1

        sftp.close()

        print("\n🔄  Restarting the backend application service on the VPS...")
        stdin, stdout, stderr = client.exec_command(f"echo '{password}' | sudo -S systemctl restart cti-dashboard")
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("    ✅ Service restarted successfully!")
        else:
            err_msg = stderr.read().decode().strip()
            print(f"    ⚠️ Could not automatically restart service: {err_msg}")

        print(f"\n{'='*60}")
        if errors == 0:
            print("✅  Deployment complete!")
        else:
            print(f"⚠️   Deployment finished with {errors} error(s).")
        print(f"    Uploaded : {uploaded} file(s)")
        print(f"    Skipped  : {skipped} file(s)")
        print(f"    Host     : http://{host}")
        print(f"{'='*60}\n")
        print("💡 NOTE: You must establish the Python backend environment on the VPS to serve the PRO dashboard.")
        print("Please read VPS_HOSTING_GUIDE.md for setting up Nginx and Systemd.")

    except Exception as e:
        print(f"\n❌  Deployment FAILED: {e}\n")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    deploy()
