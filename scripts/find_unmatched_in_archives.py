import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import glob

# Check archived or other registers
print("Searching registers...")
for f in glob.glob("data/**/*.csv", recursive=True):
    if "archive" in f.lower() or "master" in f.lower() or "register" in f.lower():
        print("Found:", f)

# Check if unmatched plots are in archived plots
archived_files = glob.glob("data/**/archive*.csv", recursive=True) + glob.glob("data/**/*archived*.csv", recursive=True)
print("Archived files:", archived_files)
