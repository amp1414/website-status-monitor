import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
XLSX_PATH = DATA_DIR / "sites.xlsx"

TARGET_SITE_NAME = "Httpbin200"
NEW_URL = "https://httpbin.org/status/503"


def main():
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"Missing: {XLSX_PATH.resolve()}")

    # Read sheets
    sites_df = pd.read_excel(XLSX_PATH, sheet_name="sites")
    endpoints_df = pd.read_excel(XLSX_PATH, sheet_name="endpoints")

    # Find site_id for Httpbin200
    match = sites_df.loc[sites_df["name"].astype(str).str.strip() == TARGET_SITE_NAME, "site_id"]
    if match.empty:
        raise ValueError(f"Site name not found in sites sheet: {TARGET_SITE_NAME}")

    site_id = int(match.iloc[0])

    # Update endpoints URL(s) for that site_id
    if "url" not in endpoints_df.columns or "site_id" not in endpoints_df.columns:
        raise ValueError("endpoints sheet must contain 'site_id' and 'url' columns")

    before = endpoints_df.loc[endpoints_df["site_id"] == site_id, "url"].astype(str).tolist()
    endpoints_df.loc[endpoints_df["site_id"] == site_id, "url"] = NEW_URL

    # Write back to same xlsx (make sure it's not open anywhere)
    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
        sites_df.to_excel(writer, sheet_name="sites", index=False)
        endpoints_df.to_excel(writer, sheet_name="endpoints", index=False)

    print(f"Updated site '{TARGET_SITE_NAME}' (site_id={site_id})")
    print("Before:")
    for u in before:
        print(" -", u)
    print("After:")
    print(" -", NEW_URL)


if __name__ == "__main__":
    main()