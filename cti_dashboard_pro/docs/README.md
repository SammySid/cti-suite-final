# SS Cooling Tower Dashboard Pro — Quick Reference

> **Live:** `https://ct.ftp.sh` | **Last updated:** 2026-04-18

## Quick Start (Local)

```bash
# Install dependencies
pip install fastapi uvicorn pydantic python-multipart pandas openpyxl xlsxwriter python-dateutil jinja2 xhtml2pdf matplotlib

# Start server (from cti_dashboard_pro/)
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000

# Or use the launcher (Windows)
start_dashboard.bat
```

Open `http://localhost:8000`.

---

## Project Layout

```
cti_dashboard_pro/
├── app/
│   ├── backend/
│   │   ├── main.py                  ← FastAPI server + all API endpoints
│   │   ├── report_service.py        ← Matplotlib plots + PDF generation
│   │   ├── excel_gen.py             ← Thermal report .xlsx builder
│   │   ├── excel_filter_service.py  ← Time-window filter service
│   │   ├── core/
│   │   │   ├── calculations.py      ← find_cwt, demand/supply KaVL
│   │   │   ├── merkel_engine.py     ← 🔒 DO NOT MODIFY — 100% accuracy
│   │   │   ├── psychro_engine.py    ← 🔒 DO NOT MODIFY — 100% accuracy
│   │   │   └── data/
│   │   │       ├── merkel_poly.bin  ← 29.8 KB Chebyshev coefficients
│   │   │       └── psychro_f_alt.bin
│   │   └── templates/
│   │       └── report_template.html ← Jinja2 ATC-105 PDF template
│   └── web/
│       ├── index.html               ← Single-page dashboard UI
│       ├── css/main.css
│       └── js/
│           ├── ui.js                ← Central state orchestrator
│           ├── worker.js            ← Async API proxy for curve calc
│           ├── charts.js            ← Chart.js rendering
│           └── ui/
│               ├── bind-events.js   ← All event listeners
│               ├── report.js        ← ATC-105 report builder logic
│               ├── filter.js        ← Excel filter tool
│               ├── export.js        ← Excel export
│               ├── prediction.js    ← CWT prediction
│               ├── psychro.js       ← Psychrometric display
│               ├── tabs.js          ← Tab switching
│               └── mobile-nav.js    ← Mobile drawer
├── Dockerfile                       ← python:3.11-slim + cairo build deps
├── docker-compose.yml
├── requirements.txt
├── start_dashboard.bat
└── deploy_pro_to_vps.py             ← One-command deploy to VPS
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/calculate/kavl` | Single Merkel KaV/L point |
| POST | `/api/calculate/psychro` | Psychrometric properties |
| POST | `/api/calculate/predict` | CWT prediction |
| POST | `/api/calculate/curves` | Full 3-flow performance curves |
| POST | `/api/calculate/atc105` | Full 5-step ATC-105 evaluation |
| POST | `/api/parse-filter-excel` | Parse filter output → auto-fill test conditions |
| POST | `/api/export-excel` | Generate thermal report `.xlsx` |
| POST | `/api/filter-excel` | Filter uploaded `.xlsx` files by time range |
| POST | `/api/filter-excel-local` | Filter local folder path `.xlsx` files |
| POST | `/api/generate-pdf-report` | Render full ATC-105 PDF report |

---

## Docs

- [DOCUMENTATION.md](DOCUMENTATION.md) — full API reference, data flow, architecture
- [COOLING_TOWER_FUNDAMENTALS.md](COOLING_TOWER_FUNDAMENTALS.md) — first-principles physics
