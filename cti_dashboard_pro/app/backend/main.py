import os
import sys
import tempfile
import math
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add backend and core to path so imports work happily
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from core.calculations import init as init_engines, find_cwt, solve_off_design_cwt
from core.merkel_engine import merkel_kavl
from core.psychro_engine import psychrometrics
from excel_gen import generate_excel_from_payload, sanitize_filename
from excel_filter_service import generate_filtered_workbook, generate_filtered_workbook_from_directory
from report_service import generate_pdf_report


def _model_to_dict(model: BaseModel) -> dict:
    # Support both Pydantic v1 (`dict`) and v2 (`model_dump`) at runtime.
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()

app = FastAPI(
    title="SS Cooling Tower API",
    docs_url=None,    # Disable /docs in production
    redoc_url=None,   # Disable /redoc in production
    openapi_url=None, # Disable /openapi.json schema dump
)


# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "app" / "web"
DATA_ROOT = Path(__file__).resolve().parent / "core" / "data"

# Initialize engines on startup
@app.on_event("startup")
def startup_event():
    psychro_bin = DATA_ROOT / "psychro_f_alt.bin"
    merkel_bin = DATA_ROOT / "merkel_poly.bin"
    if psychro_bin.exists() and merkel_bin.exists():
        init_engines(str(psychro_bin), str(merkel_bin))
        print("Engines initialized successfully.")
    else:
        print("[WARNING] Could not find binary data files from", DATA_ROOT)

# Pydantic models for API
class PsychroRequest(BaseModel):
    dbt: float
    wbt: float
    alt: float = 0.0

class PredictRequest(BaseModel):
    wbt: float
    range: float
    lg: float
    constC: float
    constM: float

class CurveInputs(BaseModel):
    axXMin: float
    axXMax: float
    lgRatio: float
    constantC: float
    constantM: float
    designHWT: float
    designCWT: float

class CurveRequest(BaseModel):
    inputs: CurveInputs
    flowPercent: int

class ExcelExportRequest(BaseModel):
    inputs: dict
    curves: dict

class LocalFilterRequest(BaseModel):
    startTime: Optional[str] = ""
    endTime: Optional[str] = ""
    sourcePath: str
    destPath: Optional[str] = ""

class KaVLRequest(BaseModel):
    wbt: float
    hwt: float
    cwt: float
    lg: float

class Atc105Request(BaseModel):
    # Design (nameplate / contract) conditions
    design_wbt: float
    design_cwt: float
    design_hwt: float
    design_flow: float         # m3/hr at 100% flow
    design_fan_power: float = 117.0  # kW
    # Test (site-measured) conditions
    test_wbt: float
    test_cwt: float
    test_hwt: float
    test_flow: float           # m3/hr
    test_fan_power: float = 117.0    # kW
    # Thermal model constants (from Thermal Analysis tab)
    lg_ratio: float
    constant_c: float
    constant_m: float

# Calculation endpoints
@app.post("/api/calculate/kavl")
async def api_calc_kavl(req: KaVLRequest):
    try:
        res = merkel_kavl(req.hwt, req.cwt, req.wbt, req.lg)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/calculate/psychro")
async def api_calc_psychro(req: PsychroRequest):
    try:
        res = psychrometrics(req.dbt, req.wbt, req.alt)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/calculate/predict")
async def api_calc_predict(req: PredictRequest):
    try:
        res = solve_off_design_cwt(req.wbt, req.range, req.lg, req.constC, req.constM)
        if not res:
            raise HTTPException(status_code=400, detail="Cannot solve prediction for given parameters.")
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/calculate/curves")
async def api_calc_curves(req: CurveRequest):
    try:
        data = []
        wbt_start = req.inputs.axXMin
        wbt_end = req.inputs.axXMax
        if wbt_start >= wbt_end:
            raise ValueError("Invalid axis range")

        wbt = wbt_start
        inputs_dict = _model_to_dict(req.inputs)
        while wbt <= wbt_end:
            # Format wbt exactly like JS loop
            wbt_val = float(f"{wbt:.2f}")
            cwt80 = find_cwt(inputs_dict, wbt_val, 80, req.flowPercent)
            cwt100 = find_cwt(inputs_dict, wbt_val, 100, req.flowPercent)
            cwt120 = find_cwt(inputs_dict, wbt_val, 120, req.flowPercent)

            if not (math.isnan(cwt80) or math.isnan(cwt100) or math.isnan(cwt120)):
                data.append({
                    "wbt": wbt_val,
                    "range80": cwt80,
                    "range100": cwt100,
                    "range120": cwt120
                })
            wbt += 0.25

        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/calculate/atc105")
async def api_calc_atc105(req: Atc105Request):
    """
    CTI ATC-105 Five-Step Performance Evaluation.
    Returns all intermediate tables, cross-plot data, adjusted flow,
    predicted CWT, shortfall and capability.
    """
    try:
        def _lerp(x, x0, x1, y0, y1):
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

        def _interp_curve(x, xs, ys):
            """Linear interpolation / extrapolation along a curve."""
            n = len(xs)
            if x <= xs[0]:
                slope = (ys[1] - ys[0]) / (xs[1] - xs[0]) if xs[1] != xs[0] else 0
                return ys[0] + slope * (x - xs[0])
            if x >= xs[-1]:
                slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2]) if xs[-1] != xs[-2] else 0
                return ys[-1] + slope * (x - xs[-1])
            for i in range(n - 1):
                if xs[i] <= x <= xs[i + 1]:
                    return _lerp(x, xs[i], xs[i + 1], ys[i], ys[i + 1])
            return ys[-1]

        def _water_density(T):
            """Kell (1975) water density (kg/m³), valid 0–100 °C."""
            num = (999.83952 + 16.945176 * T - 7.9870401e-3 * T ** 2
                   - 46.170461e-6 * T ** 3 + 105.56302e-9 * T ** 4
                   - 280.54253e-12 * T ** 5)
            return num / (1 + 16.879850e-3 * T)

        design_range = req.design_hwt - req.design_cwt
        test_range   = req.test_hwt  - req.test_cwt
        test_range_pct = (test_range / design_range) * 100.0

        range_pcts = [80.0, 100.0, 120.0]   # % of design range
        flow_pcts  = [90,   100,   110]      # % of design flow

        # Absolute range values (°C)
        ranges_abs = {int(rp): round(design_range * rp / 100.0, 3) for rp in range_pcts}

        # Absolute flow values (m3/hr)
        flows_m3h = {fp: round(req.design_flow * fp / 100.0, 2) for fp in flow_pcts}

        # Inputs dict for find_cwt (uses design HWT/CWT to derive design_range internally)
        base_inputs = {
            "lgRatio":    req.lg_ratio,
            "constantC":  req.constant_c,
            "constantM":  req.constant_m,
            "designHWT":  req.design_hwt,
            "designCWT":  req.design_cwt,
        }

        # ── STEP 1: Table 1 – CWT at test WBT for 3 ranges × 3 flows ─────────
        table1 = {}
        for fp in flow_pcts:
            table1[fp] = {}
            for rp in range_pcts:
                val = find_cwt(base_inputs, req.test_wbt, rp, fp)
                table1[fp][int(rp)] = round(val, 3) if not math.isnan(val) else None

        # ── STEP 2: Cross Plot 1 – interpolate at test_range_pct ─────────────
        cross1 = {}
        for fp in flow_pcts:
            r80  = table1[fp][80]
            r100 = table1[fp][100]
            r120 = table1[fp][120]
            if any(v is None for v in [r80, r100, r120]):
                cross1[fp] = None
                continue
            if test_range_pct <= 100.0:
                cwt = _lerp(test_range_pct, 80.0, 100.0, r80, r100)
            else:
                cwt = _lerp(test_range_pct, 100.0, 120.0, r100, r120)
            cross1[fp] = round(cwt, 3)

        cp2_flows = [flows_m3h[fp] for fp in flow_pcts]
        cp2_cwts  = [cross1[fp]   for fp in flow_pcts]

        # ── STEP 4: Adjusted water flow ───────────────────────────────────────
        avg_test_T   = (req.test_hwt   + req.test_cwt)   / 2.0
        avg_design_T = (req.design_hwt + req.design_cwt) / 2.0
        density_test   = _water_density(avg_test_T)
        density_design = _water_density(avg_design_T)
        density_ratio  = density_test / density_design

        adj_flow = (req.test_flow
                    * (req.design_fan_power / req.test_fan_power) ** (1 / 3)
                    * density_ratio ** (1 / 3))

        # ── STEP 5: Predict CWT at adj_flow, find pred_flow at design CWT ────
        valid_pairs = [(f, c) for f, c in zip(cp2_flows, cp2_cwts) if c is not None]
        vf = [p[0] for p in valid_pairs]
        vc = [p[1] for p in valid_pairs]

        pred_cwt  = round(_interp_curve(adj_flow,       vf, vc), 3) if vf else None
        pred_flow = round(_interp_curve(req.design_cwt, vc, vf), 2) if vf else None

        shortfall  = round(req.test_cwt - pred_cwt, 3) if pred_cwt is not None else None
        capability = round((adj_flow / pred_flow) * 100, 1) if pred_flow and pred_flow > 0 else None

        return {
            "design_range":    round(design_range, 3),
            "test_range":      round(test_range, 3),
            "test_range_pct":  round(test_range_pct, 2),
            "ranges_abs":      ranges_abs,
            "flows_m3h":       flows_m3h,
            # Table 1: {flow_pct: {range_pct: cwt}}
            "table1": {
                str(fp): {str(int(rp)): table1[fp][int(rp)] for rp in range_pcts}
                for fp in flow_pcts
            },
            # Cross Plot 1 series (for plotting)
            "cross_plot_1": {
                "ranges_abs":  [ranges_abs[int(rp)] for rp in range_pcts],
                "cwt_90":      [table1[90][int(rp)]  for rp in range_pcts],
                "cwt_100":     [table1[100][int(rp)] for rp in range_pcts],
                "cwt_110":     [table1[110][int(rp)] for rp in range_pcts],
                "test_range":  round(test_range, 3),
                "f90_cwt":     cross1[90],
                "f100_cwt":    cross1[100],
                "f110_cwt":    cross1[110],
            },
            # Cross Plot 2 data (for plotting)
            "cross_plot_2": {
                "flows":      cp2_flows,
                "cwts":       cp2_cwts,
                "adj_flow":   round(adj_flow, 2),
                "pred_flow":  pred_flow,
                "pred_cwt":   pred_cwt,
                "test_cwt":   req.test_cwt,
                "design_cwt": req.design_cwt,
            },
            # Density correction details
            "density_test":    round(density_test,   4),
            "density_design":  round(density_design, 4),
            "density_ratio":   round(density_ratio,  6),
            # Top-level summary
            "adj_flow":    round(adj_flow, 2),
            "pred_cwt":    pred_cwt,
            "pred_flow":   pred_flow,
            "shortfall":   shortfall,
            "capability":  capability,
        }
    except Exception as exc:
        import traceback
        raise HTTPException(status_code=400, detail=f"ATC-105 error: {exc}\n{traceback.format_exc()}")


# Excel Export 
@app.post("/api/export-excel")
async def export_excel(payload: dict):
    project_name = payload.get("inputs", {}).get("projectName", "Thermal Analysis")
    safe_name = sanitize_filename(project_name)
    download_name = f"Professional_Report_{safe_name}.xlsx"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = os.path.join(temp_dir, download_name)
            generate_excel_from_payload(payload, temp_output)
            with open(temp_output, "rb") as f:
                file_bytes = f.read()

        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to generate report: {exc}")

@app.post("/api/parse-filter-excel")
async def api_parse_filter_excel(file: UploadFile = File(...)):
    """
    Parse a Filter Tool output Excel and extract averaged test values
    (CWT, HWT, WBT, DBT, flow, fan power) for auto-filling the Report Builder.
    Reads the "Filtered Data" sheet and identifies the COLUMN AVERAGE row,
    then classifies columns by keyword (cwt/hwt/wbt/dbt) or by Source File name.
    """
    import pandas as pd
    from io import BytesIO

    content = await file.read()
    df = None
    for sheet_arg in ['Filtered Data', 0]:
        try:
            df = pd.read_excel(BytesIO(content), sheet_name=sheet_arg)
            break
        except Exception:
            continue
    if df is None:
        raise HTTPException(status_code=400, detail="Cannot read Excel file")

    # ── Locate the COLUMN AVERAGE row ────────────────────────────────────────
    avg_row_data: dict = {}
    for i in range(max(0, len(df) - 5), len(df)):
        first = str(df.iloc[i, 0]).strip().upper()
        if 'AVERAGE' in first:
            for col_idx, col_name in enumerate(df.columns):
                try:
                    fval = float(df.iloc[i, col_idx])
                    if math.isfinite(fval) and 0 < abs(fval) < 1e12:
                        avg_row_data[str(col_name)] = round(fval, 4)
                except (ValueError, TypeError):
                    pass
            break

    # Fallback: compute averages from all numeric data rows (skip OL values)
    if not avg_row_data:
        skip_kw = {'source', 'file', 'date', 'time', 'scan', 'number'}
        for col in df.columns:
            if any(k in str(col).lower() for k in skip_kw):
                continue
            series = pd.to_numeric(df[col], errors='coerce')
            series = series[series.abs() < 1e12]
            if series.notna().sum() >= 2:
                avg_row_data[str(col)] = round(float(series.mean()), 4)

    # ── Classify by column name keyword ──────────────────────────────────────
    cwt_vals, hwt_vals, wbt_vals, dbt_vals, flow_vals, power_vals = [], [], [], [], [], []
    for col_name, avg_val in avg_row_data.items():
        cl = col_name.lower()
        if 'cwt' in cl or 'cold' in cl:
            cwt_vals.append(avg_val)
        elif 'hwt' in cl or 'hot' in cl:
            hwt_vals.append(avg_val)
        elif 'wbt' in cl or 'wet' in cl:
            wbt_vals.append(avg_val)
        elif 'dbt' in cl or 'dry' in cl:
            dbt_vals.append(avg_val)
        elif 'flow' in cl:
            flow_vals.append(avg_val)
        elif 'kw' in cl or 'power' in cl:
            power_vals.append(avg_val)

    # ── Fallback: classify by Source File name (multi-file layout) ───────────
    if not any([cwt_vals, hwt_vals, wbt_vals]) and 'Source File' in df.columns:
        skip_kw2 = {'source file', 'date', 'time', 'scan'}
        val_col = next(
            (c for c in df.columns
             if c not in ['Source File'] and 'time' not in c.lower() and 'date' not in c.lower()
             and pd.api.types.is_numeric_dtype(df[c])), None)
        if val_col:
            for src_file, group in df.groupby('Source File'):
                src_lower = str(src_file).lower()
                series = pd.to_numeric(group[val_col], errors='coerce')
                series = series[series.abs() < 1e12]
                if series.notna().sum() < 2:
                    continue
                avg_v = round(float(series.mean()), 4)
                if 'cwt' in src_lower:
                    cwt_vals.append(avg_v)
                elif 'hwt' in src_lower:
                    hwt_vals.append(avg_v)
                elif 'wbt' in src_lower:
                    wbt_vals.append(avg_v)
                elif 'dbt' in src_lower:
                    dbt_vals.append(avg_v)

    def _mean(vals):
        return round(sum(vals) / len(vals), 3) if vals else None

    return {
        "cwt":        _mean(cwt_vals),
        "hwt":        _mean(hwt_vals),
        "wbt":        _mean(wbt_vals),
        "dbt":        _mean(dbt_vals),
        "flow":       _mean(flow_vals),
        "fan_power":  _mean(power_vals),
        "all_averages": avg_row_data,
        "columns": list(df.columns.astype(str)),
    }


# Filter Excel
@app.post("/api/filter-excel")
async def filter_excel(
    startTime: Optional[str] = Form(default=""),
    endTime: Optional[str] = Form(default=""),
    files: List[UploadFile] = File(...)
):
    SUPPORTED_EXT = ('.xlsx', '.xls')
    valid_files = [f for f in files if f.filename.lower().endswith(SUPPORTED_EXT)]
    if not valid_files:
        raise HTTPException(status_code=400, detail="Please upload valid .xlsx or .xls files.")

    file_items = []
    for f in valid_files:
        file_bytes = await f.read()
        file_items.append((f.filename, file_bytes))

    try:
        download_name, final_bytes = generate_filtered_workbook(file_items, startTime, endTime)
        return Response(
            content=final_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to filter files: {exc}")

# Local filter API (Secured)
@app.post("/api/filter-excel-local")
async def filter_excel_local(req: LocalFilterRequest):
    # SECURITY: Check environment variable to allow local file writing
    if os.environ.get("ENABLE_LOCAL_WRITE", "0") != "1":
        raise HTTPException(status_code=403, detail="Local file writing is disabled for security reasons on this server.")

    if not req.sourcePath:
        raise HTTPException(status_code=400, detail="sourcePath is required.")

    try:
        download_name, bg_bytes = generate_filtered_workbook_from_directory(req.sourcePath, req.startTime, req.endTime)
        
        dest_path = req.destPath.strip() if req.destPath else ""
        if dest_path:
            os.makedirs(dest_path, exist_ok=True)
            full_save_path = os.path.join(dest_path, download_name)
            with open(full_save_path, "wb") as f:
                f.write(bg_bytes)
            
            return {"message": f"Success! File saved directly to {dest_path}", "isFile": False}
        
        return Response(
            content=bg_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to filter files: {exc}")

@app.post("/api/generate-pdf-report")
def api_generate_pdf_report(payload: dict):
    """
    Renders and streams out the fully calculated ATC-105 PDF.
    """
    try:
        pdf_bytes = generate_pdf_report(payload)
        return Response(
            content=pdf_bytes, 
            media_type="application/pdf", 
            headers={"Content-Disposition": "attachment; filename=CTI_Performance_Report_ATC105.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF Generation Failed: {str(e)}")

# Serve UI
app.mount("/css", StaticFiles(directory=str(WEB_ROOT / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(WEB_ROOT / "js")), name="js")

@app.get("/")
async def root():
    index_path = WEB_ROOT / "index.html"
    return FileResponse(index_path)

if __name__ == "__main__":
    port = 8000
    print(f"Starting highly optimized FastAPI server on http://localhost:{port}")
    # Local mode automatically sets the ENABLE_LOCAL_WRITE flag so Windows batch users can filter excel 
    os.environ["ENABLE_LOCAL_WRITE"] = "1"
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
