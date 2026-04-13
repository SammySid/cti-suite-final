import pandas as pd
import warnings
warnings.filterwarnings('ignore')

path = r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\IGPL-CT3- 2026-04-10 18-33-22 0.xlsx'
xl = pd.ExcelFile(path)

print('=== SHEETS ===')
for s in xl.sheet_names:
    print(' ', s)

print()
print('=== RAW first 35 rows (no header) ===')
raw = pd.read_excel(path, header=None, nrows=35)
for i, row in raw.iterrows():
    vals = [str(v) for v in row.tolist()]
    non_empty = [(j, v) for j, v in enumerate(vals) if v.strip() not in ('', 'nan', 'NaT', 'None')]
    if non_empty:
        print(f'  Row {i:02d}: {non_empty}')

print()
print('=== Default parse (header=0) - first 5 rows ===')
df = pd.read_excel(path)
print('Columns:', list(df.columns))
print(df.head(5).to_string())

print()
print('=== Try reading all sheets ===')
for s in xl.sheet_names:
    df2 = xl.parse(s, header=None, nrows=5)
    print(f'Sheet [{s}]: shape={df2.shape}')
    for i, row in df2.iterrows():
        vals = [(j, str(v)) for j, v in enumerate(row) if str(v).strip() not in ('', 'nan')]
        if vals:
            print(f'   row {i}: {vals}')
