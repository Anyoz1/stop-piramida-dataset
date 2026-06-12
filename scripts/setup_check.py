#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.download_videoteca import DEFAULT_CDP_URL, DEFAULT_METADATA, DEFAULT_OUTPUT_DIR, run_doctor


def main() -> None:
    ok = run_doctor(DEFAULT_CDP_URL, DEFAULT_METADATA, DEFAULT_OUTPUT_DIR)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
