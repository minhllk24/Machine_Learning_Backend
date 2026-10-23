import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
root = Path(r"c:\Users\thain\Downloads\ML Đồ Án")
df = pd.read_parquet(root / "data" / "interim" / "raw_transactions.parquet")

non_merch_candidates = [
    "POST", "D", "M", "BANK CHARGES", "PADS", "DOT", 
    "CRUK", "C2", "AMAZONFEE", "S", "B", "TEST"
]

print("NON-MERCHANDISE CODE FORENSIC AUDIT:")
records = []
for code in non_merch_candidates:
    sub = df[df["StockCode"].astype(str).str.strip().str.upper() == code.upper()]
    if not sub.empty:
        sample_desc = sub["Description"].dropna().iloc[0] if len(sub["Description"].dropna()) > 0 else "N/A"
        all_descs = sub["Description"].dropna().unique().tolist()[:3]
        total_rows = len(sub)
        total_qty = sub["Quantity"].sum()
        price_range = (sub["Price"].min(), sub["Price"].max())
        
        # Determine classification
        if code in ["POST", "DOT", "C2"]:
            cat = "Shipping & Carriage Fees"
            reason = "Postal fee or delivery surcharge, not physical merchandise"
            status = "DEFINITIVE_NON_MERCH"
        elif code in ["BANK CHARGES"]:
            cat = "Banking & Processing Fees"
            reason = "Financial transaction charge"
            status = "DEFINITIVE_NON_MERCH"
        elif code in ["D", "AMAZONFEE", "CRUK"]:
            cat = "Discounts, Platform Fees & Donations"
            reason = "Accounting line item or donation"
            status = "DEFINITIVE_NON_MERCH"
        elif code in ["M"]:
            cat = "Manual Administrative Line"
            reason = "Manual invoice correction or non-catalog item"
            status = "DEFINITIVE_NON_MERCH"
        elif code in ["PADS"]:
            cat = "Display Pads / Packaging"
            reason = "Promotional display pads (often £0.00)"
            status = "REVIEW_FLAG"
        elif code in ["S", "B"]:
            cat = "Sample / Bad Debt Adjustments"
            reason = "Samples or accounting write-offs"
            status = "REVIEW_FLAG"
        else:
            cat = "Other Non-Merchandise"
            reason = "Non-standard catalog item"
            status = "REVIEW_FLAG"
            
        records.append({
            "StockCode": code,
            "Classification_Category": cat,
            "Total_Occurrences": total_rows,
            "Total_Quantity": total_qty,
            "Min_Price": price_range[0],
            "Max_Price": price_range[1],
            "Sample_Descriptions": "; ".join(str(d) for d in all_descs),
            "Exclusion_Reason": reason,
            "Audit_Status": status
        })

df_res = pd.DataFrame(records)
print(df_res[["StockCode", "Classification_Category", "Total_Occurrences", "Total_Quantity", "Audit_Status"]].to_string(index=False))

out_path = root / "artifacts" / "tables" / "non_merchandise_audit_table.csv"
df_res.to_csv(out_path, index=False)
print(f"\nSaved detailed non-merchandise audit table to {out_path}")
