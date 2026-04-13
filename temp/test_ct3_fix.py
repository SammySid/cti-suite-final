import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, r'f:\2026 latest\cti Toolkit\cti-suite-final\cti_dashboard_pro\app\backend')
from excel_filter_service import generate_filtered_workbook
import pandas as pd

path = r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\IGPL-CT3- 2026-04-10 18-33-22 0.xlsx'
with open(path, 'rb') as f:
    data = f.read()

file_items = [('IGPL-CT3- 2026-04-10 18-33-22 0.xlsx', data)]

print('=== TEST 1: Time filter 3pm-7pm ===')
fname, out = generate_filtered_workbook(file_items, '3pm', '7pm')
outpath = r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\ct3_filtered_3pm_7pm.xlsx'
with open(outpath, 'wb') as f:
    f.write(out)
print(f'Output: {fname}  ({len(out):,} bytes)')
xl = pd.ExcelFile(outpath)
print('Sheets:', xl.sheet_names)
fd = xl.parse('Filtered Data')
print(f'Filtered Data: {len(fd)} rows, {len(fd.columns)} cols')
print('Columns:', list(fd.columns[:6]), '...')
# Check time range in filtered data
print('Time range in result:')
print(f'  Min time in Date col: {fd["Date"].unique()}')
t_col = fd['Time'] if 'Time' in fd.columns else None
if t_col is not None:
    print(f'  Min Time: {t_col.min()},  Max Time: {t_col.max()}')

# Check report sheet
for s in xl.sheet_names[1:]:
    rpt = xl.parse(s, header=None)
    print(f'\nReport sheet [{s}]: shape={rpt.shape}')
    print('  Row 0 (title):', [v for v in rpt.iloc[0] if str(v) != 'nan'][:2])
    print('  Row 1 (headers):', [(i,str(v)) for i,v in enumerate(rpt.iloc[1]) if str(v) != 'nan'])
    print('  Row 2 (sensors):', [(i,str(v)) for i,v in enumerate(rpt.iloc[2]) if str(v) != 'nan'])
    # Last 3 rows (avgs)
    for ri in [-3,-2,-1]:
        row = rpt.iloc[ri]
        nonnull = [(i,v) for i,v in enumerate(row) if str(v) not in ('nan','')]
        if nonnull:
            print(f'  Row {len(rpt)+ri}: {nonnull[:8]}')

print()
print('=== TEST 2: Process All (no time filter) ===')
fname2, out2 = generate_filtered_workbook(file_items, '', '')
print(f'Output: {fname2}  ({len(out2):,} bytes)')
xl2 = pd.ExcelFile(r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\ct3_filtered_3pm_7pm.xlsx')
fd2 = xl2.parse('Filtered Data')
print(f'Filtered Data: {len(fd2)} rows (expected ~279 total rows from CT3 file)')
