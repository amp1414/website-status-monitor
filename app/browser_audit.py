from __future__ import annotations

import asyncio
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

from app.checker import CONFIG_XLSX, Endpoint, load_config


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
BROWSER_LOGS_DIR = DATA_DIR / "browser_logs"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"

BROWSER_LOG_COLUMNS = [
    "ts_utc",
    "audit_run_ts_utc",
    "site_id",
    "endpoint_id",
    "url",
    "level",
    "message",
    "source",
    "line",
    "column",
    "exception_rule_id",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_utc_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def rewrite_browser_log_csv_with_expected_columns(path: Path) -> None:
    if not path.exists():
        return

    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(BROWSER_LOG_COLUMNS)
        return

    header = rows[0]
    data_rows = rows[1:]

    if header == BROWSER_LOG_COLUMNS:
        return

    normalized_rows = []
    header_len = len(header)

    for row in data_rows:
        padded = list(row) + [""] * max(0, header_len - len(row))
        record = {header[i]: padded[i] for i in range(header_len)}
        normalized_rows.append([record.get(col, "") for col in BROWSER_LOG_COLUMNS])

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(BROWSER_LOG_COLUMNS)
        w.writerows(normalized_rows)


def ensure_browser_log_csv(path: Path) -> None:
    BROWSER_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(BROWSER_LOG_COLUMNS)
        return

    rewrite_browser_log_csv_with_expected_columns(path)


def browser_log_path_for_today() -> Path:
    return BROWSER_LOGS_DIR / f"{today_utc_str()}.csv"


def append_browser_log_row(
    path: Path,
    *,
    ts_utc: str,
    audit_run_ts_utc: str,
    site_id: int,
    endpoint_id: int,
    url: str,
    level: str,
    message: str,
    source: str = "",
    line: str | int = "",
    column: str | int = "",
    exception_rule_id: str | int = "",
) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                ts_utc,
                audit_run_ts_utc,
                site_id,
                endpoint_id,
                url,
                level,
                message,
                source,
                line,
                column,
                exception_rule_id,
            ]
        )


def load_exception_rules() -> list[dict]:
    """
    Optional sheet in sites.xlsx named 'exceptions'.

    Expected columns:
      rule_id, enabled, site_id, endpoint_id, match_type, pattern, notes
    """

    try:
        df = pd.read_excel(CONFIG_XLSX, sheet_name="exceptions")
    except Exception:
        return []

    if df.empty:
        return []

    rules: list[dict] = []

    for _, row in df.iterrows():
        enabled = row.get("enabled", 1)
        if pd.notna(enabled) and int(enabled) != 1:
            continue

        pattern = "" if pd.isna(row.get("pattern")) else str(row.get("pattern")).strip()
        if pattern == "":
            continue

        site_id = None
        endpoint_id = None

        if pd.notna(row.get("site_id")):
            site_id = int(row["site_id"])

        if pd.notna(row.get("endpoint_id")):
            endpoint_id = int(row["endpoint_id"])

        rules.append(
            {
                "rule_id": "" if pd.isna(row.get("rule_id")) else str(row.get("rule_id")),
                "site_id": site_id,
                "endpoint_id": endpoint_id,
                "match_type": (
                    "contains"
                    if pd.isna(row.get("match_type"))
                    else str(row.get("match_type")).strip().lower()
                ),
                "pattern": pattern,
            }
        )

    return rules


def find_matching_exception_rule_id(
    *,
    site_id: int,
    endpoint_id: int,
    message: str,
    source: str,
    rules: list[dict],
) -> str:
    haystack = f"{message} {source}".strip()

    for rule in rules:
        rule_site_id = rule["site_id"]
        rule_endpoint_id = rule["endpoint_id"]

        if rule_site_id is not None and rule_site_id != site_id:
            continue

        if rule_endpoint_id is not None and rule_endpoint_id != endpoint_id:
            continue

        match_type = rule["match_type"]
        pattern = rule["pattern"]

        if match_type == "regex":
            try:
                if re.search(pattern, haystack, flags=re.IGNORECASE):
                    return rule["rule_id"]
            except re.error:
                continue
        else:
            if pattern.lower() in haystack.lower():
                return rule["rule_id"]

    return ""


def daily_screenshot_path(site_id: int, endpoint_id: int) -> Path:
    day = today_utc_str()
    out_dir = SCREENSHOTS_DIR / "daily" / str(site_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{day}_endpoint_{endpoint_id}.png"


async def audit_one_endpoint(browser, ep: Endpoint, rules: list[dict], csv_path: Path) -> None:
    audit_run_ts_utc = utc_now_iso()

    context = await browser.new_context()
    page = await context.new_page()

    console_events: list[dict] = []
    page_errors: list[dict] = []
    request_failures: list[dict] = []

    def on_console(msg):
        try:
            location = msg.location
        except Exception:
            location = {}

        console_events.append(
            {
                "level": str(msg.type),
                "message": str(msg.text),
                "source": "" if not location else str(location.get("url", "")),
                "line": "" if not location else location.get("lineNumber", ""),
                "column": "" if not location else location.get("columnNumber", ""),
            }
        )

    def on_page_error(exc):
        page_errors.append(
            {
                "level": "pageerror",
                "message": str(exc),
                "source": "",
                "line": "",
                "column": "",
            }
        )

    def on_request_failed(request):
        failure = request.failure
        failure_text = ""
        if failure:
            failure_text = str(failure)

        request_failures.append(
            {
                "level": "requestfailed",
                "message": f"{request.resource_type} failed: {failure_text}".strip(),
                "source": request.url,
                "line": "",
                "column": "",
            }
        )

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)

    try:
        await page.goto(ep.url, wait_until="load", timeout=20000)
        await page.wait_for_timeout(3000)

        shot_path = daily_screenshot_path(ep.site_id, ep.endpoint_id)
        if not shot_path.exists():
            await page.screenshot(path=str(shot_path), full_page=True)

    except Exception as e:
        exception_rule_id = find_matching_exception_rule_id(
            site_id=ep.site_id,
            endpoint_id=ep.endpoint_id,
            message=str(e),
            source=ep.url,
            rules=rules,
        )

        append_browser_log_row(
            csv_path,
            ts_utc=utc_now_iso(),
            audit_run_ts_utc=audit_run_ts_utc,
            site_id=ep.site_id,
            endpoint_id=ep.endpoint_id,
            url=ep.url,
            level="navigation_error",
            message=f"{e.__class__.__name__}: {e}",
            source=ep.url,
            line="",
            column="",
            exception_rule_id=exception_rule_id,
        )

        await context.close()
        return

    all_events = console_events + page_errors + request_failures

    for event in all_events:
        exception_rule_id = find_matching_exception_rule_id(
            site_id=ep.site_id,
            endpoint_id=ep.endpoint_id,
            message=event["message"],
            source=event["source"],
            rules=rules,
        )

        append_browser_log_row(
            csv_path,
            ts_utc=utc_now_iso(),
            audit_run_ts_utc=audit_run_ts_utc,
            site_id=ep.site_id,
            endpoint_id=ep.endpoint_id,
            url=ep.url,
            level=event["level"],
            message=event["message"],
            source=event["source"],
            line=event["line"],
            column=event["column"],
            exception_rule_id=exception_rule_id,
        )

    await context.close()


def resolve_endpoints_for_cycle(checked_endpoints: list[Endpoint] | None) -> list[Endpoint]:
    if checked_endpoints is not None:
        return checked_endpoints

    _, endpoints = load_config(CONFIG_XLSX)
    return endpoints


async def _amain(checked_endpoints: list[Endpoint] | None = None) -> None:
    endpoints = resolve_endpoints_for_cycle(checked_endpoints)

    if not endpoints:
        print("No endpoints to browser-audit this cycle.")
        return

    csv_path = browser_log_path_for_today()
    ensure_browser_log_csv(csv_path)

    rules = load_exception_rules()

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Running browser audit for {len(endpoints)} endpoint(s) ...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for ep in endpoints:
            try:
                await audit_one_endpoint(browser, ep, rules, csv_path)
                print(
                    f"[browser] endpoint {ep.endpoint_id} site {ep.site_id}: audited"
                )
            except Exception as e:
                audit_run_ts_utc = utc_now_iso()
                append_browser_log_row(
                    csv_path,
                    ts_utc=utc_now_iso(),
                    audit_run_ts_utc=audit_run_ts_utc,
                    site_id=ep.site_id,
                    endpoint_id=ep.endpoint_id,
                    url=ep.url,
                    level="browser_audit_error",
                    message=f"{e.__class__.__name__}: {e}",
                    source=ep.url,
                    line="",
                    column="",
                    exception_rule_id="",
                )
                print(
                    f"[browser] endpoint {ep.endpoint_id} site {ep.site_id}: failed {e!r}"
                )

        await browser.close()

    print(f"Browser audit done. Appended to {csv_path}")


def main(checked_endpoints: list[Endpoint] | None = None) -> None:
    asyncio.run(_amain(checked_endpoints))


if __name__ == "__main__":
    main()