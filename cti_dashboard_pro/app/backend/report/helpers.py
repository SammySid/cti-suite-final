"""
helpers.py — Reusable ReportLab flowable builders.

Design tokens (imported from styles):
  NAVY  — section bars (deep navy + 4 pt teal left accent)
  TEAL  — sub-bars, data-table headers, step badges
  GOLD  — conclusion-card accent bar
  SKY   — summary-bar bg
  PANEL — step-header right cell bg, calc-panel bg
"""
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor

from .styles import (
    NAVY, TEAL, GOLD, SKY, PANEL, PAPER, BORDER, BORDER2,
    BODY, MUTED, RED, BLUE, WHITE,
)

A4_W, _ = A4
L_MARGIN = R_MARGIN = 48.0          # slightly narrower for more content width
T_MARGIN = 52.0
B_MARGIN = 44.0
AVAIL_W  = A4_W - L_MARGIN - R_MARGIN   # ≈ 499 pt


# ── Section bar (navy + teal left accent) ─────────────────────────────────────

def section_bar(text: str, styles: dict) -> Table:
    """Full-width navy bar with a 4 pt teal left accent stripe."""
    t = Table([[Paragraph(text, styles['SectionBar'])]], colWidths=[AVAIL_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 14),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('LINEBEFORE',    (0, 0), (0, -1),  4, TEAL),
    ]))
    return t


# ── Sub-section bar (solid teal, bold white text) ─────────────────────────────

def sub_bar(text: str, styles: dict) -> Table:
    """Solid teal bar — fully readable, strong visual hierarchy."""
    t = Table([[Paragraph(text, styles['SubBar'])]], colWidths=[AVAIL_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), TEAL),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
    ]))
    return t


# ── Step header (horizontal badge + title) ────────────────────────────────────

def step_header(step_num: str, title_text: str, styles: dict) -> Table:
    """
    Teal "STEP N" badge on the left, pale-blue title panel on the right.
    Rendered as a single horizontal row — no vertical stacking.
    """
    badge = Paragraph(f'STEP {step_num}', styles['StepBadge'])
    title = Paragraph(title_text, styles['StepTitle'])
    t = Table([[badge, title]], colWidths=[56, AVAIL_W - 56])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, 0), TEAL),
        ('BACKGROUND',    (1, 0), (1, 0), PANEL),
        ('LEFTPADDING',   (0, 0), (0, 0), 6),
        ('RIGHTPADDING',  (0, 0), (0, 0), 6),
        ('LEFTPADDING',   (1, 0), (1, 0), 14),
        ('RIGHTPADDING',  (1, 0), (1, 0), 10),
        ('LINEBEFORE',    (1, 0), (1, 0), 3, TEAL),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return t


# ── Data table (teal header + alternating rows) ───────────────────────────────

def data_table(
    header_row: list,
    data_rows: list,
    col_widths: list,
    styles: dict,
    alt_bg=None,
) -> Table:
    """
    Styled table: teal header row, alternating PAPER / WHITE body rows.
    First column of each body row is left-aligned; rest centred.
    """
    alt_bg = alt_bg or PAPER

    tbl_data = [[Paragraph(str(h), styles['TblHdr']) for h in header_row]]
    for row in data_rows:
        styled = [
            Paragraph(str(c) if c not in (None, '') else '—',
                      styles['TblBodyL'] if j == 0 else styles['TblBody'])
            for j, c in enumerate(row)
        ]
        tbl_data.append(styled)

    tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)
    cmds = [
        ('BACKGROUND',    (0, 0), (-1, 0),  TEAL),
        ('GRID',          (0, 0), (-1, -1), 0.4, BORDER2),
        ('BOX',           (0, 0), (-1, -1), 1.2, NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for i in range(1, len(data_rows) + 1):
        cmds.append(('BACKGROUND', (0, i), (-1, i), alt_bg if i % 2 == 0 else WHITE))
    tbl.setStyle(TableStyle(cmds))
    return tbl


# ── Calculation panel (Step 3) ────────────────────────────────────────────────

def calc_panel(rows: list, total_row: tuple, styles: dict, w: float = AVAIL_W) -> Table:
    """
    Light-panel bordered table for Step 3 inputs.
    rows      — list of (label, value) strings
    total_row — (label, value) rendered in teal-header style as the total row
    """
    col_w1, col_w2 = w * 0.70, w * 0.30
    tbl_data = [
        [Paragraph(lbl, styles['CalcLabel']), Paragraph(str(val), styles['CalcValue'])]
        for lbl, val in rows
    ]
    n = len(rows)
    tbl_data.append([
        Paragraph(total_row[0], styles['TblHdr']),
        Paragraph(str(total_row[1]), styles['TblHdr']),
    ])
    tbl = Table(tbl_data, colWidths=[col_w1, col_w2])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0),  (-1, n - 1), PANEL),
        ('BACKGROUND',    (0, n),  (-1, n),     TEAL),
        ('GRID',          (0, 0),  (-1, -1),    0.4, BORDER2),
        ('BOX',           (0, 0),  (-1, n),     1.2, NAVY),
        ('TOPPADDING',    (0, 0),  (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0),  (-1, -1), 4),
        ('LEFTPADDING',   (0, 0),  (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0),  (-1, -1), 8),
        ('VALIGN',        (0, 0),  (-1, -1), 'MIDDLE'),
    ]))
    return tbl


# ── Result card (conclusion box) ──────────────────────────────────────────────

def result_card(
    test_label: str,
    shortfall, capability, adj_flow, pred_flow, test_cwt, pred_cwt,
    styles: dict, w: float = AVAIL_W,
) -> list:
    """
    Returns [header_table, body_table, summary_bar] — three flowables.
    Header has a 4 pt gold left accent. Shortfall in red, Capability in blue.
    """
    def _safe(val, dp=2):
        try:    return f'{float(val):.{dp}f}'
        except: return str(val) if val not in (None, '') else '—'

    sf_disp  = f"{float(shortfall):+.2f} °C" if _safe(shortfall) != '—' else '— °C'
    cap_disp = f"{_safe(capability, 1)} %"

    # Header bar (navy + gold left accent)
    header = Table(
        [[Paragraph(f'CONCLUSION \u2014 {test_label}', styles['CardHeader'])]],
        colWidths=[w],
    )
    header.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 16),
        ('LINEBEFORE',    (0, 0), (0, -1),  4, GOLD),
    ]))

    # Two-column body
    col_w = w / 2
    left_cells = [
        Paragraph('CWT SHORTFALL IN PERFORMANCE', styles['RcLabel']),
        Paragraph(sf_disp, styles['RcValueRed']),
        Paragraph(f'Test CWT ({_safe(test_cwt)}°C) vs Predicted CWT ({_safe(pred_cwt)}°C)', styles['RcSub']),
    ]
    right_cells = [
        Paragraph('COOLING TOWER CAPABILITY', styles['RcLabel']),
        Paragraph(cap_disp, styles['RcValueBlue']),
        Paragraph(f'= {_safe(adj_flow, 0)} / {_safe(pred_flow, 0)} \u00d7 100', styles['RcSub']),
    ]
    body = Table([[left_cells, right_cells]], colWidths=[col_w, col_w])
    body.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), PANEL),
        ('LINEBEFORE',    (1, 0), (1, -1),  1.5, HexColor('#7dd3fc')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 18),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 18),
        ('LEFTPADDING',   (0, 0), (-1, -1), 18),
        ('BOX',           (0, 0), (-1, -1), 1.2, NAVY),
    ]))

    # Summary bar
    try:
        sf_val  = float(shortfall)
        cap_val = float(capability)
        # Shortfall = Test CWT − Predicted CWT.
        # Positive → actual CWT higher than predicted → tower underperforming (below spec).
        # Negative → actual CWT lower than predicted → tower exceeding specification.
        if sf_val > 0:
            txt = (f'Tower is <b>BELOW specification</b> by {sf_val:.2f}°C '
                   f'\u2014 Capability: <b>{cap_val:.1f}%</b>')
        elif sf_val == 0:
            txt = f'Tower <b>MEETS design specification</b> \u2014 Capability: <b>{cap_val:.1f}%</b>'
        else:
            txt = (f'Tower <b>EXCEEDS design specification</b> by {abs(sf_val):.2f}°C '
                   f'\u2014 Capability: <b>{cap_val:.1f}%</b>')
    except (TypeError, ValueError):
        txt = 'ATC-105 Analysis Complete'

    summary = Table(
        [[Paragraph(txt, styles['ResultSummary'])]],
        colWidths=[w],
    )
    summary.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), SKY),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('BOX',           (0, 0), (-1, -1), 1.0, TEAL),
    ]))

    return [header, body, summary]
