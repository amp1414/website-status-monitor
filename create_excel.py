import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
XLSX_PATH = DATA_DIR / "sites.xlsx"

def main():
    DATA_DIR.mkdir(exist_ok=True)

    # Sites table (main domains / groups)
    sites = pd.DataFrame({
        "site_id": [1, 2, 3, 4, 5],
        "name": [
        "Google",
        "Wikipedia",
        "GitHub",
        "Httpbin503",
        "Httpbin200",],
        "enabled": [1, 1, 1, 1, 1],
    })

    # Endpoints table (what actually gets pinged)
    endpoints = pd.DataFrame({
        "endpoint_id": [1, 2, 3, 4, 5, 6],
        "site_id":     [1, 2, 3, 4, 5, 1],
        "url": [
            "https://www.google.com",           # UP (200)
            "https://www.wikipedia.org",        # usually 200, sometimes 403 (real-world)
            "https://github.com/",              # UP (200)
            "https://httpbin.org/status/503",   # DOWN test (503)
            "https://httpbin.org/status/200",   # UP test (200)
            "http://google.com",                # REVIEW test (301/302/etc.)
        ],
        "method": ["GET", "GET", "GET", "GET", "GET", "GET"],
        "slow_ms": [2000, 2000, 2000, 2000, 2000, 2000],
    })

    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
        sites.to_excel(writer, sheet_name="sites", index=False)
        endpoints.to_excel(writer, sheet_name="endpoints", index=False)

    print(f"Recreated {XLSX_PATH} with clean sites + endpoints.")

if __name__ == "__main__":
    main()