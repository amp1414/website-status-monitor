import pandas as pd
from pathlib import Path


DATA_DIR = Path("data")
XLSX_PATH = DATA_DIR / "sites.xlsx"


DOMAINS = [
    "416-flowers.com",
    "a3cf.org",
    "lejardin.com",
    "albertgelman.com",
    "arellicleaning.com",
    "argocustoms.com",
    "askhoward.com",
    "boxshop.ca",
    "canadianimportexport.ca",
    "commercialcleaninggta.com",
    "cozycomfortplus.com",
    "elginmillsendodontic.com",
    "endodonticsondonmills.com",
    "goldenrescue.ca",
    "helpinghandsdoula.com",
    "iamyoga.ca",
    "iconbedbugs.ca",
    "iconbird.ca",
    "iconpest.ca",
    "identos.com",
    "iranda.ca",
    "marketing-dentist.com",
    "metrobit.ca",
    "nuday.com",
    "officecleaningbrampton.com",
    "officecleaninggta.com",
    "officecleaningvaughan.com",
    "packyourboxes.com",
    "pante-a.com",
    "profuneralflowers.com",
    "redsealvending.ca",
    "surgearrest.com",
    "toplinedesign.ca",
    "wildlifecontrol.ca",
    "zigma.ca",
    "zigship.com",
    "oneworldimmigration.ca",
    "airconditioner-furnace.ca",
    "bed-bugs-treatments.com",
    "sultanxpress.ca",
    "wildlifepro.ca",
    "reboundproducts.com",
]


EXCEPTIONS_COLUMNS = [
    "rule_id",
    "enabled",
    "site_id",
    "endpoint_id",
    "match_type",
    "pattern",
    "notes",
]


def make_site_name(domain: str) -> str:
    """
    Keep the display name simple and readable.
    Example:
      'officecleaninggta.com' -> 'officecleaninggta.com'
    """
    return domain.strip()


def make_url(domain: str) -> str:
    return f"https://{domain.strip()}"


def main():
    DATA_DIR.mkdir(exist_ok=True)

    clean_domains = [d.strip() for d in DOMAINS if str(d).strip()]
    clean_domains = list(dict.fromkeys(clean_domains))  # remove duplicates, keep order

    sites_rows = []
    endpoints_rows = []

    for i, domain in enumerate(clean_domains, start=1):
        site_id = i
        endpoint_id = i

        sites_rows.append({
            "site_id": site_id,
            "name": make_site_name(domain),
            "enabled": 1,
        })

        endpoints_rows.append({
            "endpoint_id": endpoint_id,
            "site_id": site_id,
            "url": make_url(domain),
            "method": "GET",
            "slow_ms": 2000,
        })

    sites_df = pd.DataFrame(sites_rows, columns=["site_id", "name", "enabled"])
    endpoints_df = pd.DataFrame(
        endpoints_rows,
        columns=["endpoint_id", "site_id", "url", "method", "slow_ms"],
    )
    exceptions_df = pd.DataFrame(columns=EXCEPTIONS_COLUMNS)

    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
        sites_df.to_excel(writer, sheet_name="sites", index=False)
        endpoints_df.to_excel(writer, sheet_name="endpoints", index=False)
        exceptions_df.to_excel(writer, sheet_name="exceptions", index=False)

    print(f"Replaced workbook: {XLSX_PATH}")
    print(f"Sites written: {len(sites_df)}")
    print(f"Endpoints written: {len(endpoints_df)}")
    print("Exceptions sheet reset to empty with correct columns.")
    print()
    print("First few rows preview:")
    print(sites_df.head())
    print()
    print(endpoints_df.head())


if __name__ == "__main__":
    main()