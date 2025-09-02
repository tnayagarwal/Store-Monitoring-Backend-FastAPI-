import time
import sys
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
OUT = Path("sample_report.csv")


def main() -> int:
    try:
        r = requests.post(f"{BASE}/trigger_report", timeout=30)
        r.raise_for_status()
        report_id = r.json()["report_id"]
    except Exception as exc:
        print(f"Failed to trigger report: {exc}")
        return 1

    for _ in range(240):  # up to ~120s
        try:
            s = requests.get(f"{BASE}/get_report", params={"report_id": report_id}, timeout=30)
            if s.headers.get("X-Report-Status") == "Complete" or (
                s.status_code == 200 and s.headers.get("content-type", "").startswith("text/csv")
            ):
                OUT.write_bytes(s.content)
                print(f"Saved {OUT.resolve()}")
                return 0
            else:
                # Likely Running
                time.sleep(0.5)
        except Exception:
            time.sleep(0.5)
    print("Timed out waiting for report")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


