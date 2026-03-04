import time
from datetime import datetime

from checker import main as run_checker
from compute import main as run_compute

INTERVAL_SECONDS = 3600  # hourly


def main():
    print("Starting monitor loop. Ctrl+C to stop.")
    while True:
        print("\n---", datetime.now().isoformat(timespec="seconds"), "---")

        checker_ok = True
        try:
            run_checker()
        except Exception as e:
            checker_ok = False
            print("Checker failed:", repr(e))

        try:
            run_compute()
        except Exception as e:
            print("Compute failed:", repr(e))

        # Optional: if checker failed, you may want a shorter retry window
        # For now, keep it simple and sleep the normal interval.
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()