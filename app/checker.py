from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CONFIG_XLSX = DATA_DIR / "sites.xlsx"
LOGS_DIR = DATA_DIR / "logs"

def log_path_for_ts(ts_utc: str) -> Path:
    # ts_utc like "2026-03-02T04:21:30+00:00" -> date "2026-03-02"
    day = ts_utc[:10]
    return LOGS_DIR / f"{day}.csv"

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_SLOW_MS = 2000
RETRIES = 3  # 3 failed attempts => DOWN


@dataclass(frozen=True)
class Endpoint:
    endpoint_id: int
    site_id: int
    url: str
    method: str
    slow_ms: int


def ensure_checks_csv(path: Path) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "ts_utc",
                "site_id",
                "endpoint_id",
                "state",         # UP / REVIEW / DOWN
                "status_code",
                "error_type",
                "error_detail",
                "latency_ms",
                "attempts",
                "slow",
            ]
        )


def load_config(xlsx_path: Path) -> tuple[dict[int, str], list[Endpoint]]:
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Config not found: {xlsx_path}")

    sites_df = pd.read_excel(xlsx_path, sheet_name="sites")
    endpoints_df = pd.read_excel(xlsx_path, sheet_name="endpoints")

    enabled_site_ids = set(
        sites_df.loc[sites_df["enabled"] == 1, "site_id"].astype(int).tolist()
    )
    endpoints_df = endpoints_df[
        endpoints_df["site_id"].astype(int).isin(enabled_site_ids)
    ].copy()

    site_name = {int(r["site_id"]): str(r["name"]) for _, r in sites_df.iterrows()}

    # Fill defaults if missing
    if "method" in endpoints_df.columns:
        endpoints_df["method"] = endpoints_df["method"].fillna("GET")
    if "slow_ms" in endpoints_df.columns:
        endpoints_df["slow_ms"] = endpoints_df["slow_ms"].fillna(DEFAULT_SLOW_MS)

    endpoints: list[Endpoint] = []
    for _, row in endpoints_df.iterrows():
        endpoints.append(
            Endpoint(
                endpoint_id=int(row["endpoint_id"]),
                site_id=int(row["site_id"]),
                url=str(row["url"]).strip(),
                method=str(row["method"]).strip().upper(),
                slow_ms=int(row["slow_ms"]),
            )
        )

    return site_name, endpoints


def classify_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connect"
    if isinstance(exc, httpx.ReadError):
        return "read"
    if isinstance(exc, httpx.RemoteProtocolError):
        return "protocol"
    if isinstance(exc, httpx.RequestError):
        return "request_error"
    return exc.__class__.__name__.lower()


def strip_default_port(netloc: str) -> str:
    netloc = (netloc or "").strip().lower()
    if netloc.endswith(":80"):
        return netloc[:-3]
    if netloc.endswith(":443"):
        return netloc[:-4]
    return netloc


def strip_www(host: str) -> str:
    host = (host or "").strip().lower()
    if host.startswith("www."):
        return host[4:]
    return host


def normalize_path(path: str) -> str:
    path = (path or "").strip()
    return path if path else "/"


def is_www_only_redirect(from_url: str, location: str) -> bool:
    if not location:
        return False

    try:
        target_url = urljoin(from_url, location)

        src = urlparse(from_url)
        dst = urlparse(target_url)

        src_host = strip_default_port(src.netloc)
        dst_host = strip_default_port(dst.netloc)

        if not src_host or not dst_host:
            return False

        src_base = strip_www(src_host)
        dst_base = strip_www(dst_host)

        # Same underlying domain after removing www.
        if src_base != dst_base:
            return False

        # Must actually change between www and non-www.
        if src_host == dst_host:
            return False

        src_is_www = src_host.startswith("www.")
        dst_is_www = dst_host.startswith("www.")

        if src_is_www == dst_is_www:
            return False

        # Keep meaningful path redirects as REVIEW.
        if normalize_path(src.path) != normalize_path(dst.path):
            return False

        return True

    except Exception:
        return False


def classify_http_result(code: int, from_url: str, location: str) -> str:
    # Required behavior:
    # - 200 => UP
    # - 3xx => UP only if redirect is just www <-> non-www
    # - other 3xx => REVIEW
    # - everything else => DOWN
    if code == 200:
        return "UP"

    if 300 <= code <= 399:
        if is_www_only_redirect(from_url, location):
            return "UP"
        return "REVIEW"

    return "DOWN"


def check_endpoint(client: httpx.Client, ep: Endpoint) -> dict:
    last_status: Optional[int] = None
    last_error_type: str = ""
    last_error_detail: str = ""
    last_latency_ms: Optional[int] = None

    for attempt in range(1, RETRIES + 1):
        t0 = time.perf_counter()
        try:
            # IMPORTANT: do NOT follow redirects so we can inspect raw 3xx responses
            resp = client.request(ep.method, ep.url, follow_redirects=False)
            dt_ms = int((time.perf_counter() - t0) * 1000)

            last_status = resp.status_code
            last_latency_ms = dt_ms
            last_error_type = ""
            last_error_detail = ""

            location = resp.headers.get("location", "")
            state = classify_http_result(resp.status_code, ep.url, location)
            slow = dt_ms > ep.slow_ms

            # UP or REVIEW are final (no retry)
            if state in ("UP", "REVIEW"):
                return {
                    "state": state,
                    "status_code": resp.status_code,
                    "error_type": "" if state == "UP" else f"http_{resp.status_code}",
                    "error_detail": "" if state == "UP" else f"Redirect target: {location}",
                    "latency_ms": dt_ms,
                    "attempts": attempt,
                    "slow": 1 if slow else 0,
                }

            # DOWN (retry)
            last_error_type = f"http_{resp.status_code}"
            last_error_detail = ""

        except Exception as e:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            last_latency_ms = dt_ms
            last_error_type = classify_error(e)
            last_error_detail = f"{e.__class__.__name__}: {e}"

        if attempt < RETRIES:
            time.sleep(1.0)

    # After retries -> DOWN
    return {
        "state": "DOWN",
        "status_code": last_status if last_status is not None else "",
        "error_type": last_error_type or "unknown",
        "error_detail": last_error_detail,
        "latency_ms": last_latency_ms if last_latency_ms is not None else "",
        "attempts": RETRIES,
        "slow": 0,
    }


def append_check_row(path: Path, ts_utc: str, site_id: int, endpoint_id: int, result: dict) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                ts_utc,
                site_id,
                endpoint_id,
                result["state"],
                result["status_code"],
                result["error_type"],
                result["error_detail"],
                result["latency_ms"],
                result["attempts"],
                result["slow"],
            ]
        )


def main() -> None:
    site_name, endpoints = load_config(CONFIG_XLSX)

    if not endpoints:
        print("No endpoints to check (are sites enabled in sites.xlsx?).")
        return

    ts_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Running checks at {ts_utc} (UTC) ...")
    daily_csv = log_path_for_ts(ts_utc)
    ensure_checks_csv(daily_csv)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SiteMonitor/0.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close",
    }

    with httpx.Client(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers=headers,
        http2=False,
        trust_env=False,
    ) as client:
        for ep in endpoints:
            res = check_endpoint(client, ep)
            append_check_row(daily_csv, ts_utc, ep.site_id, ep.endpoint_id, res)

            code_txt = res["status_code"] if res["status_code"] != "" else "-"
            err_txt = res["error_type"] if res["error_type"] else "-"
            print(
                f"[{site_name.get(ep.site_id, str(ep.site_id))}] endpoint {ep.endpoint_id}: "
                f"{res['state']} code={code_txt} err={err_txt} ms={res['latency_ms']} attempts={res['attempts']}"
            )
            if res["error_detail"]:
                print(f"  detail: {res['error_detail']}")

    print(f"Done. Appended to {daily_csv}")


if __name__ == "__main__":
    main()