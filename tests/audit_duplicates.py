import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
root = Path(r"c:\Users\thain\Downloads\ML Đồ Án")
raw_path = root / "data" / "raw" / "online_retail_II.xlsx"

print("AUDITING DUPLICATES ON RAW EXCEL SHEETS...")
df1 = pd.read_excel(raw_path, sheet_name="Year 2009-2010", engine="openpyxl")
df2 = pd.read_excel(raw_path, sheet_name="Year 2010-2011", engine="openpyxl")

# Clean column names
for d in [df1, df2]:
    d.columns = [c.strip() for c in d.columns]

dups1_first = df1.duplicated(keep="first").sum()
dups1_all = df1.duplicated(keep=False).sum()

dups2_first = df2.duplicated(keep="first").sum()
dups2_all = df2.duplicated(keep=False).sum()

print(f"Sheet 2009-2010 (525,461 rows):")
print(f"  Exact duplicates (keep='first'): {dups1_first:,}")
print(f"  Total duplicate rows (keep=False): {dups1_all:,}")

print(f"\nSheet 2010-2011 (541,910 rows):")
print(f"  Exact duplicates (keep='first'): {dups2_first:,}")
print(f"  Total duplicate rows (keep=False): {dups2_all:,}")

sum_within = dups1_first + dups2_first
print(f"\nSum of duplicates within individual sheets (keep='first'): {sum_within:,}")

# Combined
df_comb = pd.concat([df1, df2], ignore_index=True)
dups_comb_first = df_comb.duplicated(keep="first").sum()
dups_comb_all = df_comb.duplicated(keep=False).sum()

print(f"\nCombined Dataset (1,067,371 rows):")
print(f"  Exact duplicates (keep='first'): {dups_comb_first:,}")
print(f"  Total duplicate rows (keep=False): {dups_comb_all:,}")
print(f"  Cross-sheet duplicates: {dups_comb_first - sum_within:,}")

# Check business key duplicates (Invoice, StockCode, InvoiceDate)
bk_dups_first = df_comb.duplicated(subset=["Invoice", "StockCode", "InvoiceDate"], keep="first").sum()
print(f"\nBusiness Key duplicates on [Invoice, StockCode, InvoiceDate] (keep='first'): {bk_dups_first:,}")

# Check if 12,133 was from Year 2009-2010 or specific subset
print(f"\nIs 12,133 equal to Year 2009-2010 duplicates? (Diff: {dups1_first - 12133})")
