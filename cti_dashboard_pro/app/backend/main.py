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
