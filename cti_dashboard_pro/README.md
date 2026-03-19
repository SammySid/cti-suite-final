# CTI Analysis Dashboard (PRO Full-Stack Version)

The `cti_dashboard_pro` is the **Full-Stack, Python-backed** evolution of the CTI Analysis suite. 

While the standard `cti_dashboard` operates entirely in the browser using static HTML/JS (requiring ZERO dependencies beyond a basic HTTP server), this **PRO** version integrates a robust Python backend to support **Heavy Data Filtering and Professional Excel Generation**.

### Key Differences & Additions

- **Secure Python Backend Engine**: Employs an active high-performance `main.py` (FastAPI) daemon running on port 8000. It dynamically intercepts `/api/calculate`, `/api/export-excel` and `/api/filter-excel` routes, completely hiding your Trade Secrets and proprietary math from the frontend web browser.
- **Excel Filter System**: Capable of processing massive multiphase `.xlsx` datasets. The Python backend extracts sensor columns, interpolates rows by matching timestamps, styles the output using XlsxWriter, and serves the file securely via JSON payloads and Multipart.
- **Performance Report Generator**: Intercepts calculations processed asynchronously via your web workers (the 320 probe Tchebeycheff algorithms) and builds automated professional thermal reports directly to `.xlsx`.

### Requirements

Unlike the static version, this requires Python (>= 3.9) and several Data Science libraries natively installed:
```bash
pip install pandas openpyxl xlsxwriter python-dateutil fastapi uvicorn pydantic python-multipart
```

### Starting the Environment
If you are running this locally:
- Simply run `start_dashboard.bat`. It will verify dependencies and immediately launch the unified UI in your browser.

If you are running this on a VPS:
- Refer to the `VPS_HOSTING_GUIDE.md` located in the root directory for instructions on deploying Python Systemd proxies.

---

### Engineering & Logic Guide
For a deep dive into the "First Principles" of cooling towers, Merkel's Method, and the physics behind the dashboard, see:
- [COOLING_TOWER_FUNDAMENTALS.md](docs/COOLING_TOWER_FUNDAMENTALS.md)
