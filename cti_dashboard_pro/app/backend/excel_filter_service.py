from io import BytesIO
import os
import re
from datetime import datetime

import pandas as pd
from dateutil import parser
from typing import List, Dict, Any


def _parse_user_time(time_str):
    """Parse a user-supplied time string. Returns None if the string is empty (meaning 'no filter')."""
    value = str(time_str or '').strip().lower().replace('.', ':')
    if not value:
        return None  # Signals 'process all rows' – no time filter applied

    if re.match(r'^\d{1,2}(:00)?$', value):
        hour = int(value.split(':')[0])
        if 1 <= hour <= 7:
            value = f'{hour + 12}:00'
        else:
            value = f'{hour}:00'

    return parser.parse(value).time()


def _find_header_row(preview_df):
    for idx, row in preview_df.head(30).iterrows():
        for cell in row.values:
            if str(cell).strip().lower() == 'time':
                return idx
    return None


def _get_time_column(df):
    for col in df.columns:
        if str(col).strip().lower() == 'time':
            return col
    return None


def _read_excel_bytes(file_bytes, engine=None):
    """Read excel bytes into a DataFrame, trying the given engine first."""
    kwargs = {}
    if engine:
        kwargs['engine'] = engine
    return pd.read_excel(BytesIO(file_bytes), **kwargs)


def _read_excel_with_time_header(file_bytes, engine=None):
    """Read an Excel file (any engine) and locate the 'Time' column.
    Returns (df, time_col) where time_col may be None if not found.
    """
    first_pass = _read_excel_bytes(file_bytes, engine=engine)
    time_col = _get_time_column(first_pass)
    if time_col:
        return first_pass, time_col

    preview = pd.read_excel(BytesIO(file_bytes), header=None, nrows=30, **(({'engine': engine}) if engine else {}))
    header_idx = _find_header_row(preview)
    if header_idx is None:
        return first_pass, None  # Return the df anyway; time col just absent

    adjusted = pd.read_excel(BytesIO(file_bytes), header=header_idx, **(({'engine': engine}) if engine else {}))
    return adjusted, _get_time_column(adjusted)


def _parse_times(series):
    parsed = pd.to_datetime(series, format='%H:%M:%S', errors='coerce').dt.time
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(series.loc[missing].astype(str), errors='coerce').dt.time
    return parsed


def _style_sheet(writer, sheet_name, df):
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    header_fmt = workbook.add_format({
        'bold': True,
        'font_color': '#0F172A',
        'bg_color': '#DBEAFE',
        'border': 1,
        'border_color': '#BFDBFE',
        'align': 'center',
        'valign': 'vcenter'
    })
    data_fmt = workbook.add_format({
        'border': 1,
        'border_color': '#E2E8F0'
    })

    worksheet.freeze_panes(1, 0)
    worksheet.set_zoom(115)

    for col_idx, col_name in enumerate(df.columns):
        worksheet.write(0, col_idx, col_name, header_fmt)
        max_len = max(len(str(col_name)), df[col_name].astype(str).str.len().max() if not df.empty else 0)
        worksheet.set_column(col_idx, col_idx, min(max(max_len + 2, 12), 35), data_fmt)

    if len(df.columns) > 0 and len(df.index) > 0:
        worksheet.autofilter(0, 0, len(df.index), len(df.columns) - 1)


def _merge_sensor_dfs(dfs, date_col, time_col):
    if not dfs:
        return pd.DataFrame()

    working: List[Any] = []
    for df in dfs:
        copy_df = df.copy()
        dt_str = copy_df[date_col].astype(str) + ' ' + copy_df[time_col].astype(str)
        merge_key = pd.to_datetime(dt_str, dayfirst=True, errors='coerce').dt.floor('min')
        copy_df['_merge_key'] = merge_key
        
        # When falling back for unparseable dates, combine date and time string so dates don't mix
        fallback = copy_df[date_col].astype(str).str.strip() + '_' + copy_df[time_col].astype(str).str[:5]
        copy_df.loc[copy_df['_merge_key'].isna(), '_merge_key'] = fallback.loc[copy_df['_merge_key'].isna()]
        working.append(copy_df)

    merged = working[0]
    for df in working[1:]:
        merged = pd.merge(merged, df, on='_merge_key', how='outer', suffixes=('', '_y'))
        merged[date_col] = merged[date_col].combine_first(merged[date_col + '_y'])
        merged[time_col] = merged[time_col].combine_first(merged[time_col + '_y'])
        merged.drop(columns=[date_col + '_y', time_col + '_y'], inplace=True)

    merged.sort_values(by='_merge_key', inplace=True)
    merged.drop(columns=['_merge_key'], inplace=True)
    merged.reset_index(drop=True, inplace=True)
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Helper: smart sensor label for generic (non-CWT/HWT) files
# ─────────────────────────────────────────────────────────────────────────────

def _extract_generic_sensor_id(file_name):
    """Best-effort short label from a filename with no CWT/HWT/DBT/WBT tag.
    Produces labels like 'Q1_A', 'Q2_B', 'Cell_C', or a fallback number.
    """
    stem = os.path.splitext(file_name)[0]
    # Pattern: "2nd quadrant reading Cell B …" → "Q2_B"
    quad = re.search(r'(\d+)\s*(?:st|nd|rd|th)\s+quadrant', stem, re.IGNORECASE)
    cell = re.search(r'[Cc]ell\s+([A-Za-z0-9]+)', stem)
    if quad and cell:
        return f"Q{quad.group(1)}_{cell.group(1)}"
    if cell:
        return f"Cell_{cell.group(1)}"
    # Fall back: 2+-digit number block
    matches = re.findall(r'\d{2,}', stem)
    if matches:
        return max(matches, key=lambda x: (len(x), int(x)))
    # Last resort: clean up the stem
    clean = re.sub(r'\s+', '_', stem.strip())
    return clean[:18] if len(clean) > 18 else clean


# ─────────────────────────────────────────────────────────────────────────────
# Report Layout
# ─────────────────────────────────────────────────────────────────────────────

def _create_report_layout(writer, master_df, sheet_name='Report Layout'):
    if master_df.empty:
        return

    date_col = next((c for c in master_df.columns if 'date' in str(c).lower()), None)
    time_col = next((c for c in master_df.columns if 'time' in str(c).lower()), None)
    if not date_col or not time_col:
        return

    # Primary value column (NTC / anything with 'value')
    val_col = next((c for c in master_df.columns if 'ntc' in str(c).lower() or 'value' in str(c).lower()), None)
    if not val_col:
        val_col = next(
            (
                c for c in master_df.columns
                if c not in ['Source File', date_col, time_col] and pd.api.types.is_numeric_dtype(master_df[c])
            ),
            None
        )
    if not val_col:
        return

    # ── Categorise source files ─────────────────────────────────────────────
    cwt_dfs: List[Any] = []
    hwt_dfs: List[Any] = []
    dbt_dfs: List[Any] = []
    wbt_dfs: List[Any] = []
    unclassified_dfs: List[Any] = []   # files whose names lack CWT/HWT/DBT/WBT
    seen_sensors: set = set()

    for file_name, group in master_df.groupby('Source File'):
        lower_name = file_name.lower()
        is_classified = any(k in lower_name for k in ('cwt', 'hwt', 'dbt', 'wbt'))

        # Sensor ID
        if is_classified:
            matches = re.findall(r'\d{2,}', file_name) or re.findall(r'\d+', file_name)
            base_sensor = max(matches, key=lambda x: (len(x), int(x))) if matches else file_name.split('.')[0]
        else:
            base_sensor = _extract_generic_sensor_id(file_name)

        sensor_no = base_sensor
        counter = 1
        while sensor_no in seen_sensors:
            sensor_no = f"{base_sensor}_{counter}"
            counter += 1
        seen_sensors.add(sensor_no)

        subset = group[[date_col, time_col, val_col]].copy()
        subset.rename(columns={val_col: sensor_no}, inplace=True)
        subset[time_col] = subset[time_col].astype(str).str.split('.').str[0]
        if pd.api.types.is_datetime64_any_dtype(subset[date_col]):
            subset[date_col] = subset[date_col].dt.strftime('%d-%m-%Y')

        if 'cwt' in lower_name:
            cwt_dfs.append(subset)
        elif 'hwt' in lower_name:
            hwt_dfs.append(subset)
        elif 'dbt' in lower_name:
            dbt_dfs.append(subset)
        elif 'wbt' in lower_name:
            wbt_dfs.append(subset)
        else:
            unclassified_dfs.append(subset)

    water_df   = _merge_sensor_dfs(cwt_dfs + hwt_dfs, date_col, time_col)
    air_df     = _merge_sensor_dfs(dbt_dfs + wbt_dfs, date_col, time_col)
    generic_df = _merge_sensor_dfs(unclassified_dfs, date_col, time_col)

    if water_df.empty and air_df.empty and generic_df.empty:
        return

    # ── Common format objects ───────────────────────────────────────────────
    workbook = writer.book
    safe_sheet_name = sheet_name[:31]
    worksheet = workbook.add_worksheet(safe_sheet_name)

    title_fmt       = workbook.add_format({'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter', 'border': 1})
    cwt_header_fmt  = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#BDD7EE'})
    hwt_header_fmt  = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FCE4D6'})
    dbt_header_fmt  = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#EDEDED'})
    wbt_header_fmt  = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FFF2CC'})
    vel_header_fmt  = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#BDD7EE'})
    temp_header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FCE4D6'})
    date_time_fmt   = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FFF59D'})
    sensor_fmt      = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FFF59D'})
    data_fmt        = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'num_format': '0.00'})
    str_data_fmt    = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
    avg_label_fmt   = workbook.add_format({'bold': True, 'align': 'right', 'valign': 'vcenter', 'border': 1, 'bg_color': '#D9D9D9'})
    avg_val_fmts = {
        'cwt':     workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#BDD7EE', 'num_format': '0.00'}),
        'hwt':     workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FCE4D6', 'num_format': '0.00'}),
        'dbt':     workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#EDEDED', 'num_format': '0.00'}),
        'wbt':     workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FFF2CC', 'num_format': '0.00'}),
        'vel':     workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#BDD7EE', 'num_format': '0.00'}),
        'temp':    workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#FCE4D6', 'num_format': '0.00'}),
        'default': workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#E2EFDA', 'num_format': '0.00'}),
    }

    # ══════════════════════════════════════════════════════════════════════════
    # GENERIC LAYOUT  – fan / anemometer / any non-CWT/HWT/DBT/WBT data
    # ══════════════════════════════════════════════════════════════════════════
    if not generic_df.empty and water_df.empty and air_df.empty:
        gen_sensor_cols = [c for c in generic_df.columns if c not in [date_col, time_col]]

        # Try to find a secondary numeric column (e.g. Tem_Value alongside Main_Value)
        secondary_val_col = next(
            (
                c for c in master_df.columns
                if c not in ['Source File', date_col, time_col, val_col]
                and pd.api.types.is_numeric_dtype(master_df[c])
                and 'no' not in c.lower()    # skip row-number columns like 'NO'
            ),
            None
        )

        # Build secondary (temperature) DF with same sensor IDs
        secondary_df = pd.DataFrame()
        sec_sensor_cols: List[str] = []
        if secondary_val_col:
            sec_dfs: List[Any] = []
            seen_sec: set = set()
            for file_name, group in master_df.groupby('Source File'):
                sec_id = _extract_generic_sensor_id(file_name)
                sno = sec_id
                sc = 1
                while sno in seen_sec:
                    sno = f"{sec_id}_{sc}"
                    sc += 1
                seen_sec.add(sno)
                s = group[[date_col, time_col, secondary_val_col]].copy()
                s.rename(columns={secondary_val_col: sno}, inplace=True)
                s[time_col] = s[time_col].astype(str).str.split('.').str[0]
                if pd.api.types.is_datetime64_any_dtype(s[date_col]):
                    s[date_col] = s[date_col].dt.strftime('%d-%m-%Y')
                sec_dfs.append(s)
            secondary_df = _merge_sensor_dfs(sec_dfs, date_col, time_col)
            sec_sensor_cols = [c for c in secondary_df.columns if c not in [date_col, time_col]]

        # ── Column layout dimensions ────────────────────────────────────────
        n_vel   = len(gen_sensor_cols)
        n_temp  = len(sec_sensor_cols)
        vel_start  = 2                                      # after Date + Time
        vel_end    = vel_start + n_vel - 1
        # Temperature section: skip 2 cols (Date + Time) after velocity section
        temp_start: Any = (vel_end + 3) if n_temp > 0 else None
        temp_end: Any   = (temp_start + n_temp - 1) if (n_temp > 0 and temp_start is not None) else None
        total_cols = vel_start + n_vel + (2 + n_temp if n_temp > 0 else 0)

        # ── Title ───────────────────────────────────────────────────────────
        worksheet.merge_range(0, 0, 0, total_cols - 1, 'Performance Test Consolidated Report', title_fmt)

        # ── Velocity section (row 1 + row 2) ────────────────────────────────
        worksheet.write(1, 0, 'Date', date_time_fmt)
        worksheet.write(1, 1, 'Time', date_time_fmt)
        vel_label = f'Velocity / Main Value  [{val_col}]'
        if n_vel > 1:
            worksheet.merge_range(1, vel_start, 1, vel_end, vel_label, vel_header_fmt)
        else:
            worksheet.write(1, vel_start, vel_label, vel_header_fmt)
        worksheet.merge_range(2, 0, 2, 1, 'Sensor No.', sensor_fmt)
        for ci, col_name in enumerate(gen_sensor_cols):
            worksheet.write(2, vel_start + ci, col_name, sensor_fmt)

        # ── Temperature section (row 1 + row 2) ─────────────────────────────
        if n_temp > 0 and temp_start is not None and temp_end is not None:
            worksheet.write(1, temp_start - 2, 'Date', date_time_fmt)
            worksheet.write(1, temp_start - 1, 'Time', date_time_fmt)
            temp_label = f'Temperature  [{secondary_val_col}]'
            if n_temp > 1:
                worksheet.merge_range(1, temp_start, 1, temp_end, temp_label, temp_header_fmt)
            else:
                worksheet.write(1, temp_start, temp_label, temp_header_fmt)
            worksheet.merge_range(2, temp_start - 2, 2, temp_start - 1, 'Sensor No.', sensor_fmt)
            for ci, col_name in enumerate(sec_sensor_cols):
                worksheet.write(2, temp_start + ci, col_name, sensor_fmt)

        # ── Data rows ────────────────────────────────────────────────────────
        max_rows_gen = max(
            len(generic_df),
            len(secondary_df) if not secondary_df.empty else 0
        )

        def _write_cell(ws, row, col, val, num_fmt, s_fmt):
            if pd.isna(val) or str(val).lower() == 'nan':
                ws.write_string(row, col, '', s_fmt)
            else:
                try:
                    ws.write_number(row, col, float(val), num_fmt)
                except (TypeError, ValueError):
                    ws.write_string(row, col, str(val), s_fmt)

        for r_idx in range(max_rows_gen):
            target_row = r_idx + 3
            # Velocity rows
            if r_idx < len(generic_df):
                g_row = generic_df.iloc[r_idx]
                dv = g_row.get(date_col, '')
                worksheet.write_string(target_row, 0,
                    '' if (pd.isna(dv) or str(dv).lower() == 'nan') else str(dv), str_data_fmt)
                tv = g_row.get(time_col, '')
                worksheet.write_string(target_row, 1,
                    '' if (pd.isna(tv) or str(tv).lower() == 'nan') else str(tv), str_data_fmt)
                for ci, col_name in enumerate(gen_sensor_cols):
                    _write_cell(worksheet, target_row, vel_start + ci, g_row.get(col_name), data_fmt, str_data_fmt)
            # Temperature rows
            if n_temp > 0 and not secondary_df.empty and temp_start is not None and r_idx < len(secondary_df):
                s_row = secondary_df.iloc[r_idx]
                dv2 = s_row.get(date_col, '')
                worksheet.write_string(target_row, temp_start - 2,
                    '' if (pd.isna(dv2) or str(dv2).lower() == 'nan') else str(dv2), str_data_fmt)
                tv2 = s_row.get(time_col, '')
                worksheet.write_string(target_row, temp_start - 1,
                    '' if (pd.isna(tv2) or str(tv2).lower() == 'nan') else str(tv2), str_data_fmt)
                for ci, col_name in enumerate(sec_sensor_cols):
                    _write_cell(worksheet, target_row, temp_start + ci, s_row.get(col_name), data_fmt, str_data_fmt)

        worksheet.set_column(0, max(total_cols - 1, 0), 13)

        # ── Average rows ─────────────────────────────────────────────────────
        avg_row_idx       = max_rows_gen + 4
        total_avg_row_idx = max_rows_gen + 5

        # Velocity section labels
        worksheet.write(avg_row_idx,       0, '', avg_label_fmt)
        worksheet.write(avg_row_idx,       1, 'Average',       avg_label_fmt)
        worksheet.write(total_avg_row_idx, 0, '', avg_label_fmt)
        worksheet.write(total_avg_row_idx, 1, 'Total Average', avg_label_fmt)
        # Temperature section labels
        if n_temp > 0 and temp_start is not None:
            worksheet.write(avg_row_idx,       temp_start - 2, '', avg_label_fmt)
            worksheet.write(avg_row_idx,       temp_start - 1, 'Average',       avg_label_fmt)
            worksheet.write(total_avg_row_idx, temp_start - 2, '', avg_label_fmt)
            worksheet.write(total_avg_row_idx, temp_start - 1, 'Total Average', avg_label_fmt)

        def _write_section_avgs(df, cols, col_offset, avg_fmt_key):
            avgs = []
            fmt = avg_val_fmts[avg_fmt_key]
            for ci, col_name in enumerate(cols):
                series = pd.to_numeric(df[col_name], errors='coerce')
                avg_val = series.mean()
                if pd.notna(avg_val):
                    worksheet.write_number(avg_row_idx, col_offset + ci, float(avg_val), fmt)
                    avgs.append(avg_val)
                else:
                    worksheet.write_string(avg_row_idx, col_offset + ci, '-', fmt)
            overall = sum(avgs) / len(avgs) if avgs else None
            if len(cols) > 1:
                val = float(overall) if overall is not None else '-'
                worksheet.merge_range(total_avg_row_idx, col_offset, total_avg_row_idx,
                                      col_offset + len(cols) - 1, val, fmt)
            elif len(cols) == 1:
                if overall is not None:
                    worksheet.write_number(total_avg_row_idx, col_offset, float(overall), fmt)
                else:
                    worksheet.write_string(total_avg_row_idx, col_offset, '-', fmt)

        _write_section_avgs(generic_df, gen_sensor_cols, vel_start, 'vel')
        if n_temp > 0 and not secondary_df.empty and temp_start is not None:
            _write_section_avgs(secondary_df, sec_sensor_cols, temp_start, 'temp')

        return   # ← done with generic layout

    # ══════════════════════════════════════════════════════════════════════════
    # EXISTING CWT / HWT / DBT / WBT LAYOUT  (behaviour unchanged)
    # ══════════════════════════════════════════════════════════════════════════
    cwt_cols = sorted([c for df in cwt_dfs for c in df.columns if c not in [date_col, time_col, '_merge_key']])
    hwt_cols = sorted([c for df in hwt_dfs for c in df.columns if c not in [date_col, time_col, '_merge_key']])
    dbt_cols = sorted([c for df in dbt_dfs for c in df.columns if c not in [date_col, time_col, '_merge_key']])
    wbt_cols = sorted([c for df in wbt_dfs for c in df.columns if c not in [date_col, time_col, '_merge_key']])

    max_rows = max(len(water_df), len(air_df))
    final_df_dict: Dict[str, Any] = {}
    if not water_df.empty:
        final_df_dict['Date_W'] = water_df[date_col].tolist() + [None] * (max_rows - len(water_df))
        final_df_dict['Time_W'] = water_df[time_col].tolist() + [None] * (max_rows - len(water_df))
        for col in cwt_cols:
            final_df_dict[col] = water_df[col].tolist() + [None] * (max_rows - len(water_df))
        for col in hwt_cols:
            final_df_dict[col] = water_df[col].tolist() + [None] * (max_rows - len(water_df))
    if not air_df.empty:
        final_df_dict['Date_A'] = air_df[date_col].tolist() + [None] * (max_rows - len(air_df))
        final_df_dict['Time_A'] = air_df[time_col].tolist() + [None] * (max_rows - len(air_df))
        for col in dbt_cols:
            final_df_dict[col] = air_df[col].tolist() + [None] * (max_rows - len(air_df))
        for col in wbt_cols:
            final_df_dict[col] = air_df[col].tolist() + [None] * (max_rows - len(air_df))

    final_df = pd.DataFrame(final_df_dict)

    total_cols = len(final_df.columns)
    if total_cols > 0:
        worksheet.merge_range(0, 0, 0, total_cols - 1, 'Performance Test Consolidated Report', title_fmt)

    col_ptr: int = 0
    start_air: int = 0
    if not water_df.empty:
        worksheet.write(1, col_ptr, 'Date', date_time_fmt)
        worksheet.write(1, col_ptr + 1, 'Time', date_time_fmt)
        worksheet.merge_range(2, col_ptr, 2, col_ptr + 1, 'Sensor No.', sensor_fmt)
        col_ptr += 2
        if cwt_cols:
            if len(cwt_cols) > 1:
                worksheet.merge_range(1, col_ptr, 1, col_ptr + len(cwt_cols) - 1, 'Cold Water Temp. (CWT)', cwt_header_fmt)
            else:
                worksheet.write(1, col_ptr, 'Cold Water Temp. (CWT)', cwt_header_fmt)
            for col in cwt_cols:
                worksheet.write(2, col_ptr, col, sensor_fmt)
                col_ptr += 1
        if hwt_cols:
            if len(hwt_cols) > 1:
                worksheet.merge_range(1, col_ptr, 1, col_ptr + len(hwt_cols) - 1, 'Hot Water Temp. (HWT)', hwt_header_fmt)
            else:
                worksheet.write(1, col_ptr, 'Hot Water Temp. (HWT)', hwt_header_fmt)
            for col in hwt_cols:
                worksheet.write(2, col_ptr, col, hwt_header_fmt)
                col_ptr += 1

    if not air_df.empty:
        start_air = int(col_ptr) if not water_df.empty else 0
        worksheet.write(1, start_air, 'Date', date_time_fmt)
        worksheet.write(1, start_air + 1, 'Time', date_time_fmt)
        worksheet.merge_range(2, start_air, 2, start_air + 1, 'Sensor No.', sensor_fmt)
        col_ptr = start_air + 2
        if dbt_cols:
            if len(dbt_cols) > 1:
                worksheet.merge_range(1, col_ptr, 1, col_ptr + len(dbt_cols) - 1, 'Dry Bulb Temp. (DBT)', dbt_header_fmt)
            else:
                worksheet.write(1, col_ptr, 'Dry Bulb Temp. (DBT)', dbt_header_fmt)
            for col in dbt_cols:
                worksheet.write(2, col_ptr, col, dbt_header_fmt)
                col_ptr += 1
        if wbt_cols:
            if len(wbt_cols) > 1:
                worksheet.merge_range(1, col_ptr, 1, col_ptr + len(wbt_cols) - 1, 'Wet Bulb Temp. (WBT)', wbt_header_fmt)
            else:
                worksheet.write(1, col_ptr, 'Wet Bulb Temp. (WBT)', wbt_header_fmt)
            for col in wbt_cols:
                worksheet.write(2, col_ptr, col, wbt_header_fmt)
                col_ptr += 1

    for r_idx, row in final_df.iterrows():
        for c_idx, value in enumerate(row):
            target_row = r_idx + 3
            if pd.isna(value) or str(value).lower() == 'nan':
                worksheet.write(target_row, c_idx, '', data_fmt)
            else:
                try:
                    worksheet.write_number(target_row, c_idx, float(value), data_fmt)
                except (TypeError, ValueError):
                    worksheet.write_string(target_row, c_idx, str(value), data_fmt)

    worksheet.set_column(0, max(total_cols - 1, 0), 12)

    avg_row_idx = max_rows + 5
    total_avg_row_idx = max_rows + 6

    if not water_df.empty:
        worksheet.write(avg_row_idx, 0, '', avg_label_fmt)
        worksheet.write(avg_row_idx, 1, 'Average', avg_label_fmt)
        worksheet.write(total_avg_row_idx, 0, '', avg_label_fmt)
        worksheet.write(total_avg_row_idx, 1, 'Total Average', avg_label_fmt)
    if not air_df.empty:
        worksheet.write(avg_row_idx, start_air, '', avg_label_fmt)
        worksheet.write(avg_row_idx, start_air + 1, 'Average', avg_label_fmt)
        worksheet.write(total_avg_row_idx, start_air, '', avg_label_fmt)
        worksheet.write(total_avg_row_idx, start_air + 1, 'Total Average', avg_label_fmt)

    cwt_avgs = []
    hwt_avgs = []
    dbt_avgs = []
    wbt_avgs = []

    for c_idx, col_name in enumerate(final_df.columns):
        if col_name in ['Date_W', 'Time_W', 'Date_A', 'Time_A']:
            continue

        col_series = pd.to_numeric(final_df[col_name], errors='coerce')
        avg_val = col_series.mean()
        fmt = avg_val_fmts['default']

        if col_name in cwt_cols:
            fmt = avg_val_fmts['cwt']
            if pd.notna(avg_val):
                cwt_avgs.append(avg_val)
        elif col_name in hwt_cols:
            fmt = avg_val_fmts['hwt']
            if pd.notna(avg_val):
                hwt_avgs.append(avg_val)
        elif col_name in dbt_cols:
            fmt = avg_val_fmts['dbt']
            if pd.notna(avg_val):
                dbt_avgs.append(avg_val)
        elif col_name in wbt_cols:
            fmt = avg_val_fmts['wbt']
            if pd.notna(avg_val):
                wbt_avgs.append(avg_val)

        if pd.notna(avg_val):
            worksheet.write_number(avg_row_idx, c_idx, float(avg_val), fmt)
        else:
            worksheet.write_string(avg_row_idx, c_idx, '-', fmt)

    def write_total_avg(avgs, cols, start_col_idx, fmt_key):
        if not cols:
            return
        total_avg = (sum(avgs) / len(avgs)) if avgs else None
        fmt = avg_val_fmts[fmt_key]
        end_col_idx = start_col_idx + len(cols) - 1
        if len(cols) > 1:
            if total_avg is not None:
                worksheet.merge_range(total_avg_row_idx, start_col_idx, total_avg_row_idx, end_col_idx, float(total_avg), fmt)
            else:
                worksheet.merge_range(total_avg_row_idx, start_col_idx, total_avg_row_idx, end_col_idx, '-', fmt)
        else:
            if total_avg is not None:
                worksheet.write_number(total_avg_row_idx, start_col_idx, float(total_avg), fmt)
            else:
                worksheet.write_string(total_avg_row_idx, start_col_idx, '-', fmt)

    if not water_df.empty:
        cidx = 2
        write_total_avg(cwt_avgs, cwt_cols, cidx, 'cwt')
        cidx += len(cwt_cols)
        write_total_avg(hwt_avgs, hwt_cols, cidx, 'hwt')
    if not air_df.empty:
        cidx = start_air + 2
        write_total_avg(dbt_avgs, dbt_cols, cidx, 'dbt')
        cidx += len(dbt_cols)
        write_total_avg(wbt_avgs, wbt_cols, cidx, 'wbt')


def _detect_excel_engine(file_name):
    """Return the pandas read_excel engine to use based on the file extension."""
    ext = os.path.splitext(file_name)[1].lower()
    if ext == '.xls':
        return 'xlrd'
    # .xlsx / .xlsm / .xlsb – let pandas pick (openpyxl is the default)
    return None


def generate_filtered_workbook(file_items, start_time_str, end_time_str):
    if not file_items:
        raise ValueError('Please upload at least one Excel file.')

    start_time = _parse_user_time(start_time_str)
    end_time = _parse_user_time(end_time_str)
    apply_time_filter = (start_time is not None) and (end_time is not None)

    if apply_time_filter and start_time > end_time:
        raise ValueError('Start time must be earlier than or equal to end time.')

    filtered_dataframes = []

    for file_name, file_bytes in file_items:
        try:
            engine = _detect_excel_engine(file_name)
            df, time_col = _read_excel_with_time_header(file_bytes, engine=engine)
            if df is None:
                continue

            if apply_time_filter and time_col:
                parsed_times = _parse_times(df[time_col])
                mask = (parsed_times >= start_time) & (parsed_times <= end_time)
                filtered_df = df[mask.fillna(False)].copy()
            else:
                # No time filter – take all rows
                filtered_df = df.copy()

            if len(filtered_df) == 0:
                continue

            filtered_df.insert(0, 'Source File', file_name)
            filtered_dataframes.append(filtered_df)
        except Exception:
            continue

    if not filtered_dataframes:
        if apply_time_filter:
            raise ValueError('No rows matched the selected time range in uploaded files.')
        else:
            raise ValueError('No valid data found in the uploaded/selected files.')

    master_df = pd.concat(filtered_dataframes, ignore_index=True)
    master_df.dropna(axis=1, how='all', inplace=True)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        master_df.to_excel(writer, sheet_name='Filtered Data', index=False)
        _style_sheet(writer, 'Filtered Data', master_df)
        
        date_col = next((c for c in master_df.columns if 'date' in str(c).lower()), None)
        if date_col:
            dt_series = pd.to_datetime(master_df[date_col], dayfirst=True, errors='coerce')
            unique_dt_list = dt_series.dropna().dt.normalize().unique()
            # Sort the dates chronologically
            unique_dt_list = sorted(unique_dt_list)
            
            if len(unique_dt_list) == 1:
                # If there's exactly one date, use it as the sheet name instead of 'Consolidated'
                d_str = unique_dt_list[0].strftime('%d-%m-%Y')
                _create_report_layout(writer, master_df, d_str)
            elif len(unique_dt_list) > 1:
                # If multiple dates, split into multiple sheets
                for dt_val in unique_dt_list:
                    # Format as DD-MM-YYYY for display/matching
                    d_str = dt_val.strftime('%d-%m-%Y')
                    mask = dt_series.dt.strftime('%d-%m-%Y') == d_str
                    date_df = master_df[mask].copy()
                    _create_report_layout(writer, date_df, f'{d_str}')
            else:
                # Fallback if no valid dates could be parsed despite having a date column
                _create_report_layout(writer, master_df, 'Consolidated')
        else:
            _create_report_layout(writer, master_df, 'Consolidated')

    if apply_time_filter:
        safe_start = start_time.strftime('%H%M')
        safe_end = end_time.strftime('%H%M')
        file_name = f'Master_Filtered_{safe_start}_to_{safe_end}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    else:
        file_name = f'Master_All_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return file_name, buffer.getvalue()


def generate_filtered_workbook_from_directory(input_dir, start_time_str, end_time_str):
    if not input_dir:
        raise ValueError('Source folder path is required.')
    if not os.path.isdir(input_dir):
        raise ValueError('Source folder path does not exist.')

    SUPPORTED_EXTENSIONS = ('.xlsx', '.xls')

    file_items = []
    for name in os.listdir(input_dir):
        if name.startswith('~'):
            continue
        if not name.lower().endswith(SUPPORTED_EXTENSIONS):
            continue
        file_path = os.path.join(input_dir, name)
        if os.path.isfile(file_path):
            with open(file_path, 'rb') as f:
                file_items.append((name, f.read()))

    if not file_items:
        raise ValueError('No valid .xlsx or .xls files found in the source folder.')

    return generate_filtered_workbook(file_items, start_time_str, end_time_str)
