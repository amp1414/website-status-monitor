import time
from datetime import datetime

from app.checker import main as run_checker
from app.browser_audit import main as run_browser_audit
from app.compute import main as run_compute
from app.alerts import main as run_alerts

INTERVAL_SECONDS = 300  # poll every 5 minutes


def main():
    print("Starting monitor loop. Ctrl+C to stop.")
    while True:
        print("\n---", datetime.now().isoformat(timespec="seconds"), "---")

        checked_endpoints = []

        try:
            checked_endpoints = run_checker() or []
        except Exception as e:
            print("Checker failed:", repr(e))
            checked_endpoints = []

        try:
            run_browser_audit(checked_endpoints)
        except Exception as e:
            print("Browser audit failed:", repr(e))

        try:
            run_compute()
        except Exception as e:
            print("Compute failed:", repr(e))

        try:
            run_alerts()
        except Exception as e:
            print("Alerts failed:", repr(e))

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()