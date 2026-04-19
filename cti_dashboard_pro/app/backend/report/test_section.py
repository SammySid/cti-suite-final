"""
test_section.py — ATC-105 per-test flowables (4 pages per test).

Page A — Design vs Recorded (teal sub-bar) + Step 1 (Table 1)
Page B — Step 2: Cross Plot 1 + Table 2 (teal sub-bar)
Page C — Step 3: Calc Panel + Step 4: Cross Plot 2  (same page)
Page D — Step 5: Results table + Result card

build_test_section(ctx, styles) → list of flowables
"""
import io
import base64

from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor

from .helpers import (
    section_bar, sub_bar, step_header,
    data_table, result_card, calc_panel, AVAIL_W,
)
from .styles import (
    NAVY, TEAL, PANEL, PAPER, BORDER2, WHITE, MUTED, BODY,
)

A4_W, A4_H = A4


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(val, dp: int = 2) -> str:
    try:
        f = float(val)
        return f'{f:.{dp}f}'
    except (TypeError, ValueError):
        return str(val) if val not in (None, '') else '\u2014'


def _img(b64_str: str, width: float) -> Image:
    raw = base64.b64decode(b64_str)
    return Image(io.BytesIO(raw), width=width, height=width * 0.46)


# ── Page A — Design vs Recorded + Step 1 ─────────────────────────────────────

def _design_vs_recorded(ctx: dict, styles: dict) -> Table:
    """3-col design-vs-recorded conditions table."""
    try:
        d_app = round(float(ctx.get('design_cwt', 0)) - float(ctx.get('design_wbt', 0)), 2)
    except (TypeError, ValueError):
        d_app = ctx.get('design_approach', '\u2014')
    try:
        t_app = round(float(ctx.get('test_cwt', 0)) - float(ctx.get('test_wbt', 0)), 2)
    except (TypeError, ValueError):
        t_app = ctx.get('test_approach', '\u2014')

    hdr  = ['Parameter', 'Unit', 'Design Conditions', 'Recorded Test Conditions']
    rows = [
        ('Water Flow',      'm\u00b3/hr', _fmt(ctx.get('design_flow')),  _fmt(ctx.get('test_flow'))),
        ('Hot Water Temp',  '\u00b0C',    _fmt(ctx.get('design_hwt')),   _fmt(ctx.get('test_hwt'))),
        ('Cold Water Temp', '\u00b0C',    _fmt(ctx.get('design_cwt')),   _fmt(ctx.get('test_cwt'))),
        ('Wet Bulb Temp',   '\u00b0C',    _fmt(ctx.get('design_wbt')),   _fmt(ctx.get('test_wbt'))),
        ('Range',           '\u00b0C',    _fmt(ctx.get('design_range')), _fmt(ctx.get('test_range'))),
        ('Approach',        '\u00b0C',    _fmt(d_app),                   _fmt(t_app)),
    ]
    cw = [AVAIL_W * 0.28, AVAIL_W * 0.10, AVAIL_W * 0.31, AVAIL_W * 0.31]

    tbl_data = [[Paragraph(h, styles['TblHdr']) for h in hdr]]
    for i, row in enumerate(rows):
        tbl_data.append([
            Paragraph(row[0], styles['TblBodyL']),
            Paragraph(row[1], styles['TblBody']),
            Paragraph(row[2], styles['TblBody']),
            Paragraph(row[3], styles['TblBody']),
        ])

    tbl = Table(tbl_data, colWidths=cw)
    cmds = [
        ('BACKGROUND',    (0, 0), (-1, 0),  TEAL),
        ('BACKGROUND',    (2, 1), (2, -1),  PANEL),
        ('GRID',          (0, 0), (-1, -1), 0.4, BORDER2),
        ('BOX',           (0, 0), (-1, -1), 1.2, NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for i in range(1, len(rows) + 1):
        cmds.append(('BACKGROUND', (0, i), (-1, i), PAPER if i % 2 == 0 else WHITE))
        cmds.append(('BACKGROUND', (2, i), (2, i), PANEL))   # keep design col tinted
    tbl.setStyle(TableStyle(cmds))
    return tbl


def _page_a(ctx: dict, label: str, styles: dict) -> list:
    items = []
    items.append(section_bar(f'ATC-105 PERFORMANCE EVALUATION \u2014 {label}', styles))
    items.append(Spacer(1, 8))

    dr_bar = sub_bar('DESIGN VS RECORDED TEST CONDITIONS', styles)
    dr_tbl = _design_vs_recorded(ctx, styles)
    items.append(KeepTogether([dr_bar, Spacer(1, 2), dr_tbl]))
    items.append(Spacer(1, 12))

    s1_hdr  = step_header('1', 'TABLE 1 \u2014 CWT vs Range at Test WBT', styles)
    s1_desc = Paragraph(
        'Using the Merkel method, predicted Cold Water Temperatures (CWT) are computed '
        'at three fan speeds (90%, 100%, 110% of design flow) for three range values '
        '(80%, 100%, 120% of design range) at the recorded Test Wet Bulb Temperature.',
        styles['StepDesc'],
    )
    items.append(KeepTogether([Spacer(1, 6), s1_hdr, Spacer(1, 9), s1_desc]))

    t1_hdr  = ['Range %', 'Range (\u00b0C)', 'CWT @ 90% Flow', 'CWT @ 100% Flow', 'CWT @ 110% Flow']
    t1_rows = [
        [row.get('range_pct', '\u2014'), row.get('range_abs', '\u2014'),
         row.get('cwt_90', '\u2014'), row.get('cwt_100', '\u2014'), row.get('cwt_110', '\u2014')]
        for row in ctx.get('table1_rows', [])
    ]
    cw_t1 = [AVAIL_W * 0.12, AVAIL_W * 0.18, AVAIL_W * 0.23, AVAIL_W * 0.24, AVAIL_W * 0.23]
    items.append(data_table(t1_hdr, t1_rows, cw_t1, styles))
    items.append(Spacer(1, 6))
    return items


# ── Page B — Step 2: Cross Plot 1 + Table 2 ──────────────────────────────────

def _page_b(ctx: dict, label: str, styles: dict) -> list:
    items = []

    s2_hdr  = step_header('2', 'CROSS PLOT 1 \u2014 CWT vs Range at Test WBT', styles)
    s2_desc = Paragraph(
        'Plot the three CWT lines (90%, 100%, 110% flow) from Table 1 against Range. '
        'Draw a vertical line at the Test Range to read off the CWT for each flow condition. '
        'These three (Flow, CWT) pairs form Table 2.',
        styles['StepDesc'],
    )
    items.append(KeepTogether([s2_hdr, Spacer(1, 9), s2_desc]))
    items.append(Spacer(1, 8))

    plot1_b64 = ctx.get('plot_1')
    if plot1_b64:
        items.append(_img(plot1_b64, AVAIL_W))
        items.append(Paragraph(
            f'Figure 1: Cross Plot 1 \u2014 CWT vs Range at Test WBT \u2014 {label}',
            styles['Caption'],
        ))
    items.append(Spacer(1, 10))

    intersect  = ctx.get('intersect', {})
    test_range = ctx.get('test_range', '\u2014')

    t2_bar = sub_bar(
        f'TABLE 2 \u2014 CWT at Test Range = {_fmt(test_range)} \u00b0C', styles)
    t2_hdr = ['Flow Condition', 'Water Flow (m\u00b3/hr)', f'CWT at Range {_fmt(test_range)}\u00b0C']
    t2_rows = [
        ('90% Flow',  _fmt(ctx.get('flow_90')),  _fmt(intersect.get('f90_cwt'))),
        ('100% Flow', _fmt(ctx.get('flow_100')), _fmt(intersect.get('f100_cwt'))),
        ('110% Flow', _fmt(ctx.get('flow_110')), _fmt(intersect.get('f110_cwt'))),
    ]
    cw_t2 = [AVAIL_W * 0.33, AVAIL_W * 0.33, AVAIL_W * 0.34]
    items.append(KeepTogether([t2_bar, Spacer(1, 2), data_table(t2_hdr, t2_rows, cw_t2, styles)]))
    items.append(Spacer(1, 6))
    return items


# ── Page C — Step 3 (Calc) + Step 4 (Cross Plot 2) ───────────────────────────

def _page_c(ctx: dict, label: str, styles: dict) -> list:
    items = []
    mr        = ctx.get('math_results', {})
    intersect = ctx.get('intersect', {})

    s3_hdr  = step_header('3', 'ADJUSTED WATER FLOW \u2014 Air Density Correction', styles)
    s3_desc = Paragraph(
        'Adjust the recorded water flow for air density differences between test and design '
        'conditions: Q_adj = Q_test \u00d7 (Air Density Ratio)^0.5. '
        'The density ratio accounts for atmospheric variation in air mass flow delivered by the fan.',
        styles['StepDesc'],
    )
    items.append(KeepTogether([s3_hdr, Spacer(1, 9), s3_desc]))
    items.append(Spacer(1, 6))

    fan_d = mr.get('fan_power_design')
    fan_t = mr.get('fan_power_test')

    calc_rows = [
        ('i.    Recorded Test Water Flow (Q_test)',              f'{_fmt(mr.get("test_flow"))} m\u00b3/hr'),
        ('ii.   Air Density Ratio (\u03c1_design / \u03c1_test)', f'{_fmt(mr.get("density_ratio"))}'),
        ('iii.  CWT @ 90% Design Flow (Cross Plot 1)',          f'{_fmt(intersect.get("f90_cwt"))} \u00b0C'),
        ('iv.   CWT @ 100% Design Flow (Cross Plot 1)',         f'{_fmt(intersect.get("f100_cwt"))} \u00b0C'),
        ('v.    CWT @ 110% Design Flow (Cross Plot 1)',         f'{_fmt(intersect.get("f110_cwt"))} \u00b0C'),
        ('vi.   Test Hot Water Temperature (HWT)',              f'{_fmt(mr.get("test_hwt"))} \u00b0C'),
        ('vii.  Test Cold Water Temperature (CWT)',             f'{_fmt(mr.get("test_cwt"))} \u00b0C'),
        ('viii. Test Wet Bulb Temperature (WBT)',               f'{_fmt(mr.get("test_wbt"))} \u00b0C'),
    ]
    if fan_d is not None:
        calc_rows.append(('ix.   Fan Power \u2014 Design', f'{_fmt(fan_d)} kW'))
    if fan_t is not None:
        calc_rows.append(('x.    Fan Power \u2014 Test',   f'{_fmt(fan_t)} kW'))

    total_row = ('Q_adj \u2014 Adjusted Water Flow (Density Corrected)',
                 f'{_fmt(mr.get("adj_flow"))} m\u00b3/hr')
    items.append(calc_panel(calc_rows, total_row, styles))
    items.append(Spacer(1, 14))

    s4_hdr  = step_header('4', 'CROSS PLOT 2 \u2014 Water Flow vs CWT (Design WBT & Range)', styles)
    s4_desc = Paragraph(
        'Plot (Water Flow, CWT) pairs from Table 2. Locate Q_adj on the performance curve '
        'to read the Predicted CWT. Then find the water flow where the curve meets the Design CWT '
        '\u2014 this is the Predicted Flow used in Step 5.',
        styles['StepDesc'],
    )
    items.append(KeepTogether([s4_hdr, Spacer(1, 9), s4_desc]))
    items.append(Spacer(1, 8))

    plot2_b64 = ctx.get('plot_2')
    if plot2_b64:
        items.append(_img(plot2_b64, AVAIL_W))
        items.append(Paragraph(
            f'Figure 2: Cross Plot 2 \u2014 Water Flow vs CWT (Design WBT & Range) \u2014 {label}',
            styles['Caption'],
        ))
    return items


# ── Page D — Step 5 + Result Card ────────────────────────────────────────────

def _page_d(ctx: dict, label: str, styles: dict) -> list:
    items = []
    mr = ctx.get('math_results', {})

    adj_flow   = mr.get('adj_flow',    '\u2014')
    pred_cwt   = mr.get('pred_cwt',    '\u2014')
    test_cwt   = mr.get('test_cwt',    '\u2014')
    pred_flow  = mr.get('pred_flow',   '\u2014')
    shortfall  = mr.get('shortfall',   '\u2014')
    capability = mr.get('capability',  '\u2014')
    density_r  = mr.get('density_ratio', '\u2014')

    items.append(section_bar(f'FINAL ATC-105 RESULTS \u2014 {label}', styles))
    items.append(Spacer(1, 8))

    s5_hdr  = step_header('5', 'FINAL EVALUATION \u2014 CWT Shortfall & Capability', styles)
    s5_desc = Paragraph(
        'Compare the Predicted CWT (from Cross Plot 2 at Q_adj) with the Test CWT. '
        'CWT Shortfall = Test CWT \u2212 Predicted CWT. '
        'A positive shortfall means the tower performed below specification '
        '(actual CWT is higher than the tower should achieve at these conditions). '
        'Capability % = (Q_adj / Predicted Flow) \u00d7 100.',
        styles['StepDesc'],
    )
    items.append(KeepTogether([s5_hdr, Spacer(1, 9), s5_desc]))
    items.append(Spacer(1, 8))

    s5_hdr_row = ['Step', 'Parameter', 'Value']
    s5_rows = [
        ('i',   'Q_adj \u2014 Adjusted Water Flow (density corrected)',              f'{_fmt(adj_flow)} m\u00b3/hr'),
        ('ii',  'Predicted CWT \u2014 from Cross Plot 2 at Q_adj',                   f'{_fmt(pred_cwt)} \u00b0C'),
        ('iii', 'Test CWT \u2014 Recorded during test',                              f'{_fmt(test_cwt)} \u00b0C'),
        ('iv',  'Predicted Water Flow \u2014 at Design CWT on Cross Plot 2',         f'{_fmt(pred_flow)} m\u00b3/hr'),
        ('v',   'CWT Shortfall = Test CWT \u2212 Predicted CWT',                    f'{_fmt(shortfall)} \u00b0C'),
        ('vi',  'Cooling Tower Capability = (Q_adj / Pred. Flow) \u00d7 100',       f'{_fmt(capability)} %'),
        ('vii', 'Air Density Ratio applied',                                          f'{_fmt(density_r)}'),
    ]
    cw_s5 = [AVAIL_W * 0.07, AVAIL_W * 0.61, AVAIL_W * 0.32]
    tbl_data = [[Paragraph(h, styles['TblHdr']) for h in s5_hdr_row]]
    for row in s5_rows:
        tbl_data.append([
            Paragraph(row[0], styles['TblBody']),
            Paragraph(row[1], styles['TblBodyL']),
            Paragraph(row[2], styles['TblBody']),
        ])

    s5_tbl = Table(tbl_data, colWidths=cw_s5)
    cmds = [
        ('BACKGROUND',    (0, 0), (-1, 0),  TEAL),
        ('GRID',          (0, 0), (-1, -1), 0.4, BORDER2),
        ('BOX',           (0, 0), (-1, -1), 1.2, NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        # Shortfall (row 5) and Capability (row 6) value cells — subtle tints
        ('BACKGROUND',    (2, 5), (2, 5),   HexColor('#fff1f2')),
        ('BACKGROUND',    (2, 6), (2, 6),   HexColor('#eff6ff')),
        ('FONTNAME',      (2, 5), (2, 6),   'Helvetica-Bold'),
    ]
    for i in range(1, len(s5_rows) + 1):
        cmds.append(('BACKGROUND', (0, i), (-1, i), PAPER if i % 2 == 0 else WHITE))
    # Re-apply highlights (must come after alternating rows)
    cmds += [
        ('BACKGROUND', (2, 5), (2, 5), HexColor('#fff1f2')),
        ('BACKGROUND', (2, 6), (2, 6), HexColor('#eff6ff')),
    ]
    s5_tbl.setStyle(TableStyle(cmds))
    items.append(s5_tbl)
    items.append(Spacer(1, 14))

    card = result_card(
        label, shortfall, capability,
        adj_flow, pred_flow, test_cwt, pred_cwt,
        styles, AVAIL_W,
    )
    items.extend(card)
    return items


# ── Public API ────────────────────────────────────────────────────────────────

def build_test_section(ctx: dict, styles: dict) -> list:
    """
    Return all flowables for one ATC-105 test (4 pages: A → B → C → D).
    PageBreaks between pages A-B, B-C, C-D are inserted internally.
    No trailing PageBreak — the orchestrator inserts one between tests.
    """
    label = ctx.get('label', 'TEST')
    story = []
    story.extend(_page_a(ctx, label, styles));  story.append(PageBreak())
    story.extend(_page_b(ctx, label, styles));  story.append(PageBreak())
    story.extend(_page_c(ctx, label, styles));  story.append(PageBreak())
    story.extend(_page_d(ctx, label, styles))
    return story
