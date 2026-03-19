# SS Cooling Tower Dashboard - Complete Documentation

## 1) Project Overview

This project is a local-first engineering dashboard for cooling tower thermal analysis, psychrometric calculations, and Excel data processing/export.

The dashboard is built as:
- A static frontend (`app/web/index.html` + modular JS/CSS)
- A high-performance Python FastAPI server (`app/backend/main.py`)
- Backend services for Excel report generation and Excel time-window filtering

Primary outcomes supported:
- Live thermal curve generation (90/100/110% flow scenarios)
- Thermal KPI display (supply/demand KaV/L, approach, range)
- Psychrometric property calculations
- Professional Excel report export
- Batch Excel filtering and consolidated workbook export

---

## 2) Core Features

### Thermal analysis engine
- Computes demand KaV/L using Merkel integration logic.
- Computes supply KaV/L from L/G and constants C, m.
- Renders 3 performance charts:
  - Low flow (90%)
  - Nominal flow (100%)
  - High flow (110%)

### Psychrometric calculator
- Inputs: DBT, WBT, altitude
- Outputs: humidity ratio, dew point, RH, enthalpy, specific volume, density, pressure
- Validation: rejects invalid state `WBT > DBT`

### Excel export (thermal report)
- Frontend sends payload to `/api/export-excel`
- Backend generates formatted workbook with:
  - metadata and branded layout
  - data tables for flow scenarios
  - helper columns and KPIs
  - performance charts

### Excel filter tool
- Supports:
  - local source folder path mode (`/api/filter-excel-local`)
  - uploaded files mode (`/api/filter-excel`)
- Optional Destination path input to bypass browser download and save the output directly to disk.
- Filters by start/end time.
- Produces:
  - filtered data sheet
  - summary sheet
  - dynamic date-based report layout sheets (e.g., `12-11-2023`, `13-11-2023`) or a `Consolidated` sheet if only one date is present.

### Responsive UX
- Mobile drawer for controls
- Tablet/desktop adaptive layout
- Sticky mobile header and touch-friendly actions
- Print-focused formatting for engineering reports

---

## 3) Architecture

## Frontend
- `app/web/index.html`: full dashboard UI and panel structure
- `app/web/css/main.css`: visual style, responsive behavior, print rules
- `app/web/js/ui.js`: central state + orchestration
- `app/web/js/ui/*`: modular UI features

### Frontend module map
- `app/web/js/ui/constants.js` - shared field lists and curve-affecting input map
- `app/web/js/ui/bind-events.js` - event wiring and startup UI flow
- `app/web/js/ui/mobile-nav.js` - drawer open/close logic
- `app/web/js/ui/tabs.js` - tab activation and panel switching
- `app/web/js/ui/psychro.js` - psychrometric rendering/validation
- `app/web/js/ui/filter.js` - filter tool state + request flow
- `app/web/js/ui/export.js` - export state + download flow

### Calculation layer
- `app/web/js/worker.js` - async fetch wrapper offloading curve generation arrays to the API
- `app/web/js/charts.js` - Chart.js rendering wrapper

## Backend (IP Secured)
- `app/backend/main.py` provides static file serving + FastAPI routes:
  - `POST /api/calculate/kavl`
  - `POST /api/calculate/psychro`
  - `POST /api/calculate/predict`
  - `POST /api/calculate/curves`
  - `POST /api/export-excel`
  - `POST /api/filter-excel`
  - `POST /api/filter-excel-local`
- `app/backend/excel_gen.py` generates thermal report workbook from frontend payload
- `app/backend/excel_filter_service.py` performs filtering/merge/report-layout generation

---

## 4) Data Flow

### Thermal charts
1. User updates thermal or axis inputs.
2. UI updates KPI cards immediately.
3. Worker receives `CALCULATE_CURVE` per flow percent.
4. Worker returns curve datasets.
5. UI renders charts and updates export readiness.

### Excel export
1. UI ensures curves are ready.
2. UI sends payload (`inputs`, `data90`, `data100`, `data110`) to backend.
3. Backend validates payload and writes workbook in temp directory.
4. Backend returns XLSX bytes as downloadable response.

### Excel filtering
1. User provides time range and source path OR uploaded files.
2. Backend parses files, detects time column/header, filters rows.
3. Backend generates filtered master workbook and summary.
4. Browser downloads result.

---

## 5) API Reference

## `POST /api/export-excel`
Generates professional thermal report workbook.

Request:
- JSON body
- Required keys:
  - `inputs`
  - `data90`
  - `data100`
  - `data110`

Response:
- `200` XLSX binary
- `400/413` JSON error: `{"error":"..."}` on validation/size failures

## `POST /api/filter-excel`
Filters uploaded Excel files by time range.

Request:
- `multipart/form-data`
- fields:
  - `startTime`
  - `endTime`
  - one or more `files` (`.xlsx`)

Response:
- `200` XLSX binary
- `400/413` JSON error

## `POST /api/filter-excel-local`
Filters `.xlsx` files found in a local folder path.

Request:
- JSON body with:
  - `startTime`
  - `endTime`
  - `sourcePath`
  - `destPath` (optional)

Response:
- `200` JSON `{"message": "..."}` if `destPath` is provided (file saved directly to disk)
- `200` XLSX binary if `destPath` is omitted
- `400/413` JSON error

---

## 6) Directory and File Guide

Key runtime files:
- `app/web/index.html` - dashboard entry
- `app/web/css/main.css` - styling + print overrides
- `app/web/js/ui.js` - central orchestrator
- `app/web/js/ui/` - modular UI code
- `app/web/js/worker.js` - background curve calculations
- `app/backend/main.py` - FastAPI server + backend endpoints
- `app/backend/core/merkel_engine.py` - IP Secured Merkel integration
- `app/backend/core/psychro_engine.py` - IP Secured Psychrometrics
- `app/backend/excel_gen.py` - report generation
- `app/backend/excel_filter_service.py` - filter service
- `start_dashboard.bat` - one-click launch
- `app/scripts/test_backend.mjs` - backend/engine smoke test

Supporting folders:
- `app/backend/core/data/` - binary tables serving python engines
- `app/reports/` - generated outputs and stored exports
- `docs/` - documentation and references

---

## 7) Setup and Run

## Windows quick start (recommended)
1. Open `Caclulator/start_dashboard.bat`
2. It:
   - verifies Python availability
   - installs required Python packages if needed
   - starts server on `http://localhost:8000`
3. Keep terminal open while using dashboard. Press `Ctrl+C` for a graceful shutdown.

## Manual run
From `cti_dashboard_pro/`:
- `python app/backend/main.py`

Then open:
- `http://localhost:8000`

Python dependencies (auto-installed by launcher):
- `fastapi`
- `uvicorn`
- `pydantic`
- `python-multipart`
- `xlsxwriter`
- `pandas`
- `openpyxl`
- `python-dateutil`

---

## 8) Performance and UX Notes

Implemented hardening includes:
- Worker-based curve generation (no heavy UI blocking)
- Debounced heavy recalculation
- Recalculation only for curve-affecting inputs
- Duplicate curve-request skipping via signature checks
- Mobile drawer behavior and state management
- Improved export/filter status handling
- Psychrometric readiness guard during engine initialization
- Invalid psychrometric state clears stale output values

---

## 9) Testing and Validation

## Smoke test
Run from `Caclulator/`:
- `node app/scripts/test_backend.mjs`

This verifies:
- psychrometric output path
- Merkel KaV/L computation path
- top-level calculations pipeline consistency

## Manual QA checklist
- Thermal/Psychro/Filter tab switching
- Mobile drawer open/close and control accessibility
- Export button disable/enable state transition
- Psychrometric validation (`WBT > DBT`)
- Filter validation errors and successful download flow
- Print preview/report layout readability

---

## 10) Troubleshooting

## Dashboard not loading
- Confirm server is running at `http://localhost:8000`
- Ensure no port conflict on `8000`

## Export button stays disabled
- Wait for curves to complete.
- Check invalid axis ranges (`X min < X max`, `Y min < Y max`).

## Psychrometric shows `--`
- Check DBT/WBT/Altitude are numeric
- Ensure `WBT <= DBT`
- Wait for engine initialization to complete

## Filter export fails
- Verify time values and source path
- Ensure files are valid `.xlsx`
- Confirm time column exists in source sheets

## Tailwind CDN warning in console
- Current UI uses CDN script for convenience in local environment.
- For production hardening, migrate to local Tailwind build pipeline.

---

## 11) Security and operational notes

- Server enforces payload size limits for JSON/multipart routes.
- Filenames are sanitized before report generation.
- Local-path filtering is intended for trusted local use.
- Keep this service local/network-restricted unless further hardened.

---

## 12) Future recommendations

- Replace Tailwind CDN with build-time Tailwind output.
- Add automated browser regression suite (desktop/tablet/mobile).
- Add API contract tests for export/filter endpoints.
- Package as installable desktop app if required.

