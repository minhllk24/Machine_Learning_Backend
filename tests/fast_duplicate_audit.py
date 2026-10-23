import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
root = Path(r"c:\Users\thain\Downloads\ML Đồ Án")
df = pd.read_parquet(root / "data" / "interim" / "raw_transactions.parquet")

print(f"Total raw rows: {len(df):,}")

# 1. Exact-row duplicates:
# keep='first' -> Number of surplus rows to drop to leave 1 unique copy
n_surplus_first = df.duplicated(keep="first").sum()

# keep=False -> Total rows that belong to any duplicate group
n_all_in_dup_groups = df.duplicated(keep=False).sum()

# Number of distinct duplicate groups
n_dup_groups = df[df.duplicated(keep=False)].groupby(list(df.columns)).ngroups

print("\n--- EXACT ROW DUPLICATES AUDIT ---")
print(f"1. Total surplus duplicate rows to remove (keep='first'): {n_surplus_first:,}")
print(f"2. Total rows participating in duplicate groups (keep=False): {n_all_in_dup_groups:,}")
print(f"3. Number of distinct duplicate groups (patterns): {n_dup_groups:,}")
print(f"Check arithmetic: {n_all_in_dup_groups:,} - {n_dup_groups:,} = {n_all_in_dup_groups - n_dup_groups:,} surplus rows")

# 2. Check year-based duplicates:
df["year"] = pd.to_datetime(df["InvoiceDate"]).dt.year
for y, gdf in df.groupby("year"):
    y_first = gdf.duplicated(keep="first").sum()
    print(f"Year {y} exact duplicates (keep='first'): {y_first:,} / {len(gdf):,} rows")

# 3. Check historical 12,133 reference:
# Year 2009-2010 sheet had 525,461 rows. If deduplicated without CustomerID or with specific subset:
for sub in [
    ["Invoice", "StockCode"],
    ["Invoice", "StockCode", "Price"],
    ["Invoice", "StockCode", "InvoiceDate"],
    ["Invoice", "StockCode", "Quantity", "Price"],
]:
    n_sub = df.duplicated(subset=sub, keep="first").sum()
    print(f"Business key subset {sub}: {n_sub:,} duplicates")

# Check if 12,133 was in Year 2009-2010 only:
df_2009_2010 = df.iloc[:525461]
dups_sheet1 = df_2009_2010.duplicated(keep="first").sum()
print(f"\nSheet 1 exact duplicates (iloc[:525,461]): {dups_sheet1:,}")
df_2010_2011 = df.iloc[525461:]
dups_sheet2 = df_2010_2011.duplicated(keep="first").sum()
print(f"Sheet 2 exact duplicates (iloc[525,461:]): {dups_sheet2:,}")
print(f"Sum of duplicates within sheets: {dups_sheet1 + dups_sheet2:,}")
cross_sheet = n_surplus_first - (dups_sheet1 + dups_sheet2)
print(f"Cross-sheet duplicates (identical row in both sheets): {cross_sheet:,}")
