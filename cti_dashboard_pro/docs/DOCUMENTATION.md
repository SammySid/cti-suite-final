# CTI Dashboard Pro — Complete Technical Documentation

> **Last updated:** 2026-04-18

---

## 1. Project Overview

A full-stack engineering dashboard for cooling tower thermal analysis, psychrometric calculations, Excel data processing, and automated ATC-105 PDF report generation.

**Stack:**
- Frontend: Single-page HTML/CSS/JS (Tailwind CDN, Chart.js, modular ES6)
- Backend: Python 3.11 + FastAPI + Uvicorn
- PDF reports: Jinja2 + xhtml2pdf + Matplotlib
- Deployment: Docker (python:3.11-slim) on Oracle UK VPS via `auto_sync.sh`

---

## 2. Core Features

### Thermal Analysis Engine
- Demand KaV/L: Merkel 4-point Chebyshev integration (Kell 1975 psychrometrics)
- Supply KaV/L: `C × (L/G)^(-m)` — user-defined tower characteristic constants
- 3 performance curves rendered: 90%, 100%, 110% water flow
- Live KPI cards: approach, range, supply KaV/L, demand KaV/L, curve balance point

### Psychrometric Calculator
- Inputs: DBT, WBT, altitude (m)
- Outputs: humidity ratio (HR), dew point (DP), RH, enthalpy (H), specific volume (SV), density
- Validation: rejects `WBT > DBT` states

### Excel Data Filter
- Accepts uploaded `.xlsx` files or local folder path
- Filters rows by start/end time window
- Outputs: filtered data sheet + summary sheet + date-based layout sheets
- Auto-detects time column and header row
- Produces a "COLUMN AVERAGE" row for use with the ATC-105 auto-fill feature

### Excel Report Export
- Generates branded thermal report `.xlsx` from current analysis inputs
- Includes flow scenario data tables and KPIs

### ATC-105 PDF Report Engine (full 5-step CTI method)

See Section 4 for the complete calculation flow.

- **Table 1** — 3×3 CWT grid (3 ranges × 3 flows) at test WBT from Merkel engine
- **Cross Plot 1** — CWT vs Range with test-range vertical marker; professional Matplotlib output
- **Table 2** — CWT at test range for each flow (read from Cross Plot 1 intersections)
- **Cross Plot 2** — Water Flow vs CWT with crosshair step annotations (adj flow → pred CWT → pred flow)
- **Steps 4–5** — Adjusted flow, predicted CWT, shortfall, capability
- **PDF layout** — 11-page Jinja2 template: cover, preamble, members, assessment, instruments, conclusions, suggestions, data table, air flow, ATC-105 calculation pages, final results

### Excel Auto-Fill (Report Builder)
- Upload the filtered `.xlsx` output from the Excel Data Filter
- Backend parses "COLUMN AVERAGE" row, classifies columns by type (CWT, HWT, WBT, flow, fan power)
- Auto-populates test condition fields in the Report Builder tab
- Triggers live ATC-105 preview update

---

## 3. Architecture

### Frontend Modules

| File | Purpose |
|---|---|
| `js/ui.js` | Central state store + orchestration |
| `js/worker.js` | Web Worker proxy for curve API calls |
| `js/charts.js` | Chart.js rendering wrapper |
| `js/ui/bind-events.js` | All event listeners — inputs, buttons, tabs, file uploads |
| `js/ui/report.js` | ATC-105 report builder logic: `_buildAtc105Payload`, `updateAtcPreview`, `syncDesignFromThermal`, `bindFilterUpload`, `generateReport` |
| `js/ui/filter.js` | Excel filter state + request flow |
| `js/ui/export.js` | Excel export state + download |
| `js/ui/prediction.js` | CWT prediction wrapper |
| `js/ui/psychro.js` | Psychrometric display + validation |
| `js/ui/tabs.js` | Tab activation + sidebar/inline panel toggling |
| `js/ui/mobile-nav.js` | Mobile drawer open/close |

### Backend Files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app: all endpoints + `Atc105Request` Pydantic model |
| `backend/report_service.py` | `create_cross_plot_1`, `create_cross_plot_2`, `generate_pdf_report` |
| `backend/excel_gen.py` | Thermal report `.xlsx` builder |
| `backend/excel_filter_service.py` | Time-window filter service |
| `backend/core/calculations.py` | `find_cwt`, `calculate_demand_kavl`, `calculate_supply_kavl` |
| `backend/core/merkel_engine.py` | 🔒 Merkel KaV/L — **DO NOT MODIFY** |
| `backend/core/psychro_engine.py` | 🔒 Psychrometrics — **DO NOT MODIFY** |
| `backend/core/data/merkel_poly.bin` | 29.8 KB Chebyshev coefficients |
| `backend/core/data/psychro_f_alt.bin` | 2D probed enhancement factor table |
| `backend/templates/report_template.html` | Jinja2 PDF template (11 pages) |

### ⚠️ Critical — Python Backend Import Rule
The Math Engines load binary lookup tables into **module-level globals** at startup. To prevent Python's `sys.modules` from creating two isolated engine instances (which causes lookup tables to be empty during API calls), **always use relative imports** inside `core/`:

```python
# ✅ CORRECT (inside calculations.py)
from .merkel_engine import merkel_kavl, find_cwt
from .psychro_engine import psychro_properties
```

---

## 4. ATC-105 Calculation Flow

### Pydantic Request Model (`Atc105Request`)
```
design_wbt, design_cwt, design_hwt     — °C
design_flow                             — m³/hr at 100% flow
design_fan_power                        — kW (default 117)
test_wbt, test_cwt, test_hwt           — °C
test_flow                               — m³/hr
test_fan_power                          — kW (default 117)
lg_ratio, constant_c, constant_m        — tower characteristic constants
density_ratio_override                  — optional float (uses Kell formula if None)
```

### Step-by-step computation (`/api/calculate/atc105`)

**STEP 1 — Table 1 (3×3 CWT grid)**
- Flow percentages: 90%, 100%, 110%
- Range percentages: 80%, 100%, 120% (of design range)
- For each (flow%, range%) combination: calls `find_cwt(inputs, test_wbt, range_pct, flow_pct)` → CWT
- `find_cwt` balances supply KaV/L = C × (LG)^(-m) against demand KaV/L (Merkel integration)

**STEP 2 — Cross Plot 1 / Table 2**
- Interpolates across the range dimension at `test_range` (= test_hwt − test_cwt)
- For each flow%: linear interpolation of Table 1 CWTs at test_range → `cross1[flow_pct]`

**STEP 3 — Cross Plot 2 data**
- Three (flow, CWT) pairs from Table 2 form the performance curve

**STEP 4 — Adjusted Water Flow**
```
density_ratio = ρ_water(avg_test_T) / ρ_water(avg_design_T)   [Kell 1975]
effective_density_ratio = density_ratio_override or density_ratio
adj_flow = test_flow × (design_fan_power / test_fan_power)^(1/3) × effective_density_ratio^(1/3)
```

**STEP 5 — Predicted CWT, Shortfall, Capability**
```
pred_cwt  = interpolate/extrapolate Cross Plot 2 curve at adj_flow (x→y)
pred_flow = interpolate/extrapolate Cross Plot 2 curve at design_cwt (y→x)
shortfall = test_cwt - pred_cwt
capability = (adj_flow / pred_flow) × 100   [%]
```

### API Response Keys
```json
{
  "design_range", "test_range", "test_range_pct",
  "ranges_abs",           // {80: 8.0, 100: 10.0, 120: 12.0}
  "flows_m3h",            // {90: 3477, 100: 3864, 110: 4250}
  "table1",               // {"90": {"80": cwt, "100": cwt, "120": cwt}, ...}
  "cross_plot_1": {
    "ranges_abs", "cwt_90", "cwt_100", "cwt_110",
    "test_range", "f90_cwt", "f100_cwt", "f110_cwt"
  },
  "cross_plot_2": {
    "flows", "cwts", "adj_flow", "pred_flow", "pred_cwt", "test_cwt", "design_cwt"
  },
  "density_test", "density_design", "density_ratio", "density_ratio_used",
  "adj_flow", "pred_cwt", "pred_flow", "shortfall", "capability",
  "design_wbt", "design_cwt", "design_hwt", "design_flow",
  "test_wbt", "test_cwt", "test_hwt", "test_flow"
}
```

---

## 5. API Reference

### `POST /api/calculate/atc105`
Full 5-step CTI ATC-105 performance evaluation.

Request: `Atc105Request` JSON (see Section 4).
Response: Full calculation JSON (all steps, tables, cross-plot data, final results).

### `POST /api/parse-filter-excel`
Parses filtered Excel output for report auto-fill.

Request: `multipart/form-data` with single `file` (`.xlsx`).
Response:
```json
{
  "cwt": 32.4, "hwt": 42.13, "wbt": 21.7,
  "flow": 3680.0, "fan_power": 117.0, "dbt": null,
  "columns_found": ["CWT", "HWT", "WBT", "FLOW", "FANPOWER"]
}
```

### `POST /api/generate-pdf-report`
Renders and streams the ATC-105 PDF report.

Request JSON keys:
```
report_title, client, asset, test_date, report_date
atc105                  ← full response from /api/calculate/atc105
preamble_paragraphs     ← list of strings
members_client          ← list of strings
members_ssctc           ← list of strings
assessment_method       ← list of strings
instrument_placement    ← list of strings
conclusions             ← list of strings
suggestions             ← list of strings
final_data_table        ← list of {name, unit, test1, test2, test3}
data_notes              ← list of strings
airflow                 ← {avg_velocity, area, total_flow}
```

Response: `200` PDF binary stream / `500` JSON error with traceback.

### `POST /api/export-excel`
Generates thermal analysis report `.xlsx`.

Request: `{inputs, data90, data100, data110}` JSON.
Response: `200` XLSX binary.

### `POST /api/filter-excel`
Filters uploaded `.xlsx` files by time range.

Request: `multipart/form-data` — `startTime`, `endTime`, one or more `files`.
Response: `200` XLSX binary / `400` error.

### `POST /api/filter-excel-local`
Filters `.xlsx` files from a local folder path.

Request: `{startTime, endTime, sourcePath, destPath?}` JSON.
Response: `200` XLSX binary (or JSON message if `destPath` provided).

### `POST /api/calculate/kavl`
Single Merkel KaV/L point: `{wbt, hwt, cwt, lg}` → `{kavl}`.

### `POST /api/calculate/psychro`
Psychrometric properties: `{dbt, wbt, alt}` → `{hr, dp, rh, h, sv, density}`.

### `POST /api/calculate/curves`
Full 3-flow performance curves for Chart.js rendering.

---

## 6. Report Service — Plot Details

### `create_cross_plot_1(cp1)`
- White background, clean professional axes
- Three smooth interpolated curves: 90% (purple), 100% (green), 110% (blue)
- Test-range vertical line (red) with shaded band
- Intersection points annotated with coloured bbox labels + `-|>` arrowheads
- Horizontal dashed guide lines from intersections to Y-axis
- TABLE 2 summary inset box (lower right)

### `create_cross_plot_2(cp2)`
- Piecewise-linear curve from Table 2 data (extrapolated with last-segment slope)
- Orange vertical line: adjusted water flow
- Cyan dashed horizontal: predicted CWT
- Purple dashed horizontal + green vertical: design CWT → predicted flow crosshair
- Red solid horizontal: test CWT
- All key points annotated with coloured bbox labels + arrows

### `generate_pdf_report(payload)`
- Calls `create_cross_plot_1` and `create_cross_plot_2`
- Renders `report_template.html` with Jinja2
- Passes `_f0`, `_f1`, `_f2` format-helper callables to the template
- Converts rendered HTML → PDF bytes via `xhtml2pdf.pisa.CreatePDF`
- Returns raw PDF bytes (streamed to browser as attachment)

---

## 7. PDF Report Layout (11 pages)

| Page | Content |
|---|---|
| 1 | Cover — title, asset, owner, dates, SSCTC attribution |
| 2 | Preamble |
| 3 | Members Present |
| 4 | Assessment Method + Instrument Placement |
| 5 | Conclusions + Suggestions |
| 6 | Final Data Table (3-test comparison) |
| 7 | Air Flow Data (anemometer traverses) |
| 8 | ATC-105 design vs test conditions + Table 1 + Table 2 |
| 9 | Cross Plot 1 |
| 10 | Steps 3–4 + Adjusted Flow table + Cross Plot 2 |
| 11 | Step 5 — Predicted CWT, shortfall, capability (verdict box) |

SSCTC header bar appears at top of pages 2–11. Page numbers appear in footer.

---

## 8. Data Flow

### ATC-105 Report Generation
1. User fills Design Conditions (or clicks "Sync from Thermal Tab")
2. User fills Test Conditions (manually or via "Auto-Fill from Filter Output")
3. Live ATC-105 Preview updates on every input change (debounced)
4. User clicks "Generate Report" → `report.js` calls `/api/calculate/atc105`
5. Full atc105 result + narrative payload → `POST /api/generate-pdf-report`
6. PDF bytes streamed → browser download

### Excel Auto-Fill Flow
1. User runs Excel Data Filter → downloads filtered `.xlsx`
2. In Report Builder tab, user uploads the file via "Auto-Fill from Filter Output"
3. `POST /api/parse-filter-excel` → extracts COLUMN AVERAGE row
4. Frontend auto-fills: `rep-cwt`, `rep-hwt`, `rep-test-wbt`, `rep-flow`, `rep-test-fanpow`
5. Live ATC-105 Preview updates automatically

### Thermal Chart Flow
1. Input change → debounced → `CALCULATE_CURVE` message to worker
2. Worker calls `/api/calculate/curves` → returns curve datasets
3. Charts rendered via Chart.js; KPI cards updated

---

## 9. Known Bugs Fixed

| Date | Bug | Fix |
|---|---|---|
| 2026-04-18 | `502 Bad Gateway` on `ct.ftp.sh` after Dockerfile update | Upgraded `FROM python:3.9-slim` → `python:3.11-slim`; added `libcairo2-dev`, `libpango1.0-dev` and other build tools for pycairo compilation; removed `--exclude="Dockerfile"` from `auto_sync.sh` |
| 2026-04-18 | Blank charts on Thermal Analysis tab | Fixed `try:` (Python syntax) → `try {` (JS syntax) in `report.js` — SyntaxError broke the module |
| 2026-04-18 | AM/PM assignment bug in Excel filter | `filter.js` line 48: `h >= 12 ? 'PM' : 'PM'` → `h >= 12 ? 'PM' : 'AM'` |
| 2026-04-18 | `'float' object is not iterable` in PDF generation | `report_service.py`: `max(flows[0] ...)` → `(flows[-1] if pred_flow is None else max(...))` |
| 2026-03-20 | Mobile hamburger closes on input tap | Moved operational inputs inline in `thermalTabPanel`; added `stopPropagation` on sidebar |
| 2026-03-20 | `auto_sync.sh` branch mismatch (`main` vs `master`) | Updated `BRANCH="master"` in `auto_sync.sh` |
| 2026-03-19 | `trading-nginx` crash loop | Fixed stray `}` in `nginx-trading.conf` |

---

## 10. Setup and Run

### Windows (recommended)
```bash
start_dashboard.bat   # validates Python, installs deps, starts server
```

### Manual
```bash
cd cti_dashboard_pro
pip install fastapi uvicorn pydantic python-multipart pandas openpyxl xlsxwriter python-dateutil jinja2 xhtml2pdf matplotlib
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000`.

### Docker (production)
See `VPS_HOSTING_GUIDE.md`.

---

## 11. Security and Operational Notes

- Payload size limits enforced on JSON and multipart routes
- Filenames sanitized before report generation
- Local-path filtering intended for trusted local use only
- Core math engines (merkel, psychro) are compiled to binary tables — IP protected
- VPS: protected by Authelia SSO (`https://ct.ftp.sh`)
