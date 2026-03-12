from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from pathlib import Path

DATA_DIR = Path("data")
XLSX_PATH = DATA_DIR / "sites.xlsx"
SHEET_NAME = "exceptions"


COLUMNS = [
    "rule_id",
    "enabled",
    "site_id",
    "endpoint_id",
    "match_type",
    "pattern",
    "notes",
]


NEW_ROW = {
    "rule_id": "GH_WEBGL_1",
    "enabled": 1,
    "site_id": 3,
    "endpoint_id": 3,
    "match_type": "contains",
    "pattern": "GPU stall due to ReadPixels",
    "notes": "Ignore GitHub WebGL GPU stall warning for testing",
}


def read_existing_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[COLUMNS].copy()


def row_already_exists(df: pd.DataFrame, row: dict) -> bool:
    if df.empty:
        return False

    mask = (
        df["rule_id"].astype(str).fillna("") == str(row["rule_id"])
    )
    return mask.any()


def write_sheet(path: Path, sheet_name: str, df: pd.DataFrame) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Could not find workbook: {path}")

    with pd.ExcelWriter(
        path,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace",
    ) as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

def main() -> None:
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"Missing Excel file: {XLSX_PATH}")

    existing = read_existing_sheet(XLSX_PATH, SHEET_NAME)
    existing = normalize_columns(existing)

    if row_already_exists(existing, NEW_ROW):
        print("Exception row already exists. No changes made.")
        return

    updated = pd.concat([existing, pd.DataFrame([NEW_ROW])], ignore_index=True)
    updated = normalize_columns(updated)

    write_sheet(XLSX_PATH, SHEET_NAME, updated)

    print(f"Updated sheet '{SHEET_NAME}' in {XLSX_PATH}")
    print("Added row:")
    print(NEW_ROW)


if __name__ == "__main__":
    main()