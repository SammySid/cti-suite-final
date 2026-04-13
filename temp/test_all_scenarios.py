import sys, warnings, io
warnings.filterwarnings('ignore')
sys.path.insert(0, r'f:\2026 latest\cti Toolkit\cti-suite-final\cti_dashboard_pro\app\backend')
from excel_filter_service import generate_filtered_workbook_from_directory, generate_filtered_workbook
import pandas as pd

PASS = True

# ─── Test 1: Fan folder - Process All ───────────────────────────────────────
print('=== Test 1: Fan folder (Process All) ===')
fname, out = generate_filtered_workbook_from_directory(
    r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\fan', '', '')
xl = pd.ExcelFile(io.BytesIO(out))
fd = xl.parse('Filtered Data')
sheets = xl.sheet_names
rpt = xl.parse(sheets[1], header=None)
avg_row   = rpt.iloc[-2]
total_row = rpt.iloc[-1]

def _num_cells(row):
    result = []
    for i, v in enumerate(row):
        if str(v) in ('nan', ''):
            continue
        try:
            result.append((i, round(float(v), 4)))
        except (ValueError, TypeError):
            pass
    return result

v_avgs = _num_cells(avg_row)
t_avgs = _num_cells(total_row)

ok1 = fd['Source File'].nunique() == 12
ok2 = len(fd) == 3660
ok3 = len(v_avgs) >= 12      # 12 vel + 12 temp averages
ok4 = len(t_avgs) == 2       # total vel avg + total temp avg
print(f'  Files in Filtered Data : {fd["Source File"].nunique()}/12  {"OK" if ok1 else "FAIL"}')
print(f'  Total rows             : {len(fd)}/3660  {"OK" if ok2 else "FAIL"}')
print(f'  Avg values present     : {len(v_avgs)} (>=24?)  {"OK" if ok3 else "FAIL"}')
print(f'  Total avg cells        : {len(t_avgs)} (expect 2)  {"OK" if ok4 else "FAIL"}')
print(f'  Total Vel Avg          : {t_avgs[0][1]}')
print(f'  Total Temp Avg         : {t_avgs[1][1]}')
if not all([ok1, ok2, ok3, ok4]):
    PASS = False

# ─── Test 2: CT3 file - Time filter 3pm-7pm ─────────────────────────────────
print()
print('=== Test 2: CT3 file - Time filter 3pm to 7pm ===')
ct3_path = r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\IGPL-CT3- 2026-04-10 18-33-22 0.xlsx'
with open(ct3_path, 'rb') as f:
    raw = f.read()
fname2, out2 = generate_filtered_workbook(
    [('IGPL-CT3- 2026-04-10 18-33-22 0.xlsx', raw)], '3pm', '7pm')
xl2    = pd.ExcelFile(io.BytesIO(out2))
fd2    = xl2.parse('Filtered Data')
rpt2   = xl2.parse(xl2.sheet_names[1], header=None)
avg2   = rpt2.iloc[-2]
tot2   = rpt2.iloc[-1]
t_min  = fd2['Time'].min()
t_max  = fd2['Time'].max()
n_sens = sum(1 for v in rpt2.iloc[2] if str(v) not in ('nan','') and v != 'Sensor No.')
n_avgs = sum(1 for i,v in enumerate(avg2) if str(v) not in ('nan','') and i > 1)
tot_avg = next((float(v) for i,v in enumerate(tot2) if i > 1 and str(v) not in ('nan','')), None)

ok5 = len(fd2) == 212                     # 3pm-7pm → 212 rows
ok6 = t_min == '15:00:05'
ok7 = t_max == '18:31:05'
ok8 = '102' in str(list(rpt2.iloc[2]))    # OL channel 101 removed
ok9 = n_avgs >= 14                         # 15 valid CWT sensors
ok10 = tot_avg is not None and 28 < tot_avg < 35   # sensible CWT avg

print(f'  Filtered rows (3pm-7pm)  : {len(fd2)}/212  {"OK" if ok5 else "FAIL"}')
print(f'  Min time                  : {t_min}  {"OK" if ok6 else "FAIL"}')
print(f'  Max time                  : {t_max}  {"OK" if ok7 else "FAIL"}')
print(f'  OL ch101 removed          : {"OK" if ok8 else "FAIL"} (first sensor = 102)')
print(f'  CWT avg columns           : {n_avgs}  {"OK" if ok9 else "FAIL"}')
print(f'  Total CWT avg             : {round(tot_avg,4) if tot_avg else None}  {"OK" if ok10 else "FAIL"}')
if not all([ok5, ok6, ok7, ok8, ok9, ok10]):
    PASS = False

# ─── Test 3: CT3 - Process All ───────────────────────────────────────────────
print()
print('=== Test 3: CT3 file - Process All ===')
fname3, out3 = generate_filtered_workbook(
    [('IGPL-CT3- 2026-04-10 18-33-22 0.xlsx', raw)], '', '')
xl3 = pd.ExcelFile(io.BytesIO(out3))
fd3 = xl3.parse('Filtered Data')
ok11 = len(fd3) == 279    # full file = 279 rows
print(f'  Total rows (all)  : {len(fd3)}/279  {"OK" if ok11 else "FAIL"}')
if not ok11:
    PASS = False

# ─── Result ──────────────────────────────────────────────────────────────────
print()
print('=' * 55)
print(f'  OVERALL RESULT: {"ALL TESTS PASSED" if PASS else "SOME TESTS FAILED"}')
print('=' * 55)
