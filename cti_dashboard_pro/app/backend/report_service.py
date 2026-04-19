import os
import io
import base64
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import numpy as np
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML as WeasyprintHTML
from fastapi import HTTPException

matplotlib.use('Agg')

# ─────────────────────────────────────────────────────────────────────────────
# Shared style constants
# ─────────────────────────────────────────────────────────────────────────────
_FONT  = {'family': 'DejaVu Sans'}
_CLR   = {'90': '#7c3aed', '100': '#16a34a', '110': '#2563eb'}  # purple, green, blue
_RED   = '#dc2626'
_ORG   = '#ea580c'
_CYAN  = '#0891b2'
_GREY  = '#94a3b8'


def _b64_fig(fig):
    """Encode a matplotlib figure as a base64 PNG string and close the figure."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=160, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return b64


def _style_ax(ax, title, xlabel, ylabel):
    """Apply consistent professional styling to an axes object."""
    ax.set_facecolor('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#475569')
    ax.spines['bottom'].set_color('#475569')
    ax.tick_params(colors='#334155', labelsize=9)
    ax.set_title(title, fontsize=11, fontweight='bold', color='#0f172a', pad=14, loc='center')
    ax.set_xlabel(xlabel, fontsize=10, fontweight='bold', color='#0f172a', labelpad=8)
    ax.set_ylabel(ylabel, fontsize=10, fontweight='bold', color='#0f172a', labelpad=8)
    ax.grid(which='major', color='#e2e8f0', linewidth=0.8, zorder=0)
    ax.grid(which='minor', color='#f1f5f9', linestyle=':', linewidth=0.5, zorder=0)
    ax.minorticks_on()


# ─────────────────────────────────────────────────────────────────────────────
# Cross Plot 1: CWT vs Range @ Test WBT
# ─────────────────────────────────────────────────────────────────────────────

def create_cross_plot_1(cp1: dict, label: str = ""):
    """
    Professional Cross Plot 1.
    cp1 keys: ranges_abs, cwt_90, cwt_100, cwt_110,
               test_range, f90_cwt, f100_cwt, f110_cwt
    """
    ranges   = [float(v) for v in cp1["ranges_abs"]]
    cwt_90   = [float(v) for v in cp1["cwt_90"]]
    cwt_100  = [float(v) for v in cp1["cwt_100"]]
    cwt_110  = [float(v) for v in cp1["cwt_110"]]
    test_rng = float(cp1["test_range"])

    v90  = cp1.get("f90_cwt")
    v100 = cp1.get("f100_cwt")
    v110 = cp1.get("f110_cwt")

    title_suffix = f" — {label}" if label else ""
    fig, ax = plt.subplots(figsize=(10, 4.6))
    fig.patch.set_facecolor('white')
    _style_ax(ax,
        title=f"CROSS PLOT 1 — CWT vs RANGE at Test WBT{title_suffix}",
        xlabel="Range (°C)",
        ylabel="Cold Water Temperature (°C)")

    r_fine = np.linspace(ranges[0], ranges[-1], 300)
    for cwts, key, lbl in [(cwt_90,'90','90% Flow'), (cwt_100,'100','100% Flow'), (cwt_110,'110','110% Flow')]:
        clr = _CLR[key]
        c_fine = np.interp(r_fine, ranges, cwts)
        ax.plot(r_fine, c_fine, color=clr, linewidth=2.2, zorder=3)
        ax.plot(ranges, cwts, 'o', color=clr, markersize=6, zorder=4)
        ax.text(ranges[-1] + 0.08, cwts[-1], lbl,
                color=clr, fontsize=8.5, fontweight='bold', va='center', zorder=5)

    all_cwts = cwt_90 + cwt_100 + cwt_110
    y_min = min(all_cwts) - 0.6
    y_max = max(all_cwts) + 0.8
    ax.axvline(x=test_rng, color=_RED, linestyle='-', linewidth=2.2, zorder=3,
               label=f'Test Range = {test_rng:.2f} °C')
    ax.axvspan(test_rng - 0.04, test_rng + 0.04, alpha=0.15, color=_RED, zorder=2)

    annot_data = [
        (v90,  _CLR['90'],  'Purple Line'),
        (v100, _CLR['100'], 'Green Line'),
        (v110, _CLR['110'], 'Blue Line'),
    ]
    offsets = [(0.30, -0.15), (0.30, -0.15), (0.30, 0.15)]
    for idx, (val, clr, _lbl) in enumerate(annot_data):
        if val is None:
            continue
        val = float(val)
        ax.plot(test_rng, val, 'o', color=clr, markersize=10,
                markeredgecolor='white', markeredgewidth=1.5, zorder=6)
        ax.hlines(val, xmin=ranges[0], xmax=test_rng, colors=clr,
                  linestyles='--', linewidth=0.9, alpha=0.5, zorder=2)
        x_txt = test_rng + 0.18
        y_txt = val + offsets[idx][1] * 0.3
        ax.annotate(
            f'{val:.2f} °C',
            xy=(test_rng, val),
            xytext=(x_txt, y_txt),
            fontsize=9.5, color=clr, fontweight='bold',
            ha='left', va='center',
            arrowprops=dict(arrowstyle='-|>', color=clr, lw=1.6,
                            mutation_scale=14, connectionstyle='arc3,rad=0.0'),
            zorder=7,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                      edgecolor=clr, linewidth=1.0, alpha=0.95),
        )

    legend_handles = [
        mpatches.Patch(color=_CLR['90'],  label='90% Flow'),
        mpatches.Patch(color=_CLR['100'], label='100% Flow'),
        mpatches.Patch(color=_CLR['110'], label='110% Flow'),
        mpatches.Patch(color=_RED,        label=f'Test Range = {test_rng:.2f} °C'),
    ]
    ax.legend(handles=legend_handles, loc='upper left', fontsize=8.5,
              frameon=True, framealpha=0.95, edgecolor='#cbd5e1')

    r_pad = (ranges[-1] - ranges[0]) * 0.10
    ax.set_xlim(ranges[0] - 0.3, ranges[-1] + r_pad + 0.8)
    ax.set_ylim(y_min, y_max)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(0.5))

    if v90 and v100 and v110:
        tbl_txt = (
            f"TABLE 2 (@ {test_rng:.2f} °C Range)\n"
            f"  90% Flow : {float(v90):.2f} °C\n"
            f" 100% Flow : {float(v100):.2f} °C\n"
            f" 110% Flow : {float(v110):.2f} °C"
        )
        ax.text(0.985, 0.04, tbl_txt, transform=ax.transAxes,
                fontsize=7.5, va='bottom', ha='right', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#f0fdf4',
                          edgecolor='#16a34a', linewidth=1.0, alpha=0.95))

    plt.tight_layout()
    return _b64_fig(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Cross Plot 2: Water Flow vs CWT
# ─────────────────────────────────────────────────────────────────────────────

def create_cross_plot_2(cp2: dict, label: str = ""):
    """
    Professional Cross Plot 2 with crosshair step annotations.
    """
    flows      = [float(v) for v in cp2["flows"]]
    cwts       = [float(v) for v in cp2["cwts"]]
    adj_flow   = float(cp2["adj_flow"])
    pred_flow  = cp2.get("pred_flow")
    pred_cwt   = cp2.get("pred_cwt")
    test_cwt   = cp2.get("test_cwt")
    design_cwt = cp2.get("design_cwt")

    if pred_flow:  pred_flow  = float(pred_flow)
    if pred_cwt:   pred_cwt   = float(pred_cwt)
    if test_cwt:   test_cwt   = float(test_cwt)
    if design_cwt: design_cwt = float(design_cwt)

    f_min = min(flows) * 0.84
    all_x = list(flows) + ([pred_flow] if pred_flow else [])
    f_max = max(all_x) * 1.10

    xs = np.linspace(f_min, f_max, 600)
    slope_l = (cwts[1] - cwts[0]) / (flows[1] - flows[0])
    slope_r = (cwts[-1] - cwts[-2]) / (flows[-1] - flows[-2])
    ys = np.interp(xs, flows, cwts)
    ys = np.where(xs < flows[0],  cwts[0]  + slope_l * (xs - flows[0]),  ys)
    ys = np.where(xs > flows[-1], cwts[-1] + slope_r * (xs - flows[-1]), ys)

    def curve_cwt_at(flow_val):
        if flow_val <= flows[-1]:
            return float(np.interp(flow_val, flows, cwts))
        return cwts[-1] + slope_r * (flow_val - flows[-1])

    title_suffix = f" — {label}" if label else ""
    fig, ax = plt.subplots(figsize=(10, 4.6))
    fig.patch.set_facecolor('white')
    _style_ax(ax,
        title=f"CROSS PLOT 2 — WATER FLOW vs CWT (Design WBT & Design Range){title_suffix}",
        xlabel="Water Flow (m³/hr)",
        ylabel="Cold Water Temperature (°C)")

    ax.plot(xs, ys, color='#1e293b', linewidth=2.4, zorder=4, label='Performance Curve')
    ax.plot(flows, cwts, 's', color='#1e293b', markersize=7,
            markeredgecolor='white', markeredgewidth=1.2, zorder=5,
            label='Data Points (Table 2)')

    for fl, cw in zip(flows, cwts):
        ax.text(fl, cw + 0.18, f'{cw:.2f}°C', ha='center', va='bottom',
                fontsize=7.5, color='#1e293b', fontweight='bold', zorder=6)

    y_adj = curve_cwt_at(adj_flow)

    ax.vlines(adj_flow, ymin=min(cwts) - 1.5, ymax=y_adj,
              colors=_ORG, linestyles='-', linewidth=2.0, zorder=3)
    ax.plot(adj_flow, y_adj, 'D', color=_ORG, markersize=10,
            markeredgecolor='white', markeredgewidth=1.5, zorder=6)

    if pred_cwt is not None:
        ax.hlines(pred_cwt, xmin=f_min, xmax=adj_flow,
                  colors=_CYAN, linestyles='--', linewidth=1.8, zorder=3)
        ax.plot(adj_flow, pred_cwt, 'o', color=_CYAN, markersize=9,
                markeredgecolor='white', markeredgewidth=1.5, zorder=6)

    if design_cwt is not None and pred_flow is not None:
        ax.hlines(design_cwt, xmin=f_min, xmax=pred_flow,
                  colors=_CLR['90'], linestyles='--', linewidth=1.8, zorder=3)
        ax.vlines(pred_flow, ymin=min(cwts) - 1.5, ymax=design_cwt,
                  colors=_CLR['100'], linestyles='--', linewidth=1.8, zorder=3)
        ax.plot(pred_flow, design_cwt, 'o', color=_CLR['100'], markersize=9,
                markeredgecolor='white', markeredgewidth=1.5, zorder=6)

    if test_cwt is not None:
        ax.hlines(test_cwt, xmin=f_min, xmax=f_max * 0.98,
                  colors=_RED, linestyles='-', linewidth=1.8, zorder=3)

    x_note_right = f_max * 0.98

    ax.annotate(
        f'Adj. Flow\n{adj_flow:.0f} m³/hr',
        xy=(adj_flow, y_adj),
        xytext=(adj_flow - (f_max - f_min) * 0.12, y_adj + 0.6),
        fontsize=8.5, color=_ORG, fontweight='bold', ha='center',
        arrowprops=dict(arrowstyle='-|>', color=_ORG, lw=1.6,
                        mutation_scale=13, connectionstyle='arc3,rad=-0.2'),
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff7ed',
                  edgecolor=_ORG, linewidth=1.0),
        zorder=7,
    )

    if pred_cwt is not None:
        ax.annotate(
            f'Predicted CWT\n{pred_cwt:.2f} °C',
            xy=(f_min + (f_max - f_min) * 0.06, pred_cwt),
            xytext=(f_min + (f_max - f_min) * 0.03, pred_cwt + 0.65),
            fontsize=8.5, color=_CYAN, fontweight='bold', ha='left',
            arrowprops=dict(arrowstyle='-|>', color=_CYAN, lw=1.5, mutation_scale=12),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#ecfeff',
                      edgecolor=_CYAN, linewidth=1.0),
            zorder=7,
        )

    if test_cwt is not None:
        ax.text(x_note_right, test_cwt + 0.12,
                f'Test CWT = {test_cwt:.2f} °C  ←',
                fontsize=8.5, color=_RED, fontweight='bold',
                ha='right', va='bottom', zorder=7,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#fef2f2',
                          edgecolor=_RED, linewidth=1.0, alpha=0.95))

    if pred_flow is not None:
        ax.annotate(
            f'Pred. Flow\n{pred_flow:.0f} m³/hr',
            xy=(pred_flow, design_cwt if design_cwt else cwts[-1]),
            xytext=(pred_flow + (f_max - f_min) * 0.04,
                    (design_cwt if design_cwt else cwts[-1]) - 0.7),
            fontsize=8.5, color=_CLR['100'], fontweight='bold', ha='left',
            arrowprops=dict(arrowstyle='-|>', color=_CLR['100'], lw=1.5, mutation_scale=12),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#f0fdf4',
                      edgecolor=_CLR['100'], linewidth=1.0),
            zorder=7,
        )

    legend_elements = [
        plt.Line2D([0], [0], color='#1e293b', linewidth=2.4, label='Performance Curve (Table 2)'),
        plt.Line2D([0], [0], color=_ORG,  linewidth=2.0, label=f'Adj. Flow = {adj_flow:.0f} m³/hr'),
    ]
    if pred_cwt:
        legend_elements.append(
            plt.Line2D([0], [0], color=_CYAN, linewidth=1.8,
                       linestyle='--', label=f'Pred. CWT = {pred_cwt:.2f} °C'))
    if test_cwt:
        legend_elements.append(
            plt.Line2D([0], [0], color=_RED, linewidth=1.8,
                       label=f'Test CWT = {test_cwt:.2f} °C'))
    if pred_flow:
        legend_elements.append(
            plt.Line2D([0], [0], color=_CLR['100'], linewidth=1.8,
                       linestyle='--', label=f'Pred. Flow = {pred_flow:.0f} m³/hr'))
    ax.legend(handles=legend_elements, loc='upper left', fontsize=8,
              frameon=True, framealpha=0.95, edgecolor='#cbd5e1')

    y_bottom = min(cwts) - 2.0
    y_top    = max(cwts) + 3.5
    if test_cwt:
        y_top = max(y_top, test_cwt + 1.5)
    ax.set_xlim(f_min, f_max)
    ax.set_ylim(y_bottom, y_top)

    def fmt_x(val, pos):
        return f'{val/1000:.2f}'
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(fmt_x))
    ax.set_xlabel("Water Flow (m³/hr × 1000)", fontsize=10, fontweight='bold',
                  color='#0f172a', labelpad=8)
    ax.xaxis.set_major_locator(ticker.AutoLocator())
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

    plt.tight_layout()
    return _b64_fig(fig)


def _blank_plot(title: str) -> str:
    """Return a base64 placeholder image when no data is available."""
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8fafc')
    ax.text(0.5, 0.5, title, ha='center', va='center', fontsize=12, color='#94a3b8',
            transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines[:].set_color('#e2e8f0')
    return _b64_fig(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Per-test context builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_test_context(atc: dict, label: str, design_flow_fallback, _f0) -> dict:
    """
    Build all template variables for one ATC-105 test result.
    Called once per test (pre / post-fan / post-distribution).
    """
    cp1 = atc.get("cross_plot_1", {})
    cp2 = atc.get("cross_plot_2", {})

    if not cp1 or not cp2:
        plot_1_b64 = _blank_plot(f"Cross Plot 1 — {label} — No ATC-105 data provided")
        plot_2_b64 = _blank_plot(f"Cross Plot 2 — {label} — No ATC-105 data provided")
    else:
        plot_1_b64 = create_cross_plot_1(cp1, label)
        plot_2_b64 = create_cross_plot_2(cp2, label)

    flows_m3h = atc.get("flows_m3h", {})
    intersect = {
        "f90_flow":  flows_m3h.get(90,  flows_m3h.get("90",  "—")),
        "f90_cwt":   cp1.get("f90_cwt",  "—"),
        "f100_flow": flows_m3h.get(100, flows_m3h.get("100", "—")),
        "f100_cwt":  cp1.get("f100_cwt", "—"),
        "f110_flow": flows_m3h.get(110, flows_m3h.get("110", "—")),
        "f110_cwt":  cp1.get("f110_cwt", "—"),
    }

    adj_flow   = atc.get("adj_flow",   "—")
    pred_cwt   = atc.get("pred_cwt",   "—")
    pred_flow  = atc.get("pred_flow",  "—")
    shortfall  = atc.get("shortfall",  "—")
    capability = atc.get("capability", "—")
    density_r  = atc.get("density_ratio_used", atc.get("density_ratio", "—"))

    test_cwt_raw = atc.get("test_cwt")
    test_wbt_raw = atc.get("test_wbt")
    test_cwt = test_cwt_raw if test_cwt_raw is not None else cp2.get("test_cwt", "—")

    try:
        test_approach = round(float(test_cwt_raw) - float(test_wbt_raw), 2)
    except (TypeError, ValueError):
        test_approach = "—"

    math_results = {
        "adj_flow":         adj_flow,
        "pred_cwt":         pred_cwt,
        "test_cwt":         test_cwt,
        "test_hwt":         atc.get("test_hwt", "—"),
        "test_approach":    test_approach,
        "shortfall":        shortfall,
        "capability":       capability,
        "density_ratio":    density_r,
        "pred_flow":        pred_flow,
        "test_wbt":         atc.get("test_wbt", "—"),
        "test_flow":        atc.get("test_flow", cp2.get("flows", [None])[0] if cp2.get("flows") else "—"),
        "fan_power_design": atc.get("fan_power_design", None),
        "fan_power_test":   atc.get("fan_power_test",   None),
    }

    table1_raw = atc.get("table1", {})
    ranges_abs = atc.get("ranges_abs", {})
    table1_rows = []

    def _fmt(val):
        try:
            return f"{float(val):.2f}"
        except (TypeError, ValueError):
            return str(val) if val else "—"

    for rp_key, rp_label in [("80", "80%"), ("100", "100%"), ("120", "120%")]:
        abs_rng = ranges_abs.get(int(rp_key), ranges_abs.get(rp_key, "—"))
        row = {
            "range_pct": rp_label,
            "range_abs": f"{abs_rng} °C" if abs_rng != "—" else "—",
            "cwt_90":  _fmt(table1_raw.get("90",  {}).get(rp_key)),
            "cwt_100": _fmt(table1_raw.get("100", {}).get(rp_key)),
            "cwt_110": _fmt(table1_raw.get("110", {}).get(rp_key)),
        }
        table1_rows.append(row)

    design_flow = atc.get("design_flow", design_flow_fallback)
    try:
        df_num = float(design_flow)
    except (TypeError, ValueError):
        df_num = 0.0

    try:
        design_approach = round(float(atc.get("design_cwt", 0)) - float(atc.get("design_wbt", 0)), 2)
    except (TypeError, ValueError):
        design_approach = "—"

    return {
        "label":           label,
        "design_approach": design_approach,
        "plot_1":       plot_1_b64,
        "plot_2":       plot_2_b64,
        "table1_rows":  table1_rows,
        "intersect":    intersect,
        "math_results": math_results,
        "test_range":   atc.get("test_range",   "—"),
        "design_range": atc.get("design_range", "—"),
        "test_wbt":     atc.get("test_wbt",     "—"),
        "design_wbt":   atc.get("design_wbt",   "—"),
        "design_cwt":   atc.get("design_cwt",   "—"),
        "design_hwt":   atc.get("design_hwt",   "—"),
        "design_flow":  design_flow,
        "test_cwt":     test_cwt,
        "test_hwt":     atc.get("test_hwt",     "—"),
        "test_flow":    atc.get("test_flow",    "—"),
        "test_approach": test_approach,
        "flow_90":      _f0(df_num * 0.9),
        "flow_100":     _f0(df_num),
        "flow_110":     _f0(df_num * 1.1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main PDF generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf_report(payload: dict):
    """
    Render the Jinja2 HTML report template and convert to PDF bytes.

    Payload must include THREE separate ATC-105 results:
      - atc105_pre  : Pre-test ATC-105 result
      - atc105_post : Post fan-change ATC-105 result
      - atc105_dist : Post distribution-change ATC-105 result

    Legacy: if only 'atc105' is present it is treated as the distribution test.
    """
    # ── Format helpers ────────────────────────────────────────────────────────
    def _f2(v, unit=""):
        try:
            return f"{float(v):.2f}{unit}"
        except (TypeError, ValueError):
            return str(v)

    def _f1(v, unit=""):
        try:
            return f"{float(v):.1f}{unit}"
        except (TypeError, ValueError):
            return str(v)

    def _f0(v, unit=""):
        try:
            return f"{float(v):.0f}{unit}"
        except (TypeError, ValueError):
            return str(v)

    # ── Resolve the three test results ───────────────────────────────────────
    atc_pre  = payload.get("atc105_pre")
    atc_post = payload.get("atc105_post")
    atc_dist = payload.get("atc105_dist")

    # Backward-compatibility: single 'atc105' key → treat as distribution test
    if not atc_pre and not atc_post and not atc_dist:
        atc_dist = payload.get("atc105", {})

    primary = atc_dist or atc_post or atc_pre or {}
    design_flow_fallback = primary.get("design_flow", "—")

    # ── Build per-test contexts (generates plots for each) ───────────────────
    tests = []
    test_labels = [
        (atc_pre,  "TEST 1 — PRE TEST"),
        (atc_post, "TEST 2 — POST FAN CHANGE"),
        (atc_dist, "TEST 3 — POST DISTRIBUTION CHANGE"),
    ]
    for atc, label in test_labels:
        if atc:
            tests.append(_build_test_context(atc, label, design_flow_fallback, _f0))

    # ── Template variables ────────────────────────────────────────────────────
    template_vars = {
        # Cover
        "client":       payload.get("client",       "—"),
        "asset":        payload.get("asset",        "—"),
        "test_date":    payload.get("test_date",    "—"),
        "report_date":  payload.get("report_date",  "—"),
        "report_title": payload.get("report_title", "CT PERFORMANCE EVALUATION REPORT"),
        # Narrative
        "preamble_paragraphs":  payload.get("preamble_paragraphs",  []),
        "conclusions":          payload.get("conclusions",           []),
        "suggestions":          payload.get("suggestions",           []),
        "members_client":       payload.get("members_client",        []),
        "members_ssctc":        payload.get("members_ssctc",         []),
        "assessment_method":    payload.get("assessment_method",     []),
        "instrument_placement": payload.get("instrument_placement",  []),
        # Comparison data
        "final_data_table": payload.get("final_data_table", []),
        "data_notes":       payload.get("data_notes",       []),
        "airflow":          payload.get("airflow",           {}),
        # Shared design conditions (same for all tests)
        "design_flow":  primary.get("design_flow",  "—"),
        "design_hwt":   primary.get("design_hwt",   "—"),
        "design_cwt":   primary.get("design_cwt",   "—"),
        "design_wbt":   primary.get("design_wbt",   "—"),
        "design_range": primary.get("design_range", "—"),
        # All three test analyses (each has label, plots, tables, math_results)
        "tests": tests,
        # Format helpers available in Jinja2 template
        "_f2": _f2,
        "_f1": _f1,
        "_f0": _f0,
    }

    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,    # strip newline after block tags  → cleaner output
        lstrip_blocks=True,  # strip leading whitespace before block tags
    )

    try:
        template = env.get_template("report_template.html")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF Template Missing: {exc}")

    html_out = template.render(template_vars)

    try:
        pdf_bytes = WeasyprintHTML(
            string=html_out,
            base_url=template_dir,   # allows relative image/font URLs if ever needed
        ).write_pdf()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WeasyPrint PDF render error: {exc}")

    return pdf_bytes
