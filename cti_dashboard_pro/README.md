# CTI Analysis Dashboard (PRO Full-Stack Version)

The `cti_dashboard_pro` is the **Full-Stack, Python-backed** evolution of the CTI Analysis suite. 

While the standard `cti_dashboard` operates entirely in the browser using static HTML/JS (requiring ZERO dependencies beyond a basic HTTP server), this **PRO** version integrates a robust Python backend to support **Heavy Data Filtering and Professional Excel Generation**.

### Key Differences & Additions

- **Secure Python Backend Engine**: Employs an active high-performance `main.py` (FastAPI) daemon running on port 8000. It dynamically intercepts `/api/calculate`, `/api/export-excel` and `/api/filter-excel` routes, completely hiding your Trade Secrets and proprietary math from the frontend web browser.
- **Excel Filter System**: Capable of processing massive multiphase `.xlsx` datasets. The Python backend extracts sensor columns, interpolates rows by matching timestamps, styles the output using XlsxWriter, and serves the file securely via JSON payloads and Multipart.
- **Excel Report Generator**: Intercepts calculations processed asynchronously via your web workers (the 320 probe Tchebeycheff algorithms) and builds automated professional thermal reports directly to `.xlsx`.
- **ATC-105 Automated PDF Engine**: An advanced HTML-to-PDF compiler using `xhtml2pdf`, `Jinja2`, and `matplotlib`. Evaluates Pre and Post multi-state testing data and mathematically constructs 17-page industry-grade ATC-105 compliance reports with precise visual graphs.

### Requirements

Unlike the static version, this requires Python (>= 3.9) and several Data Science libraries natively installed:
```bash
pip install pandas openpyxl xlsxwriter python-dateutil fastapi uvicorn pydantic python-multipart jinja2 xhtml2pdf matplotlib
```

### Starting the Environment
If you are running this locally:
- Simply run `start_dashboard.bat`. It will verify dependencies and immediately launch the unified UI in your browser.

If you are running this on a VPS:
- The app is containerised with Docker. See [`VPS_HOSTING_GUIDE.md`](../VPS_HOSTING_GUIDE.md) for the full architecture and deployment guide.
- **Live URL:** `https://ct.ftp.sh` (Oracle UK VPS — protected by Authelia SSO)
- **Live URL:** `https://ct.ftp.sh` (Oracle UK VPS — protected by Authelia SSO)
- **Auto-deploy:** Push to `master` on GitHub → VPS auto-syncs within 5 minutes via `auto_sync.sh`

---

### Engineering & Logic Guide
For a deep dive into the "First Principles" of cooling towers, Merkel's Method, and the physics behind the dashboard, see:
- [COOLING_TOWER_FUNDAMENTALS.md](docs/COOLING_TOWER_FUNDAMENTALS.md)

### Mobile UX Architecture
The **Thermal Analysis** tab moves all operational inputs (WBT, CWT, HWT, L/G ratio, constants, chart scaling) **inline** in the main panel on mobile/tablet devices (`lg:hidden`). On desktop the inputs remain in the left sidebar. The hamburger menu on mobile shows only project metadata (client name, engineer, date) and export buttons — no keyboard inputs — eliminating the historical bug where tapping a sidebar input closed the menu. This design is consistent with the other tabs (Psychrometric, Performance Prediction, Excel Filter) which have always used inline inputs.
