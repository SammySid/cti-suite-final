# VPS Hosting Guide: CTI Dashboard Pro

The `cti_dashboard_pro` is fully containerised and deployed on the **UK Oracle VPS** (`ct.ftp.sh`) via Docker. This guide covers the live architecture, how to deploy updates, and the automated sync system.

> **Last updated:** 2026-03-20

---

## 🌐 Live Production URL

**`https://ct.ftp.sh`** — Protected by Authelia SSO (login required)

| Detail | Value |
|--------|-------|
| **VPS** | Oracle Cloud UK — `130.162.191.58` |
| **SSH** | `ssh ubuntu@130.162.191.58` (password: on file) |
| **Container** | `cti-dashboard-pro` |
| **Network** | `options-network` (shared Docker bridge) |
| **Proxy** | `trading-nginx` container → ports 80 / 443 |
| **Auth** | `authelia` container (SSO guard) |
| **SSL** | Let's Encrypt — `/etc/letsencrypt/live/ct.ftp.sh/` |

---

## 🏗️ Architecture

```
Internet (HTTPS 443)
        ↓
trading-nginx  (Docker container — nginx:alpine)
        ├─ ct.ftp.sh  → authelia:9091 (SSO gate)
        │                    ↓ (on auth OK)
        │              cti-dashboard-pro:8000  (FastAPI)
        ├─ shiva.ftp.sh  → cpr-options-dashboard:5000
        ├─ nol.ftp.sh    → cpr-options-dashboard:5000
        └─ options.ftp.sh→ cpr-options-dashboard:5000
```

All four containers (`trading-nginx`, `authelia`, `cpr-options-dashboard`, `cti-dashboard-pro`) share the `options-network` Docker bridge.

---

## 🔄 Deploying Updates — Two Methods

### Method 1: Push to GitHub (Recommended — Fully Automatic ✅)

Just **push your changes** to the `master` branch of `github.com/SammySid/cti-suite-final`.

A **systemd timer** on the VPS runs `/home/ubuntu/cooling-tower_pro/auto_sync.sh` every **5 minutes**. It:

1. Sparse-clones only `cti_dashboard_pro/` from GitHub (`master` branch)
2. Compares the remote SHA to the last deployed SHA (`.last_deployed_sha`)
3. If changed — rsyncs new code into `/home/ubuntu/cooling-tower_pro/` (excluding `__pycache__`, `.pyc`, `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `auto_sync.sh`, `.last_deployed_sha`)
4. Rebuilds the Docker image and restarts the container
5. Logs everything to `/var/log/cti_autosync.log`

To deploy immediately without waiting for the 5-minute timer, run `deploy_pro_to_vps.py`:
```bash
python deploy_pro_to_vps.py
```
This commits + pushes to GitHub, then SSH's into the VPS and triggers `auto_sync.sh` on-demand.

**Check auto-sync status on VPS:**
```bash
sudo systemctl status cti-autosync.timer
sudo tail -f /var/log/cti_autosync.log
```

---

### Method 2: Manual Deploy (Emergency / Immediate)

SSH in and rebuild manually:

```bash
ssh ubuntu@130.162.191.58

# Navigate to app directory
cd /home/ubuntu/cooling-tower_pro

# Pull latest from GitHub manually
/home/ubuntu/cooling-tower_pro/auto_sync.sh

# Or force a full rebuild without pulling
docker compose down
docker compose up -d --build

# Check status
docker ps
docker logs cti-dashboard-pro --tail 50 -f
```

---

## 📁 VPS Directory Layout

```
/home/ubuntu/
├── cooling-tower_pro/          ← CTI Dashboard Pro app root
│   ├── app/
│   │   ├── backend/            ← FastAPI Python backend (main.py)
│   │   └── web/                ← Static frontend assets
│   ├── Dockerfile
│   ├── docker-compose.yml      ← Connects to options-network (external)
│   ├── requirements.txt
│   ├── auto_sync.sh            ← GitHub auto-sync script (runs every 5 min)
│   └── .last_deployed_sha      ← Tracks last deployed GitHub commit SHA
├── nginx-trading.conf          ← Nginx config (mounted into trading-nginx)
├── nginx-compose.yml           ← Docker Compose for nginx + authelia + cpr
├── certs/                      ← Self-signed certs (trading-nginx fallback)
└── authelia/config/            ← Authelia SSO configuration
```

---

## 🔧 Key Management Commands

```bash
# Check all running containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Restart nginx (if config changed)
cd /home/ubuntu && docker compose -f nginx-compose.yml restart nginx

# View nginx logs
docker logs trading-nginx --tail 50 -f

# View CTI dashboard logs
docker logs cti-dashboard-pro --tail 50 -f

# View Authelia logs
docker logs authelia --tail 50 -f

# Reload nginx config without downtime
docker exec trading-nginx nginx -s reload

# Test nginx config syntax
docker exec trading-nginx nginx -t
```

---

## ⚠️ Known Issues — Fixed

### Fixed 2026-03-19
**Symptom:** `ct.ftp.sh` returning "Unable to connect" / `trading-nginx` stuck in crash loop.

**Root Cause:** A stray `}` brace in `/home/ubuntu/nginx-trading.conf` caused nginx to fail its config syntax check on startup, putting the container into a crash-restart loop.

**Fix Applied:** Rewrote `nginx-trading.conf` with corrected syntax and modernised `http2 on` directive.

---

### Fixed 2026-03-20 — Mobile Hamburger Menu / Input Focus Bug
**Symptom:** On mobile (`ct.ftp.sh`), opening the hamburger menu in the Thermal Analysis tab and tapping any input field caused the menu to immediately close before the input could receive focus.

**Root Cause:** The backdrop `<div>` covered the full viewport. Touch events on sidebar inputs bubbled up through the DOM to the backdrop's `click` listener, firing `closeIfOpen()` before focus landed on the input.

**Fix Applied — 3-layer approach:**
1. **Inputs moved inline (primary fix):** All operational inputs (WBT, CWT, HWT, L/G ratio, constants, chart scaling) are now rendered inline within the `thermalTabPanel` on mobile (`lg:hidden`). On desktop they remain in the sidebar. This matches the UX pattern of all other tabs and eliminates the bug entirely for operational use.
2. **`data-mobile-mirror` sync:** Mobile inputs use `data-mobile-mirror="<id>"` attributes (no duplicate IDs). `bind-events.js` wires bidirectional sync — changes to either set propagate to `ui.inputs` and keep both in sync.
3. **`stopPropagation` safety net:** `mobile-nav.js` adds `sidebar.addEventListener('click', e => e.stopPropagation())` so any remaining sidebar taps cannot bubble to the backdrop.

**Files changed:** `index.html`, `js/ui/bind-events.js`, `js/ui/mobile-nav.js`, `js/ui/tabs.js`, `js/ui/export.js`

---

### Fixed 2026-03-20 — auto_sync.sh branch mismatch
**Symptom:** VPS auto-sync failing every 5 minutes with `fatal: couldn't find remote ref main`.

**Root Cause:** `auto_sync.sh` had `BRANCH="main"` but the GitHub repo uses `master` as the default branch.

**Fix Applied:** Updated `BRANCH="master"` in `auto_sync.sh` on the VPS and in `deploy_pro_to_vps.py` locally. Also hardened rsync excludes to prevent `__pycache__`, `auto_sync.sh`, and `.last_deployed_sha` from being deleted during sync.

---

## 💾 Automated Backups

A daily backup to Google Drive runs automatically:

| Detail | Value |
|--------|-------|
| **Service** | `backup-trading-vps.timer` (systemd) |
| **Schedule** | Daily at ~07:30 IST |
| **Destination** | `gdrive-vps:Vps Backup/backup images/uk-trading-vps/` |
| **Retention** | 5 most recent archives kept |
| **Log** | `/var/log/backup-trading-vps.log` |

```bash
# Check backup timer
sudo systemctl status backup-trading-vps.timer

# View backup log
sudo tail -50 /var/log/backup-trading-vps.log
```

---

## 5. Verify the Installation

Navigate to `https://ct.ftp.sh` in a browser:
1. You should be redirected to the **Authelia login page**
2. After logging in, the CTI Dashboard Pro should load fully
3. Test the Excel Data Filter tab and Performance Prediction tab to confirm the FastAPI backend is healthy
