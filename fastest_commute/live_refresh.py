#!/usr/bin/env python3
"""
Periodically regenerates the comparison map so the browser auto-refreshes
with the latest data. Run alongside the data collection.
"""

import time
import sys
from pathlib import Path

INTERVAL_S = 60  # regenerate every 60 seconds

def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else INTERVAL_S
    print(f"Live refresh: regenerating comparison map every {interval}s")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            import importlib
            import visualize
            importlib.reload(visualize)
            df = visualize.load_results()
            n = len(df)
            print(f"[{time.strftime('%H:%M:%S')}] {n} rows — regenerating...", end=" ", flush=True)
            visualize.create_comparison_map(df)
            print("done")
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(interval)


if __name__ == "__main__":
    main()
