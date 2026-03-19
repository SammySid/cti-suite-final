# VPS Hosting Guide: Full-Stack Dashboard (PRO)

Since the new "Pro" dashboard features a Python backend for Excel report generation and bulk data filtering, hosting it on your VPS requires slightly different steps than simply serving static files.

By following this guide, you will deploy the dashboard to your VPS, set up the Python backend to run as a 24/7 background service, and configure Nginx (or your chosen web server) as a reverse proxy.

---

## 1. Deploy the Files

Run your new deployment script locally to push the `cti_dashboard_pro` folder securely to your VPS:

```bash
python deploy_pro_to_vps.py
```

*Note: The script automatically appends `_pro` to your `remote_path` in `deploy_config.json` to prevent overwriting your old, static dashboard.*

---

## 2. Install VPS Dependencies

SSH into your VPS. Once logged in, navigate to the pro dashboard directory (e.g., `/var/www/html/cti_dashboard_pro`):

```bash
cd /path/to/your/cti_dashboard_pro
```

You need to ensure Python 3 is installed, and then install the required libraries for the backend (Pandas, XlsxWriter, OpenPyxl):

```bash
# Update package list (Ubuntu/Debian)
sudo apt update
sudo apt install python3 python3-pip -y

# Install exactly what the backend needs
pip3 install pandas xlsxwriter openpyxl python-dateutil fastapi uvicorn pydantic python-multipart
```

---

## 3. Run the Backend as a Background Service (Systemd)

You want your Python FastAPI backend (`app/backend/main.py`) to run continuously, restart on crashes, and launch automatically if the VPS reboots.

**Create a new service file:**
```bash
sudo nano /etc/systemd/system/cti-dashboard.service
```

**Paste the following configuration (adjust the paths to match your exact VPS paths):**
```ini
[Unit]
Description=CTI Dashboard Pro Backend Service
After=network.target

[Service]
User=root
WorkingDirectory=/path/to/your/cti_dashboard_pro/app/backend
# Point to your python3 executable
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable cti-dashboard
sudo systemctl start cti-dashboard
sudo systemctl status cti-dashboard
```
*If everything is correct, the status will say "active (running)".* 
*To check logs later: `sudo journalctl -u cti-dashboard -f`*

---

## 4. Configure Your Web Server (Reverse Proxy)

The Python backend is now running locally on port **8000** of your VPS. You need to tell your web server (like Nginx) to forward public internet traffic to this port.

**If you are using Nginx**, edit your site configuration:
```bash
sudo nano /etc/nginx/sites-available/default
```

Modify the config to proxy requests to port 8000. It should look something like this:

```nginx
server {
    listen 80;
    server_name your_domain_or_ip.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Important for large file uploads (Excel Filtering tool)
        client_max_body_size 100M; 
    }
}
```

**Test and restart Nginx:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 5. Verify the Installation

Navigate to your VPS IP or domain in a web browser. 
1. The dashboard UI should load successfully.
2. Go to the "Excel Data Filter" tab and upload some files to verify the backend Python engine handles multipart uploads smoothly.
3. Test the "Generate Report" PDF/Excel pipelines to confirm that Pandas and XlsxWriter are functioning flawlessly.
