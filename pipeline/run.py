"""Run the whole pipeline: fetch -> filter -> classify -> build sample pages -> build site.
Usage:  python pipeline/run.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for step in ("fetch.py", "filter.py", "classify.py", "build_sample.py", "build_site.py"):
    print(f"\n=== {step} ===")
    result = subprocess.run([sys.executable, str(HERE / step)], cwd=HERE)
    if result.returncode != 0:
        sys.exit(f"{step} failed; stopping.")
print("\nPipeline finished.")
