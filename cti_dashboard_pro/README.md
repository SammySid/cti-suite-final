# CTI Dashboard Pro — Full-Stack ATC-105 Performance Analysis Suite

`cti_dashboard_pro` is the **enterprise FastAPI-backed** evolution of the CTI Analysis Suite. It runs at **`https://ct.ftp.sh`** (Oracle UK VPS, protected by Authelia SSO).

---

## What it does

| Feature | Description |
|---|---|
| **Thermal Analysis** | Live Merkel-based performance curves at 90/100/110% flow — supply vs demand KaV/L, approach, range, CWT prediction |
| **Psychrometric Calculator** | Full Hyland-Wexler psychrometrics (DP, HR, RH, H, SV, density) with altitude correction |
| **Excel Data Filter** | Filters multi-file time-series `.xlsx` datasets by time window; interpolates, merges, exports consolidated workbook |
| **Excel Report Export** | Generates branded professional thermal report `.xlsx` from current analysis inputs |
| **ATC-105 PDF Report Engine** | Full 5-step CTI ATC-105 performance evaluation — calculates Table 1, Cross Plot 1 & 2, adjusted flow, predicted CWT, shortfall, capability, and generates a professional 11-page PDF report |
| **Excel Auto-Fill** | Upload the filtered Excel output directly into the report builder to auto-populate test condition fields |

---

## ATC-105 Report Engine

The report builder follows the **CTI ATC-105 standard** exactly:

| Step | What happens |
|---|---|
| **STEP 1** | Computes 3×3 CWT grid (Table 1) from Merkel engine at test WBT for 3 ranges × 3 flows |
| **STEP 2** | Interpolates Cross Plot 1 → Table 2 (CWT at test range for each flow %) |
| **STEP 3** | Plots Cross Plot 2: Water Flow vs CWT from Table 2 data |
| **STEP 4** | Calculates Adjusted Water Flow (`Q_adj = Q_test × (Wd/Wt)^⅓ × ρ^⅓`) |
| **STEP 5** | Reads Predicted CWT from Cross Plot 2, computes shortfall and capability (%) |

All plots are generated dynamically with Matplotlib. The Merkel and psychrometric engines are **not modified** — calibrated tower constants (LG ratio, C, m) are supplied by the user via the Thermal Analysis tab or Report Builder inputs.

### Density Ratio Override
The standard formula uses a water density ratio (ρ_test/ρ_design). The backend auto-computes this using the Kell (1975) formula. Users can override it by entering the value from ATC-105 standard tables (e.g., `1.0337` for specific test conditions) in the **ATC-105 Density Ratio** field.

### Excel Auto-Fill
After running the Excel Data Filter tool, click **"Upload Filter Output → Auto-Fill"** in the Report Builder tab to automatically populate:
- Cold Water Temperature (CWT)
- Hot Water Temperature (HWT)
- Wet Bulb Temperature (WBT)
- Water Flow
- Fan Power

---

## Quick Start (Local)

```bash
pip install fastapi uvicorn pydantic python-multipart pandas openpyxl xlsxwriter python-dateutil jinja2 xhtml2pdf matplotlib
```

Then from `cti_dashboard_pro/`:
```bash
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```
Or simply run `start_dashboard.bat` (Windows).

---

## VPS Deployment

The app is containerised with Docker and deployed to **Oracle UK VPS**.

```bash
# Deploy immediately (commits, pushes, SSH-triggers VPS rebuild)
python deploy_pro_to_vps.py
```

Or push to `master` — the VPS auto-syncs within 5 minutes via `auto_sync.sh`.

See [`VPS_HOSTING_GUIDE.md`](../VPS_HOSTING_GUIDE.md) for full architecture.

---

## Engineering Reference

- [DOCUMENTATION.md](docs/DOCUMENTATION.md) — full API reference and architecture
- [COOLING_TOWER_FUNDAMENTALS.md](docs/COOLING_TOWER_FUNDAMENTALS.md) — first-principles physics guide
- [HANDOFF.md](../HANDOFF.md) — engine reverse-engineering history

---

## ⚠️ Critical — Do Not Touch

The Merkel engine (`core/merkel_engine.py`) and Psychrometrics engine (`core/psychro_engine.py`) achieved **100% accuracy** vs the CTI binary after extensive reverse-engineering and probing. **Never modify these engines.** All calculation improvements must go through the `ATC-105` layer in `main.py`, not the core engines.

Inside `core/`, always use **relative imports** (`from .psychro_engine import ...`) to prevent Python from creating duplicate module instances that would break the binary lookup tables.
