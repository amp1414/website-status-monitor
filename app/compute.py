import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
BROWSER_LOGS_DIR = DATA_DIR / "browser_logs"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
STATUS_JSON = DATA_DIR / "status.json"
CONFIG_XLSX = DATA_DIR / "sites.xlsx"

WINDOW_DAYS = 7
RETENTION_DAYS = 30
EASTERN = ZoneInfo("America/Toronto")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def last_n_days_paths(n_days: int) -> list[Path]:
    today = datetime.now(timezone.utc).date()
    return [
        LOGS_DIR / f"{(today - timedelta(days=i)).isoformat()}.csv"
        for i in range(n_days)
    ]


def last_n_browser_log_paths(n_days: int) -> list[Path]:
    today = datetime.now(timezone.utc).date()
    return [
        BROWSER_LOGS_DIR / f"{(today - timedelta(days=i)).isoformat()}.csv"
        for i in range(n_days)
    ]


def load_logs(paths: list[Path]) -> pd.DataFrame:
    dfs = []
    for p in paths:
        if p.exists():
            dfs.append(pd.read_csv(p))

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce")
    df["site_id"] = pd.to_numeric(df["site_id"], errors="coerce")
    df["endpoint_id"] = pd.to_numeric(df["endpoint_id"], errors="coerce")

    return df


def load_browser_logs(paths: list[Path]) -> pd.DataFrame:
    dfs = []
    for p in paths:
        if p.exists():
            dfs.append(pd.read_csv(p))

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce")
    df["site_id"] = pd.to_numeric(df["site_id"], errors="coerce")
    df["endpoint_id"] = pd.to_numeric(df["endpoint_id"], errors="coerce")

    for col in ["level", "message", "source", "exception_rule_id"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    if "line" not in df.columns:
        df["line"] = ""
    if "column" not in df.columns:
        df["column"] = ""

    return df


def load_config(xlsx_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Missing config: {xlsx_path}")

    sites_df = pd.read_excel(xlsx_path, sheet_name="sites")
    endpoints_df = pd.read_excel(xlsx_path, sheet_name="endpoints")

    sites_df["site_id"] = pd.to_numeric(sites_df["site_id"], errors="coerce")
    endpoints_df["site_id"] = pd.to_numeric(endpoints_df["site_id"], errors="coerce")
    endpoints_df["endpoint_id"] = pd.to_numeric(endpoints_df["endpoint_id"], errors="coerce")

    if "enabled" in sites_df.columns:
        enabled_ids = set(
            sites_df.loc[sites_df["enabled"] == 1, "site_id"].dropna().astype(int)
        )
        endpoints_df = endpoints_df[
            endpoints_df["site_id"].astype(int).isin(enabled_ids)
        ].copy()

    return sites_df, endpoints_df


def build_timeline(df_one: pd.DataFrame) -> list[dict]:
    if df_one.empty:
        return []

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=WINDOW_DAYS)

    df_one = df_one[
        (df_one["ts_utc"] >= start) & (df_one["ts_utc"] <= end)
    ].sort_values("ts_utc")

    if df_one.empty:
        return []

    timestamps = df_one["ts_utc"].tolist()
    states = df_one["state"].astype(str).tolist()

    segments = []

    for i in range(len(timestamps)):
        t0 = timestamps[i]
        t1 = timestamps[i + 1] if i + 1 < len(timestamps) else end
        duration = max(0, int((t1 - t0).total_seconds()))

        state = states[i]

        if segments and segments[-1]["state"] == state:
            segments[-1]["duration_seconds"] += duration
        else:
            segments.append({
                "state": state,
                "duration_seconds": duration
            })

    return segments


def format_eastern(dt_utc):
    if pd.isna(dt_utc) or dt_utc is None:
        return None

    if isinstance(dt_utc, str):
        try:
            dt_utc = pd.to_datetime(dt_utc, utc=True, errors="coerce")
        except Exception:
            return None

    if pd.isna(dt_utc):
        return None

    dt_local = dt_utc.astimezone(EASTERN)
    return dt_local.strftime("%b %d, %Y • %I:%M %p")


def load_previous_snapshot() -> dict:
    if not STATUS_JSON.exists():
        return {}

    try:
        return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def daily_screenshot_path(site_id: int, endpoint_id: int) -> Path:
    day = datetime.now(timezone.utc).date().isoformat()
    return SCREENSHOTS_DIR / "daily" / str(site_id) / f"{day}_endpoint_{endpoint_id}.png"


def path_to_artifact_url(path: Path) -> str:
    try:
        rel = path.relative_to(DATA_DIR)
        return "/" + rel.as_posix()
    except Exception:
        return ""


def ensure_event_screenshot(
    site_id: int,
    endpoint_id: int,
    previous_state: str,
    new_state: str,
) -> str:
    source = daily_screenshot_path(site_id, endpoint_id)
    if not source.exists():
        return ""

    events_dir = SCREENSHOTS_DIR / "events" / str(site_id)
    events_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    out = events_dir / f"{ts}_endpoint_{endpoint_id}_{previous_state}_{new_state}.png"

    try:
        shutil.copy2(source, out)
        return path_to_artifact_url(out)
    except Exception:
        return ""


def summarize_browser_group(df_group: pd.DataFrame) -> dict:
    if df_group.empty:
        return {
            "console_status": "CLEAN",
            "console_issue_count": 0,
            "console_ignored_count": 0,
            "console_issues_recent": [],
        }

    df_group = df_group.sort_values("ts_utc")

    issue_mask = df_group["exception_rule_id"].astype(str).str.strip() == ""
    issues_df = df_group[issue_mask].copy()
    ignored_df = df_group[~issue_mask].copy()

    recent = []
    for _, row in issues_df.tail(5).iterrows():
        recent.append({
            "ts": format_eastern(row.get("ts_utc")),
            "level": "" if pd.isna(row.get("level")) else str(row.get("level")),
            "message": "" if pd.isna(row.get("message")) else str(row.get("message")),
            "source_url": "" if pd.isna(row.get("source")) else str(row.get("source")),
            "is_exception": 0,
        })

    issue_count = len(issues_df)
    ignored_count = len(ignored_df)

    if issue_count > 0:
        status = "ISSUES"
    elif ignored_count > 0:
        status = "EXCEPTED"
    else:
        status = "CLEAN"

    return {
        "console_status": status,
        "console_issue_count": int(issue_count),
        "console_ignored_count": int(ignored_count),
        "console_issues_recent": recent,
    }


def compute_snapshot(
    df: pd.DataFrame,
    sites_df: pd.DataFrame,
    endpoints_df: pd.DataFrame,
    browser_df: pd.DataFrame,
    previous_snapshot: dict,
) -> dict:

    snapshot = {
        "generated_at": format_eastern(datetime.now(timezone.utc)),
        "window_days": WINDOW_DAYS,
        "sites": [],
    }

    if df.empty:
        return snapshot

    df = df.sort_values("ts_utc").copy()

    latest = df.groupby(["site_id", "endpoint_id"], dropna=False).tail(1).copy()

    df["is_success"] = df["state"].isin(["UP", "REVIEW"])
    uptime = (
        df.groupby(["site_id", "endpoint_id"])["is_success"]
        .mean()
        .reset_index()
        .rename(columns={"is_success": "uptime"})
    )

    latest = latest.merge(
        uptime, on=["site_id", "endpoint_id"], how="left"
    )

    sites_meta = sites_df[["site_id", "name"]].drop_duplicates()
    latest = latest.merge(sites_meta, on="site_id", how="left")

    ep_meta = endpoints_df[
        ["site_id", "endpoint_id", "url", "method", "slow_ms"]
    ].drop_duplicates()

    latest = latest.merge(
        ep_meta, on=["site_id", "endpoint_id"], how="left"
    )

    groups = df.groupby(["site_id", "endpoint_id"])

    browser_groups = {}
    if not browser_df.empty:
        browser_groups = {
            key: grp.copy()
            for key, grp in browser_df.groupby(["site_id", "endpoint_id"])
        }

    prev_by_key = {}
    if isinstance(previous_snapshot, dict):
        for item in previous_snapshot.get("sites", []):
            key = (item.get("site_id"), item.get("endpoint_id"))
            prev_by_key[key] = item

    for _, row in latest.iterrows():
        if pd.isna(row["site_id"]) or pd.isna(row["endpoint_id"]):
            continue

        site_id = int(row["site_id"])
        endpoint_id = int(row["endpoint_id"])
        key = (site_id, endpoint_id)

        timeline = []
        if key in groups.groups:
            timeline = build_timeline(groups.get_group(key))

        browser_summary = {
            "console_status": "CLEAN",
            "console_issue_count": 0,
            "console_ignored_count": 0,
            "console_issues_recent": [],
        }
        if key in browser_groups:
            browser_summary = summarize_browser_group(browser_groups[key])

        daily_shot = daily_screenshot_path(site_id, endpoint_id)
        daily_url = path_to_artifact_url(daily_shot) if daily_shot.exists() else ""

        prev_item = prev_by_key.get(key, {})
        prev_state = "" if not prev_item else str(prev_item.get("state", ""))
        new_state = str(row["state"])

        last_event_screenshot_url = ""
        last_state_change_at = ""

        if prev_item:
            last_event_screenshot_url = str(prev_item.get("last_event_screenshot_url", "") or "")
            last_state_change_at = str(prev_item.get("last_state_change_at", "") or "")

        if prev_state and prev_state != new_state:
            new_event_url = ensure_event_screenshot(site_id, endpoint_id, prev_state, new_state)
            if new_event_url:
                last_event_screenshot_url = new_event_url
            last_state_change_at = format_eastern(row.get("ts_utc"))

        item = {
            "site_id": site_id,
            "site_name": "" if pd.isna(row.get("name")) else str(row.get("name")),
            "endpoint_id": endpoint_id,
            "url": "" if pd.isna(row.get("url")) else str(row.get("url")),
            "method": "" if pd.isna(row.get("method")) else str(row.get("method")),
            "slow_ms": int(row["slow_ms"]) if pd.notna(row.get("slow_ms")) else None,

            "state": new_state,
            "status_code": (
                int(row["status_code"])
                if pd.notna(row.get("status_code")) and str(row["status_code"]).isdigit()
                else ""
            ),
            "error_type": "" if pd.isna(row.get("error_type")) else str(row.get("error_type")),
            "error_detail": "" if pd.isna(row.get("error_detail")) else str(row.get("error_detail")),
            "latency_ms": int(row["latency_ms"]) if pd.notna(row.get("latency_ms")) else None,
            "attempts": int(row["attempts"]) if pd.notna(row.get("attempts")) else None,
            "slow": int(row["slow"]) if pd.notna(row.get("slow")) else 0,
            "last_checked": format_eastern(row.get("ts_utc")),
            "uptime_7d_percent": round(float(row["uptime"]) * 100.0, 2)
                if pd.notna(row.get("uptime")) else None,

            "timeline_7d": timeline,

            "console_status": browser_summary["console_status"],
            "console_issue_count": browser_summary["console_issue_count"],
            "console_ignored_count": browser_summary["console_ignored_count"],
            "console_issues_recent": browser_summary["console_issues_recent"],

            "daily_screenshot_url": daily_url,
            "last_event_screenshot_url": last_event_screenshot_url,
            "previous_state": prev_state,
            "last_state_change_at": last_state_change_at,
        }

        snapshot["sites"].append(item)

    order = {"DOWN": 0, "REVIEW": 1, "UP": 2}
    snapshot["sites"].sort(
        key=lambda x: (order.get(x["state"], 9), x["site_name"])
    )

    return snapshot


def cleanup_old_logs(retention_days: int) -> None:
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=retention_days)

    for p in LOGS_DIR.glob("*.csv"):
        if len(p.stem) != 10:
            continue
        try:
            file_date = datetime.fromisoformat(p.stem).date()
            if file_date < cutoff:
                p.unlink()
        except Exception:
            continue

    for p in BROWSER_LOGS_DIR.glob("*.csv"):
        if len(p.stem) != 10:
            continue
        try:
            file_date = datetime.fromisoformat(p.stem).date()
            if file_date < cutoff:
                p.unlink()
        except Exception:
            continue


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    paths = last_n_days_paths(WINDOW_DAYS)
    df = load_logs(paths)

    browser_paths = last_n_browser_log_paths(WINDOW_DAYS)
    browser_df = load_browser_logs(browser_paths)

    sites_df, endpoints_df = load_config(CONFIG_XLSX)
    previous_snapshot = load_previous_snapshot()

    snapshot = compute_snapshot(
        df,
        sites_df,
        endpoints_df,
        browser_df,
        previous_snapshot,
    )

    tmp = STATUS_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    tmp.replace(STATUS_JSON)

    print(f"Wrote {STATUS_JSON}")

    cleanup_old_logs(RETENTION_DAYS)


if __name__ == "__main__":
    main()