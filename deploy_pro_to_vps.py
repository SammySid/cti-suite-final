"""
deploy_pro_to_vps.py
====================
UPDATED 2026-03-19 — GitHub Auto-Sync Architecture

The VPS now pulls directly from GitHub (SammySid/cti-suite-final) every 5 minutes
via a systemd timer running /home/ubuntu/cooling-tower_pro/auto_sync.sh.

This script: 
  1. Pushes any uncommitted local changes to GitHub
  2. SSH's into the VPS and immediately triggers the auto_sync.sh
     (so you don't have to wait up to 5 minutes for the timer to fire)

Usage:
    python deploy_pro_to_vps.py

Requirements:
    pip install paramiko
    git must be installed and repo must be configured with push access
"""

import os
import subprocess
import paramiko

# ── Config ────────────────────────────────────────────────────────────────────

VPS_HOST     = "130.162.191.58"
VPS_USER     = "ubuntu"
VPS_PASSWORD = "Stallion316##"
VPS_SYNC_CMD = "/home/ubuntu/cooling-tower_pro/auto_sync.sh"
BRANCH       = "main"

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_local(cmd: list[str], cwd: str = REPO_ROOT) -> str:
    """Run a local shell command and return stdout. Raises on failure."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_push() -> bool:
    """
    Stage, commit (if anything changed), and push to GitHub.
    Returns True if a push was made, False if already up to date.
    """
    print("\n📦  Checking git status...")
    status = run_local(["git", "status", "--porcelain"])

    if status:
        print(f"    {len(status.splitlines())} changed file(s) — committing...")
        run_local(["git", "add", "-A"])
        run_local(["git", "commit", "-m", "chore: auto-deploy commit from deploy_pro_to_vps.py"])
        print("    ✅ Committed.")
    else:
        print("    Working tree clean — nothing to commit.")

    # Check if we're ahead of remote
    ahead = run_local(["git", "rev-list", f"origin/{BRANCH}..HEAD", "--count"])
    if ahead == "0":
        print("    Already up to date with remote — no push needed.")
        return False

    print(f"    ⬆️  Pushing {ahead} commit(s) to GitHub ({BRANCH})...")
    run_local(["git", "push", "origin", BRANCH])
    sha = run_local(["git", "rev-parse", "--short", "HEAD"])
    print(f"    ✅ Pushed. Latest SHA: {sha}")
    return True


def trigger_vps_sync():
    """SSH into VPS and run the auto_sync.sh immediately."""
    print(f"\n🔌  Connecting to VPS ({VPS_HOST})...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

    print(f"🚀  Triggering sync on VPS: {VPS_SYNC_CMD}\n")
    print("─" * 60)

    # Stream output line-by-line
    stdin, stdout, stderr = client.exec_command(
        VPS_SYNC_CMD, get_pty=True, timeout=300
    )
    for line in stdout:
        print(f"  VPS | {line.rstrip()}")

    exit_status = stdout.channel.recv_exit_status()
    client.close()

    print("─" * 60)
    if exit_status == 0:
        print("\n✅  VPS sync complete!")
    else:
        err = stderr.read().decode().strip()
        print(f"\n⚠️  Sync exited with code {exit_status}. stderr: {err}")


# ── Main ──────────────────────────────────────────────────────────────────────

def deploy():
    print("\n" + "=" * 60)
    print("  CTI Dashboard PRO — Deploy to VPS")
    print("  Mode: GitHub auto-sync (push → trigger)")
    print("=" * 60)

    # Step 1: Push to GitHub
    try:
        git_push()
    except RuntimeError as e:
        print(f"\n⚠️  Git error (continuing anyway): {e}")

    # Step 2: Trigger immediate sync on VPS
    try:
        trigger_vps_sync()
    except Exception as e:
        print(f"\n❌  VPS connection failed: {e}")
        print("\n💡  The VPS timer will still auto-sync within 5 minutes.")
        print(f"    Monitor: ssh {VPS_USER}@{VPS_HOST} 'tail -f /var/log/cti_autosync.log'")
        return

    print(f"\n🌐  Live at: https://ct.ftp.sh")
    print(f"    Logs:    ssh {VPS_USER}@{VPS_HOST} 'docker logs cti-dashboard-pro --tail 30'")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    deploy()
