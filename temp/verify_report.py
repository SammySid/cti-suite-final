import pandas as pd
import warnings
warnings.filterwarnings('ignore')

path = r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\Master_All_20260411_105119.xlsx'
xl = pd.ExcelFile(path)

sensors = {
    'Q1_A': '1 st quadrant reading Cell A.xls',
    'Q1_B': '1 st quadrant reading Cell B 17.34 to 17.40.xls',
    'Q1_C': '1 st quadrant reading Cell C.xls',
    'Q1_D': '1 st quadrant reading Cell D.xls',
    'Q2_A': '2nd quadrant reading Cell A.xls',
    'Q2_B': '2nd quadrant reading Cell B 17.41 to 17.47.xls',
    'Q2_C': '2nd quadrant reading Cell C.xls',
    'Q2_D': '2nd quadrant reading Cell D.xls',
    'Q3_A': '3rd quadrant reading Cell A.xls',
    'Q3_B': '3rd quadrant reading Cell B 17.49 to 17.54.xls',
    'Q3_C': '3rd quadrant reading Cell C.xls',
    'Q3_D': '3rd quadrant reading Cell D.xls',
}

fd = xl.parse('Filtered Data')
rpt = xl.parse('10-04-2026', header=None)
avg_row   = rpt.iloc[3664]
total_row = rpt.iloc[3665]

vel_cols  = list(range(2, 14))   # cols 2-13  = Q1_A..Q3_D velocity
temp_cols = list(range(16, 28))  # cols 16-27 = Q1_A..Q3_D temperature
sensor_order = list(sensors.keys())

all_ok = True
print("=" * 75)
print(" SENSOR AVERAGE CROSS-CHECK")
print("=" * 75)
print(f"{'Sensor':<8}  {'Vel Sheet':>10} {'Vel Src':>10}  {'OK':>4}    {'Tmp Sheet':>10} {'Tmp Src':>10}  {'OK':>4}")
print("-" * 75)
for i, sid in enumerate(sensor_order):
    grp     = fd[fd['Source File'] == sensors[sid]]
    v_src   = float(grp['Main_Value'].astype(float).mean())
    t_src   = float(grp['Tem_Value'].astype(float).mean())
    v_sheet = float(avg_row.iloc[vel_cols[i]])
    t_sheet = float(avg_row.iloc[temp_cols[i]])
    v_ok    = abs(v_sheet - v_src)  < 0.001
    t_ok    = abs(t_sheet - t_src) < 0.001
    if not (v_ok and t_ok):
        all_ok = False
    print(f"{sid:<8}  {v_sheet:>10.4f} {v_src:>10.4f}  {'YES' if v_ok else 'NO':>4}    {t_sheet:>10.4f} {t_src:>10.4f}  {'YES' if t_ok else 'NO':>4}")

print("-" * 75)

# Total averages
tv_sheet = float(total_row.iloc[2])
tt_sheet = float(total_row.iloc[16])
tv_exp   = sum(float(fd[fd['Source File']==f]['Main_Value'].astype(float).mean()) for f in sensors.values()) / 12
tt_exp   = sum(float(fd[fd['Source File']==f]['Tem_Value'].astype(float).mean()) for f in sensors.values()) / 12
tv_ok    = abs(tv_sheet - tv_exp) < 0.001
tt_ok    = abs(tt_sheet - tt_exp) < 0.001
if not (tv_ok and tt_ok):
    all_ok = False
print(f"{'TOTAL':8}  {tv_sheet:>10.4f} {tv_exp:>10.4f}  {'YES' if tv_ok else 'NO':>4}    {tt_sheet:>10.4f} {tt_exp:>10.4f}  {'YES' if tt_ok else 'NO':>4}")

print()
print("=" * 75)
print(" STRUCTURE CHECK")
print("=" * 75)

checks = [
    ("Sheets present",           xl.sheet_names == ['Filtered Data', '10-04-2026']),
    ("Report shape cols",        rpt.shape[1] == 28),
    ("Title row",                rpt.iloc[0,0] == 'Performance Test Consolidated Report'),
    ("Vel header text",          rpt.iloc[1,2] == 'Velocity / Main Value  [Main_Value]'),
    ("Temp header text",         rpt.iloc[1,16] == 'Temperature  [Tem_Value]'),
    ("Vel Date header",          rpt.iloc[1,0] == 'Date'),
    ("Temp Date header",         rpt.iloc[1,14] == 'Date'),
    ("Sensor IDs row Q1_A",      rpt.iloc[2,2] == 'Q1_A'),
    ("Sensor IDs row Q3_D",      rpt.iloc[2,13] == 'Q3_D'),
    ("Temp Sensor IDs Q1_A",     rpt.iloc[2,16] == 'Q1_A'),
    ("Temp Sensor IDs Q3_D",     rpt.iloc[2,27] == 'Q3_D'),
    ("Sensor No merged col",     str(rpt.iloc[2,0]) == 'Sensor No.'),
    ("All 12 files in filter",   fd['Source File'].nunique() == 12),
    ("Total rows correct",       len(fd) == 3660),
    ("Average row label",        str(avg_row.iloc[1]) == 'Average'),
    ("Total avg label vel",      str(total_row.iloc[1]) == 'Total Average'),
    ("Total avg label temp",     str(total_row.iloc[15]) == 'Total Average'),
    ("Total avg vel correct",    tv_ok),
    ("Total avg temp correct",   tt_ok),
    ("All sensor avgs match",    all_ok),
]

passed = sum(1 for _, r in checks if r)
for label, result in checks:
    status = "PASS" if result else "FAIL"
    print(f"  [{status}]  {label}")

print()
print(f"  Result: {passed}/{len(checks)} checks passed  --  {'ALL GOOD' if passed == len(checks) else 'ISSUES FOUND'}")
print("=" * 75)
