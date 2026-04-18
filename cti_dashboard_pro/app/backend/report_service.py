import os
import io
import base64
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from fastapi import HTTPException

matplotlib.use('Agg')

# ── Plot helpers ──────────────────────────────────────────────────────────────

def _b64_fig(fig):
    """Encode a matplotlib figure as a base64 PNG string and close the figure."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return b64


def create_cross_plot_1(cp1: dict):
    """
    Cross Plot 1: CWT vs Range @ Test WBT — three flow curves.
    cp1 keys: ranges_abs, cwt_90, cwt_100, cwt_110,
               test_range, f90_cwt, f100_cwt, f110_cwt
    """
    ranges   = cp1["ranges_abs"]
    cwt_90   = cp1["cwt_90"]
    cwt_100  = cp1["cwt_100"]
    cwt_110  = cp1["cwt_110"]
    test_rng = cp1["test_range"]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#f8fafc')
    ax.set_facecolor('#f0f4f8')

    ax.plot(ranges, cwt_90,  color='#7c3aed', linewidth=2.0, marker='o', markersize=5, label='90% Flow')
    ax.plot(ranges, cwt_100, color='#16a34a', linewidth=2.0, marker='o', markersize=5, label='100% Flow')
    ax.plot(ranges, cwt_110, color='#0284c7', linewidth=2.0, marker='o', markersize=5, label='110% Flow')

    # Vertical test-range line
    ax.axvline(x=test_rng, color='#dc2626', linestyle='-', linewidth=2, label=f'Test Range = {test_rng:.2f} °C')

    # Annotate intersection points
    for val, clr, lbl in [
        (cp1.get("f90_cwt"),  '#7c3aed', f'{cp1.get("f90_cwt", 0):.2f} °C'),
        (cp1.get("f100_cwt"), '#16a34a', f'{cp1.get("f100_cwt", 0):.2f} °C'),
        (cp1.get("f110_cwt"), '#0284c7', f'{cp1.get("f110_cwt", 0):.2f} °C'),
    ]:
        if val is None:
            continue
        ax.plot(test_rng, val, 'o', color=clr, markersize=9, zorder=5)
        ax.annotate(
            lbl,
            xy=(test_rng, val),
            xytext=(test_rng + (ranges[-1] - ranges[0]) * 0.04, val + 0.15),
            fontsize=8, color=clr, fontweight='bold',
            arrowprops=dict(arrowstyle='->', color=clr, lw=1.2),
        )

    ax.set_title("CROSS PLOT 1: CWT vs RANGE @ TEST WBT", fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel("Range (°C)", fontweight='bold')
    ax.set_ylabel("Cold Water Temperature (°C)", fontweight='bold')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(which='major', color='#b0b8c4', linewidth=0.7)
    ax.grid(which='minor', color='#d8dde4', linestyle=':', linewidth=0.4)
    ax.minorticks_on()
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

    plt.tight_layout()
    return _b64_fig(fig)


def create_cross_plot_2(cp2: dict):
    """
    Cross Plot 2: Water Flow vs CWT @ Design Range.
    cp2 keys: flows, cwts, adj_flow, pred_flow, pred_cwt, test_cwt, design_cwt
    """
    flows     = cp2["flows"]
    cwts      = cp2["cwts"]
    adj_flow  = cp2["adj_flow"]
    pred_flow = cp2.get("pred_flow")
    pred_cwt  = cp2.get("pred_cwt")
    test_cwt  = cp2.get("test_cwt")
    design_cwt = cp2.get("design_cwt")

    # Build extended smooth curve via linear interpolation / extrapolation
    f_min = min(flows) * 0.85
    f_max = max(flows[0] if pred_flow is None else max(flows + [pred_flow])) * 1.10
    xs = np.linspace(f_min, f_max, 300)

    # Piecewise-linear interpolation helper (numpy)
    ys = np.interp(xs, flows, cwts, left=None, right=None)
    # Extrapolation: extend with last-segment slope
    slope_left  = (cwts[1] - cwts[0]) / (flows[1] - flows[0])
    slope_right = (cwts[-1] - cwts[-2]) / (flows[-1] - flows[-2])
    ys = np.where(xs < flows[0],  cwts[0]  + slope_left  * (xs - flows[0]),  ys)
    ys = np.where(xs > flows[-1], cwts[-1] + slope_right * (xs - flows[-1]), ys)

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#f8fafc')
    ax.set_facecolor('#f0f4f8')

    ax.plot(xs, ys, color='black', linewidth=2.0, label='Flow vs CWT Curve')
    ax.plot(flows, cwts, 'ko', markersize=6, zorder=5)

    # Adjusted water flow vertical line
    ax.axvline(x=adj_flow, color='#f97316', linestyle='-', linewidth=2, label=f'Adj. Flow = {adj_flow:.0f} m³/hr')

    # Predicted CWT horizontal line
    if pred_cwt is not None:
        ax.axhline(y=pred_cwt, color='#0ea5e9', linestyle='--', linewidth=1.8, label=f'Pred. CWT = {pred_cwt:.2f} °C')

    # Test CWT horizontal line
    if test_cwt is not None:
        ax.axhline(y=test_cwt, color='#dc2626', linestyle='-', linewidth=1.8, label=f'Test CWT = {test_cwt:.2f} °C')

    # Predicted (design) flow vertical line
    if pred_flow is not None:
        ax.axvline(x=pred_flow, color='#2563eb', linestyle='--', linewidth=1.8, label=f'Pred. Flow = {pred_flow:.0f} m³/hr')

    ax.set_title("CROSS PLOT 2: WATER FLOW vs CWT @ DESIGN WBT AND DESIGN RANGE", fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel("Water Flow (m³/hr)", fontweight='bold')
    ax.set_ylabel("Cold Water Temperature (°C)", fontweight='bold')
    ax.legend(loc='upper left', fontsize=8.5)
    ax.grid(which='major', color='#b0b8c4', linewidth=0.7)
    ax.grid(which='minor', color='#d8dde4', linestyle=':', linewidth=0.4)
    ax.minorticks_on()

    plt.tight_layout()
    return _b64_fig(fig)


# ── Main PDF generator ────────────────────────────────────────────────────────

def generate_pdf_report(payload: dict):
    """
    Render the Jinja2 HTML report template and convert to PDF bytes.
    Payload must include an 'atc105' key with the result from /api/calculate/atc105.
    All other keys are narrative / metadata.
    """
    atc = payload.get("atc105", {})

    # ── Generate plots from real computed data ────────────────────────────────
    cp1 = atc.get("cross_plot_1", {})
    cp2 = atc.get("cross_plot_2", {})

    # Fallback: if atc105 not provided, render blank placeholder plots
    if not cp1 or not cp2:
        plot_1_b64 = _blank_plot("Cross Plot 1 — No ATC-105 data provided")
        plot_2_b64 = _blank_plot("Cross Plot 2 — No ATC-105 data provided")
    else:
        plot_1_b64 = create_cross_plot_1(cp1)
        plot_2_b64 = create_cross_plot_2(cp2)

    # ── Build intersection table from real atc105 results ────────────────────
    flows_m3h = atc.get("flows_m3h", {})
    intersect = {
        "f90_flow":  flows_m3h.get(90,  flows_m3h.get("90",  "—")),
        "f90_cwt":   cp1.get("f90_cwt",  "—"),
        "f100_flow": flows_m3h.get(100, flows_m3h.get("100", "—")),
        "f100_cwt":  cp1.get("f100_cwt", "—"),
        "f110_flow": flows_m3h.get(110, flows_m3h.get("110", "—")),
        "f110_cwt":  cp1.get("f110_cwt", "—"),
    }

    # ── Math results ──────────────────────────────────────────────────────────
    math_results = {
        "adj_flow":   atc.get("adj_flow",  payload.get("math_results", {}).get("adj_flow",  "—")),
        "pred_cwt":   atc.get("pred_cwt",  payload.get("math_results", {}).get("pred_cwt",  "—")),
        "test_cwt":   atc.get("cross_plot_2", {}).get("test_cwt",
                      payload.get("math_results", {}).get("test_cwt", "—")),
        "shortfall":  atc.get("shortfall", payload.get("math_results", {}).get("shortfall", "—")),
        "capability": atc.get("capability", payload.get("math_results", {}).get("capability", "—")),
        "density_ratio": atc.get("density_ratio", "—"),
        "pred_flow":  atc.get("pred_flow", "—"),
    }

    # ── Table 1 (3×3 CWT grid) ────────────────────────────────────────────────
    table1_raw = atc.get("table1", {})
    ranges_abs = atc.get("ranges_abs", {})
    table1_rows = []
    for rp_key, rp_label in [("80", "80%"), ("100", "100%"), ("120", "120%")]:
        abs_rng = ranges_abs.get(int(rp_key), ranges_abs.get(rp_key, "—"))
        row = {
            "range_pct": rp_label,
            "range_abs": f"{abs_rng} °C" if abs_rng != "—" else "—",
            "cwt_90":  table1_raw.get("90",  {}).get(rp_key, "—"),
            "cwt_100": table1_raw.get("100", {}).get(rp_key, "—"),
            "cwt_110": table1_raw.get("110", {}).get(rp_key, "—"),
        }
        table1_rows.append(row)

    template_vars = {
        # Cover
        "client":      payload.get("client", "—"),
        "asset":       payload.get("asset",  "—"),
        "test_date":   payload.get("test_date",   "—"),
        "report_date": payload.get("report_date", "—"),
        "report_title": payload.get("report_title", "CT PERFORMANCE EVALUATION REPORT"),
        # Narrative
        "preamble_paragraphs":  payload.get("preamble_paragraphs", []),
        "conclusions":          payload.get("conclusions",          []),
        "suggestions":          payload.get("suggestions",          []),
        "members_client":       payload.get("members_client",       []),
        "members_ssctc":        payload.get("members_ssctc",        []),
        "assessment_method":    payload.get("assessment_method",    []),
        "instrument_placement": payload.get("instrument_placement", []),
        # Data tables
        "final_data_table": payload.get("final_data_table", []),
        "data_notes":       payload.get("data_notes",       []),
        "airflow":          payload.get("airflow",           {}),
        # ATC-105 computed
        "table1_rows": table1_rows,
        "intersect":   intersect,
        "math_results": math_results,
        "test_range":  atc.get("test_range",  "—"),
        "design_range": atc.get("design_range", "—"),
        # Plots
        "plot_1": plot_1_b64,
        "plot_2": plot_2_b64,
    }

    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))

    try:
        template = env.get_template("report_template.html")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF Template Missing: {exc}")

    html_out = template.render(template_vars)

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_out), dest=pdf_buffer)

    if pisa_status.err:
        raise HTTPException(status_code=500, detail="xhtml2pdf error rendering PDF.")

    pdf_buffer.seek(0)
    return pdf_buffer.read()


def _blank_plot(title: str) -> str:
    """Return a base64 placeholder image when no data is available."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, title, ha='center', va='center', fontsize=12, color='gray',
            transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    return _b64_fig(fig)
