# VPS Hosting Guide: CTI Dashboard Pro

> **Last updated:** 2026-04-18 | **Live:** `https://ct.ftp.sh`

The `cti_dashboard_pro` is fully containerised and deployed on the **Oracle UK VPS** via Docker with automatic GitHub sync.

---

## 🌐 Live Production

**`https://ct.ftp.sh`** — Protected by Authelia SSO (login required)

| Detail | Value |
|--------|-------|
| **VPS** | Oracle Cloud UK — `130.162.191.58` |
| **SSH** | `ssh ubuntu@130.162.191.58` |
| **Container** | `cti-dashboard-pro` |
| **Network** | `options-network` (shared Docker bridge) |
| **Proxy** | `trading-nginx` → ports 80/443 |
| **Auth** | `authelia` container (SSO gate) |
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

## 🔄 Deploying Updates

### Method 1: `deploy_pro_to_vps.py` (Recommended — Immediate ✅)

```bash
python deploy_pro_to_vps.py
```

This script:
1. Commits and pushes all local changes to `master` on GitHub
2. SSHs into the VPS via `paramiko`
3. Triggers `auto_sync.sh` on-demand (no waiting for the 5-minute timer)
4. Tails the Docker rebuild log until completion

### Method 2: Push to GitHub (Auto-sync — up to 5 min delay)

Push to `master` — a **systemd timer** on the VPS fires `auto_sync.sh` every 5 minutes:

1. Sparse-clones only `cti_dashboard_pro/` from GitHub (`master` branch)
2. Compares remote SHA to `.last_deployed_sha` — skips if unchanged
3. rsyncs new code into `/home/ubuntu/cooling-tower_pro/`  
   _(excludes `__pycache__`, `.pyc`, `docker-compose.yml`, `requirements.txt`, `auto_sync.sh`, `.last_deployed_sha`)_  
   _(note: `Dockerfile` is now synced — was previously excluded, causing build failures)_
4. Rebuilds Docker image and restarts the container
5. Logs everything to `/var/log/cti_autosync.log`

```bash
# Check auto-sync status on VPS
sudo systemctl status cti-autosync.timer
sudo tail -f /var/log/cti_autosync.log
```

### Method 3: Manual Deploy (Emergency)

```bash
ssh ubuntu@130.162.191.58
cd /home/ubuntu/cooling-tower_pro
/home/ubuntu/cooling-tower_pro/auto_sync.sh   # pull + rebuild

# Or force rebuild without pulling
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
│   │   ├── backend/            ← FastAPI Python backend (main.py, report_service.py, etc.)
│   │   └── web/                ← Static frontend assets (index.html, js/, css/)
│   ├── Dockerfile              ← python:3.11-slim + cairo build deps
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── auto_sync.sh            ← GitHub auto-sync (runs every 5 min via systemd)
│   └── .last_deployed_sha      ← Tracks last deployed SHA
├── nginx-trading.conf          ← Nginx config (mounted into trading-nginx)
├── nginx-compose.yml           ← Docker Compose for nginx + authelia + cpr
├── certs/                      ← Self-signed certs (trading-nginx fallback)
└── authelia/config/            ← Authelia SSO configuration
```

---

## 🐳 Dockerfile

The container uses `python:3.11-slim` with full build toolchain for `pycairo` (required by `xhtml2pdf`):

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    gcc g++ build-essential \
    libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev \
    libffi-dev libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*
```

> ⚠️ If you ever see a `502 Bad Gateway`, check Docker logs first:  
> `docker logs cti-dashboard-pro --tail 30`  
> The most common cause is `pycairo` failing to compile (check if `libcairo2-dev` is missing from the image build).

---

## 🔧 Key Management Commands

```bash
# All running containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# CTI Dashboard logs
docker logs cti-dashboard-pro --tail 50 -f

# Rebuild without auto-sync
cd /home/ubuntu/cooling-tower_pro
docker compose down && docker compose up -d --build

# Restart nginx (if config changed)
cd /home/ubuntu && docker compose -f nginx-compose.yml restart nginx

# Nginx logs
docker logs trading-nginx --tail 50 -f

# Authelia logs
docker logs authelia --tail 50 -f

# Reload nginx config without downtime
docker exec trading-nginx nginx -s reload

# Test nginx config syntax
docker exec trading-nginx nginx -t
```

---

## 🩹 Known Issues — All Fixed

### Fixed 2026-04-18 — `502 Bad Gateway` after Dashboard Update
**Symptom:** `ct.ftp.sh` showing `502 Bad Gateway` after a `cti_dashboard_pro` code push.

**Root cause:** The `Dockerfile` was outdated on the VPS (using `python:3.9-slim`, missing `libcairo2-dev` and other build tools). `pycairo` (required by `xhtml2pdf`) failed to compile during Docker image rebuild. Additionally, `auto_sync.sh` had `--exclude="Dockerfile"` in its rsync command, preventing the fixed Dockerfile from reaching the VPS.

**Fix applied:**
1. Updated `Dockerfile`: `FROM python:3.9-slim` → `FROM python:3.11-slim` + added all required build-time dependencies
2. Removed `--exclude="Dockerfile"` from `auto_sync.sh` rsync command
3. Manually ran `docker compose down && docker compose up -d --build` on VPS to apply immediately

---

### Fixed 2026-03-20 — `auto_sync.sh` Branch Mismatch
**Symptom:** VPS auto-sync failing every 5 minutes with `fatal: couldn't find remote ref main`.

**Root cause:** `auto_sync.sh` had `BRANCH="main"` but the GitHub repo uses `master`.

**Fix:** Updated `BRANCH="master"` in `auto_sync.sh` on VPS and in `deploy_pro_to_vps.py` locally.

---

### Fixed 2026-03-19 — `trading-nginx` Crash Loop
**Symptom:** `ct.ftp.sh` returning "Unable to connect" — `trading-nginx` stuck in crash loop.

**Root cause:** Stray `}` brace in `/home/ubuntu/nginx-trading.conf` — nginx failed its config syntax check on startup.

**Fix:** Rewrote `nginx-trading.conf` with corrected syntax and modernised `http2 on` directive.

---

## 💾 Automated Backups

| Detail | Value |
|--------|-------|
| **Service** | `backup-trading-vps.timer` (systemd) |
| **Schedule** | Daily at ~07:30 IST |
| **Destination** | `gdrive-vps:Vps Backup/backup images/uk-trading-vps/` |
| **Retention** | 5 most recent archives |
| **Log** | `/var/log/backup-trading-vps.log` |

```bash
sudo systemctl status backup-trading-vps.timer
sudo tail -50 /var/log/backup-trading-vps.log
```

---

## ✅ Verify Installation

1. Go to `https://ct.ftp.sh` → should redirect to Authelia login
2. After login, CTI Dashboard Pro loads
3. Test **Thermal Analysis** tab — curves should render
4. Test **ATC-105 Report Builder** tab — Live Preview should update on input
5. Test **Excel Data Filter** — upload + filter should produce a download
