import io
import zipfile
from pathlib import Path

import requests

URL = "https://storage.googleapis.com/hiring-problem-statements/store-monitoring-data.zip"
DATA_DIR = Path("data")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading dataset...")
    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()

    print("Extracting...")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(DATA_DIR)

    print(f"Done. Files extracted to {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()


