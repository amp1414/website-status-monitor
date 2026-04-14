from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
STATUS_JSON = DATA_DIR / "status.json"
ALERTS_STATE_JSON = DATA_DIR / "alerts_state.json"

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_recipients(value: str) -> list[str]:
    parts = []
    for token in value.replace(";", ",").split(","):
        email = token.strip()
        if email:
            parts.append(email)
    if not parts:
        raise RuntimeError("ALERT_TO_EMAILS is empty.")
    return parts


def make_site_key(site: dict) -> str:
    return f"{site.get('site_id')}:{site.get('endpoint_id')}"


def build_subject(down_sites: list[dict]) -> str:
    if len(down_sites) == 1:
        return f"[Site Monitor] DOWN — {down_sites[0].get('site_name', 'Unknown site')}"
    return f"[Site Monitor] DOWN — {len(down_sites)} websites"


def build_text_body(down_sites: list[dict], dashboard_url: str) -> str:
    lines = []
    lines.append("One or more monitored websites are DOWN.")
    lines.append("")

    for site in down_sites:
        lines.append(f"Site: {site.get('site_name', '-')}")
        lines.append(f"Endpoint ID: {site.get('endpoint_id', '-')}")
        lines.append(f"URL: {site.get('url', '-')}")
        lines.append(f"State: {site.get('state', '-')}")
        lines.append(f"Status code: {site.get('status_code', '-') or '-'}")
        lines.append(f"Error type: {site.get('error_type', '-') or '-'}")
        lines.append(f"Error detail: {site.get('error_detail', '-') or '-'}")
        lines.append(f"Last checked: {site.get('last_checked', '-')}")
        lines.append(f"Tracking since: {site.get('tracking_since', '-')}")
        lines.append("")

    lines.append(f"Dashboard: {dashboard_url}")
    return "\n".join(lines)


def send_sendgrid_email(
    *,
    api_key: str,
    from_email: str,
    to_emails: list[str],
    subject: str,
    text_body: str,
) -> None:
    payload = {
        "personalizations": [
            {
                "to": [{"email": email} for email in to_emails],
            }
        ],
        "from": {"email": from_email},
        "subject": subject,
        "content": [
            {
                "type": "text/plain",
                "value": text_body,
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(SENDGRID_API_URL, headers=headers, json=payload)

    if response.status_code != 202:
        raise RuntimeError(
            f"SendGrid send failed: status={response.status_code} body={response.text}"
        )


def collect_new_down_sites(snapshot: dict, alerts_state: dict) -> tuple[list[dict], dict]:
    next_state = dict(alerts_state)
    new_down_sites: list[dict] = []

    for site in snapshot.get("sites", []):
        key = make_site_key(site)
        current_state = str(site.get("state", "")).strip().upper()
        previous_state = str(next_state.get(key, {}).get("last_seen_state", "")).strip().upper()

        if current_state == "DOWN":
            if previous_state != "DOWN":
                new_down_sites.append(site)
            else:
                next_state[key] = {
                    **next_state.get(key, {}),
                    "last_seen_state": "DOWN",
                    "last_seen_at": utc_now_iso(),
                }
        else:
            next_state[key] = {
                **next_state.get(key, {}),
                "last_seen_state": current_state,
                "last_seen_at": utc_now_iso(),
            }

    return new_down_sites, next_state


def main() -> None:
    api_key = get_required_env("SENDGRID_API_KEY")
    from_email = get_required_env("ALERT_FROM_EMAIL")
    to_emails = parse_recipients(get_required_env("ALERT_TO_EMAILS"))
    dashboard_url = os.getenv("DASHBOARD_URL", "http://40.233.115.28:8000/").strip()

    snapshot = load_json(STATUS_JSON, {"sites": []})
    alerts_state = load_json(ALERTS_STATE_JSON, {})

    new_down_sites, next_state = collect_new_down_sites(snapshot, alerts_state)

    if not new_down_sites:
        write_json(ALERTS_STATE_JSON, next_state)
        print("Alerts: no new DOWN websites.")
        return

    subject = build_subject(new_down_sites)
    text_body = build_text_body(new_down_sites, dashboard_url)

    send_sendgrid_email(
        api_key=api_key,
        from_email=from_email,
        to_emails=to_emails,
        subject=subject,
        text_body=text_body,
    )

    now = utc_now_iso()
    for site in new_down_sites:
        key = make_site_key(site)
        next_state[key] = {
            **next_state.get(key, {}),
            "last_seen_state": "DOWN",
            "last_seen_at": now,
            "last_alerted_down_at": now,
            "last_alert_subject": subject,
        }

    write_json(ALERTS_STATE_JSON, next_state)
    print(f"Alerts: sent DOWN alert for {len(new_down_sites)} website(s).")


if __name__ == "__main__":
    main()