import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

path = r'f:\2026 latest\cti Toolkit\cti-suite-final\temp\IGPL-CT3- 2026-04-10 18-33-22 0.xlsx'

print('=== RAW rows 0-12 (no header) ===')
raw = pd.read_excel(path, header=None, nrows=13)
for i, row in raw.iterrows():
    vals = [(j, str(v)) for j, v in enumerate(row) if str(v).strip() not in ('nan', 'NaT', '')]
    print(f'  Row {i:02d}: {vals}')

print()
print('=== Column dtypes with header=0 (default) ===')
df = pd.read_excel(path)
print(f'  Shape: {df.shape}')
for col in df.columns:
    print(f'  [{col}] dtype={df[col].dtype}  sample={df[col].dropna().iloc[0] if not df[col].dropna().empty else "EMPTY"}')

print()
print('=== Try header=8 ===')
df8 = pd.read_excel(path, header=8)
print(f'  Shape: {df8.shape}')
print(f'  Columns: {list(df8.columns)}')
print(df8.head(3).to_string())

print()
print('=== Data range check ===')
# Find rows where col 0 looks like a datetime
raw_all = pd.read_excel(path, header=None)
print(f'  Total rows: {len(raw_all)}')
# Check col 0 dtype
col0 = raw_all.iloc[:, 0]
print(f'  Col 0 dtype: {col0.dtype}')
print(f'  Col 0 sample values (first 15 non-null): {col0.dropna().head(15).tolist()}')
# How many look like datetime?
dt_parsed = pd.to_datetime(col0, errors='coerce')
valid_dt = dt_parsed.dropna()
print(f'  Valid datetime rows in col0: {len(valid_dt)}')
if len(valid_dt) > 0:
    print(f'  First datetime: {valid_dt.iloc[0]}')
    print(f'  Last datetime:  {valid_dt.iloc[-1]}')
    # Time range
    times = valid_dt.dt.time
    print(f'  Time range: {times.min()} to {times.max()}')
